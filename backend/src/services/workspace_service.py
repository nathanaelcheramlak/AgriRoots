"""All office access, version changes and publication are enforced server-side."""
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from src.api.schemas.workspace import RECORD_SCHEMAS, AdvisoryInput, RecordInput, Transition
from src.db.models.user import User
from src.db.models.workspace import (Administrator, Office, Membership, WorkspaceRecord,
                                     Advisory, AdvisoryVersion, WorkspaceEvent)


def fail(code, detail):
    raise HTTPException(code, detail)


class WorkspaceService:
    def __init__(self, db: Session, user: User):
        self.db, self.user = db, user

    def event(self, office_id, entity_id, action, **details):
        self.db.add(WorkspaceEvent(office_id=office_id, actor_id=self.user.user_id,
                                  entity_id=entity_id, action=action, details=details))

    def membership(self, office_id, roles=("administrator", "officer")):
        member = self.db.get(Membership, (office_id, self.user.user_id))
        if not member or member.role not in roles:
            fail(403, "Office permission required")
        return member

    def officer(self, office_id, user_id):
        member = self.db.get(Membership, (office_id, user_id))
        if not member or member.role not in ("officer", "administrator"):
            fail(422, "Assigned officer must belong to this office")

    def record(self, office_id, record_id, kind=None):
        row = self.db.get(WorkspaceRecord, record_id)
        if not row or row.office_id != office_id or (kind and row.kind != kind):
            fail(404, "Office record not found")
        return row

    def create_office(self, name):
        if not self.db.get(Administrator, self.user.user_id):
            fail(403, "Provisioned administrator required")
        office = Office(name=name)
        self.db.add(office)
        self.db.flush()
        # A user has one office; global administrators can create additional offices
        # and delegate them, but do not acquire cross-office record access.
        if not self.db.scalar(select(Membership).where(Membership.user_id == self.user.user_id)):
            self.db.add(Membership(office_id=office.id, user_id=self.user.user_id, role="administrator"))
        self.event(office.id, office.id, "office_created", name=name)
        self.db.commit()
        self.db.refresh(office)
        return office

    def assign_member(self, office_id, payload):
        if not self.db.get(Office, office_id):
            fail(404, "Office not found")
        global_admin = self.db.get(Administrator, self.user.user_id)
        if not global_admin:
            self.membership(office_id, ("administrator",))
        user = self.db.get(User, payload.user_id)
        if not user or not user.is_active:
            fail(422, "Active registered account required")
        existing = self.db.scalar(select(Membership).where(Membership.user_id == payload.user_id))
        if existing:
            # Memberships are permanent in Phase 1; moving/removing staff needs a
            # separate audited reassignment workflow for their existing records.
            if existing.office_id == office_id and existing.role == payload.role:
                return existing
            fail(409, "Account already has an office role; reassignment is not supported")
        row = Membership(office_id=office_id, user_id=payload.user_id, role=payload.role)
        self.db.add(row)
        self.event(office_id, payload.user_id, "role_assigned", role=payload.role)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_record(self, office_id, payload: RecordInput, record_id=None):
        self.membership(office_id)
        try:
            data = RECORD_SCHEMAS[payload.kind].model_validate(payload.data).model_dump(mode="json")
        except ValidationError as exc:
            fail(422, str(exc))
        old = self.record(office_id, record_id, payload.kind) if record_id else None
        if old and old.kind in ("evidence", "guidance", "calendar"):
            fail(409, "Reviewed sources are immutable; create a new record")
        if "assigned_officer_id" in data:
            self.officer(office_id, data["assigned_officer_id"])
        if payload.kind == "household":
            self.record(office_id, data["cluster_id"], "cluster")
            member = self.db.get(Membership, (office_id, data["farmer_user_id"]))
            if not member or member.role != "farmer":
                fail(422, "Link an administrator-enrolled farmer from this office")
            if old and old.data["farmer_user_id"] != data["farmer_user_id"]:
                fail(409, "Household account ownership is immutable")
            for household in self.db.scalars(select(WorkspaceRecord).where(
                    WorkspaceRecord.kind == "household", WorkspaceRecord.office_id == office_id)):
                if household.id != record_id and household.data["farmer_user_id"] == data["farmer_user_id"]:
                    fail(409, "Farmer is already linked to a household")
        for field, kind in (("household_id", "household"), ("plot_id", "plot")):
            if data.get(field):
                self.record(office_id, data[field], kind)
                if old and old.data[field] != data[field]:
                    fail(409, "Record ownership is immutable")
        if old:
            before = old.data.copy()
            changed = self.db.execute(update(WorkspaceRecord).where(
                WorkspaceRecord.id == old.id,
                WorkspaceRecord.revision == payload.expected_revision,
            ).values(data=data, revision=WorkspaceRecord.revision + 1)).rowcount
            if not changed:
                fail(409, "Record changed; reload before editing")
            self.event(office_id, old.id, "record_edited", before=before, after=data)
            row = old
        else:
            row = WorkspaceRecord(office_id=office_id, kind=payload.kind, data=data,
                                  created_by=self.user.user_id, farmer_user_id=data.get("farmer_user_id") if payload.kind == "household" else None)
            self.db.add(row)
            self.db.flush()
            self.event(office_id, row.id, "record_created", kind=payload.kind, data=data)
        self.db.commit()
        self.db.refresh(row)
        return row

    def advisory(self, office_id, advisory_id):
        self.membership(office_id)
        row = self.db.get(Advisory, advisory_id)
        if not row or row.office_id != office_id:
            fail(404, "Advisory not found")
        return row

    def version(self, advisory_id, version):
        return self.db.scalar(select(AdvisoryVersion).where(
            AdvisoryVersion.advisory_id == advisory_id, AdvisoryVersion.version == version))

    def claim(self, advisory):
        # Compare-and-swap serializes edits and lifecycle actions on SQLite and
        # PostgreSQL. The audit event and status change commit in one transaction.
        result = self.db.execute(update(Advisory).where(
            Advisory.id == advisory.id, Advisory.revision == advisory.revision,
        ).values(revision=Advisory.revision + 1), execution_options={"synchronize_session": False})
        if not result.rowcount:
            self.db.rollback()
            fail(409, "Advisory changed; reload before continuing")

    def save_advisory(self, office_id, payload: AdvisoryInput, advisory_id=None, *, commit=True):
        self.membership(office_id)
        self.officer(office_id, payload.assigned_officer_id)
        households = [self.record(office_id, h, "household") for h in set(payload.household_ids)]
        for p in payload.plot_ids:
            plot = self.record(office_id, p, "plot")
            if plot.data["household_id"] not in payload.household_ids:
                fail(422, "Target plot must belong to a target household")
        snapshots = {}
        for recommendation in payload.recommendations:
            for evidence_id in recommendation.evidence_ids:
                evidence = self.record(office_id, evidence_id, "evidence")
                if evidence.data.get("plot_id") and evidence.data["plot_id"] not in payload.plot_ids:
                    fail(422, "Evidence plot must be targeted")
                if evidence.data["classification"] == "synthetic" and any(not h.data["synthetic"] for h in households):
                    fail(422, "Synthetic evidence requires labelled synthetic households")
                snapshots[evidence_id] = evidence.data
        if payload.replaces_advisory_id:
            replaced = self.advisory(office_id, payload.replaces_advisory_id)
            if replaced.id == advisory_id:
                fail(422, "An advisory cannot replace itself")
            if not self.db.scalar(select(AdvisoryVersion).where(
                    AdvisoryVersion.advisory_id == replaced.id, AdvisoryVersion.status == "released")):
                fail(422, "Replacement must refer to a released advisory")
        if advisory_id:
            advisory = self.advisory(office_id, advisory_id)
            if payload.expected_version != advisory.current_version:
                fail(409, "Version changed; reload before editing")
            self.claim(advisory)
            advisory.current_version += 1
            version_number = advisory.current_version
        else:
            advisory = Advisory(office_id=office_id)
            self.db.add(advisory)
            self.db.flush()
            version_number = 1
        version = AdvisoryVersion(advisory_id=advisory.id, version=version_number,
            content=payload.model_dump(mode="json", exclude={"expected_version"}),
            recipient_user_ids=sorted({h.data["farmer_user_id"] for h in households}),
            evidence_snapshots=snapshots, created_by=self.user.user_id)
        self.db.add(version)
        self.db.flush()
        self.event(office_id, advisory.id, "edited" if advisory_id else "created", version=version_number)
        if commit:
            self.db.commit()
            self.db.refresh(version)
        return version

    def transition(self, office_id, advisory_id, payload: Transition):
        advisory = self.advisory(office_id, advisory_id)
        version = self.version(advisory.id, payload.expected_version)
        if not version:
            fail(404, "Version not found")
        if payload.action == "release" and version.status == "released":
            return version
        if payload.expected_version != advisory.current_version:
            fail(409, "Only the current version can change state")
        transitions = {"submit": (("draft", "rejected"), "pending_review"),
                       "approve": (("pending_review",), "approved"),
                       "reject": (("pending_review",), "rejected"),
                       "cancel": (("draft", "pending_review", "approved", "rejected"), "cancelled"),
                       "release": (("approved",), "released")}
        allowed, target = transitions[payload.action]
        if version.status not in allowed:
            fail(409, f"Cannot {payload.action} a {version.status} version")
        if payload.action in ("reject", "cancel") and not payload.reason.strip():
            fail(422, "A reason is required")
        if payload.action in ("submit", "approve", "release"):
            if any(not r["evidence_ids"] or any(e not in version.evidence_snapshots for e in r["evidence_ids"])
                   for r in version.content["recommendations"]):
                fail(422, "Each recommendation requires specific stored evidence")
        try:
            self.claim(advisory)
        except HTTPException as exc:
            if exc.status_code == 409 and payload.action == "release":
                version = self.version(advisory_id, payload.expected_version)
                if version and version.status == "released":
                    return version
            raise
        version.status = target
        self.event(office_id, advisory.id, payload.action, version=version.version,
                   version_id=version.id, reason=payload.reason)
        self.db.commit()
        self.db.refresh(version)
        return version

    def released(self, version_id=None):
        query = select(AdvisoryVersion).where(AdvisoryVersion.status == "released")
        if version_id:
            query = query.where(AdvisoryVersion.id == version_id)
        rows = [v for v in self.db.scalars(query) if self.user.user_id in v.recipient_user_ids]
        if version_id:
            if not rows:
                fail(404, "Released advisory not found")
            return rows[0]
        return rows


def public_version(version):
    # Internal recipients, officer IDs and audit details are never sent to farmers.
    c = version.content
    return {"id": version.id, "advisory_id": version.advisory_id, "version": version.version,
            "title": c["title"], "language": c["language"], "recommendations": c["recommendations"],
            "missing_information": c["missing_information"], "translations": c["translations"],
            "evidence": version.evidence_snapshots,
            "replaces_advisory_id": c.get("replaces_advisory_id"), "created_at": version.created_at}
