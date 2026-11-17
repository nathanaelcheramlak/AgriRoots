"""Office/assignment scoped registry transactions; no agricultural provider calls here."""

import json
from datetime import UTC, datetime

from shapely.geometry import shape
from sqlalchemy import Text, cast, func, or_, select, text
from sqlalchemy.exc import IntegrityError

from src.db.models.connectors import ConnectorJob
from src.db.models.farm_registry import (
    CropSeason,
    Farmer,
    FarmerPlot,
    PlotRun,
    RegisteredPlot,
    Territory,
    TerritoryAssignment,
)
from src.db.models.workspace import Membership, WorkspaceRecord
from src.integrations.contracts import ConnectorError, digest
from src.integrations.secrets import cipher, encrypt
from src.integrations.service import IntegrationService, audit
from src.registry.access import require_territory, territory_scope
from src.registry.geometry import area, invalid, point, validate_geometry
from src.tools.policy import authorized_plots, require_admin


def page(db, query, limit, offset):
    total = db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    return list(db.scalars(query.limit(limit).offset(offset))), {"total": total, "limit": limit, "offset": offset}


def timestamp(value):
    value = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return value.isoformat().replace("+00:00", "Z")


class FarmRegistry(IntegrationService):
    def commit(self, ident, action, **details):
        audit(self.db, self.principal, ident, action, **details)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            raise ConnectorError(
                "VERSION_CONFLICT", "Registry record already exists or changed; reload before retrying"
            ) from None

    def territory_view(self, row):
        return {
            "id": row.id,
            "name": row.name,
            "region": row.region,
            "district": row.district,
            "description": row.description,
            "officeId": row.office_id,
            "status": row.status,
            "origin": "backend",
            "boundary": row.boundary,
            "createdAt": timestamp(row.created_at),
            "revision": row.revision,
            "area_m2": row.area_m2,
        }

    def territories(self, limit=20, offset=0):
        visible = territory_scope(self.principal)
        if self.principal.role == "office_admin":
            visible = Territory.office_id == self.principal.office_id
        else:
            visible = or_(
                visible,
                (Territory.office_id == self.principal.office_id)
                & (Territory.created_by == self.principal.user_id)
                & (Territory.status != "assigned"),
            )
        rows, meta = page(
            self.db, select(Territory).where(visible).order_by(Territory.created_at, Territory.id), limit, offset
        )
        return {"items": [self.territory_view(r) for r in rows], **meta}

    def propose(self, payload):
        if self.principal.role == "viewer":
            raise ConnectorError("POLICY_DENIED", "Viewers cannot propose territories")
        _, size = validate_geometry(payload.boundary)
        row = Territory(
            **payload.model_dump(), office_id=self.principal.office_id, area_m2=size, created_by=self.principal.user_id
        )
        self.db.add(row)
        self.db.flush()
        self.commit(row.id, "territory_proposed", revision=1)
        return self.territory_view(row)

    def review(self, ident, payload):
        require_admin(self.principal)
        row = self.owned(Territory, ident, lock=True)
        if row.revision != payload.expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Territory changed; reload")
        if payload.decision in ("approve", "reject") and row.status != "pending-approval":
            raise ConnectorError("VERSION_CONFLICT", "Only pending proposals can be reviewed")
        row.status = {"approve": "assigned", "reject": "inactive", "deactivate": "inactive"}[payload.decision]
        row.revision += 1
        self.commit(row.id, "territory_reviewed", decision=payload.decision, revision=row.revision)
        return self.territory_view(row)

    def edit_territory(self, ident, payload):
        row = self.owned(Territory, ident, lock=True)
        if self.principal.role != "office_admin" and not (
            row.created_by == self.principal.user_id and row.status == "pending-approval"
        ):
            raise ConnectorError("POLICY_DENIED", "Only office administrators can change an official boundary")
        if row.revision != payload.expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Territory changed; reload")
        geometry, size = validate_geometry(payload.boundary)
        for plot in self.db.scalars(select(RegisteredPlot).where(RegisteredPlot.territory_id == ident)):
            if not geometry.covers(shape(plot.boundary)):
                raise ConnectorError("VERSION_CONFLICT", "Territory change would exclude a registered plot")
        for key in ("name", "region", "district", "description", "boundary"):
            setattr(row, key, getattr(payload, key))
        row.area_m2, row.revision = size, row.revision + 1
        self.commit(row.id, "territory_updated", revision=row.revision, boundary_digest=digest(row.boundary))
        return self.territory_view(row)

    def assign(self, ident, payload):
        require_admin(self.principal)
        row = self.owned(Territory, ident, lock=True)
        if row.status != "assigned":
            invalid("Approve the territory before assigning staff")
        member = self.db.get(Membership, (self.principal.office_id, payload.user_id))
        if not member or member.role not in ("administrator", "office_admin", "officer", "extension_officer", "viewer"):
            invalid("Assignee must be an office staff member")
        assignment = TerritoryAssignment(
            office_id=row.office_id,
            territory_id=row.id,
            user_id=payload.user_id,
            role=payload.role,
            starts_at=payload.starts_at or datetime.now(UTC),
            ends_at=payload.ends_at,
        )
        self.db.add(assignment)
        self.db.flush()
        self.commit(row.id, "territory_assigned", assignment_id=assignment.id, assignee_id=assignment.user_id)
        return {
            "id": assignment.id,
            "territory_id": row.id,
            "user_id": assignment.user_id,
            "role": assignment.role,
            "revision": assignment.revision,
        }

    def revoke(self, ident, expected_revision):
        require_admin(self.principal)
        row = self.owned(TerritoryAssignment, ident, lock=True)
        if row.revision != expected_revision:
            raise ConnectorError("VERSION_CONFLICT", "Assignment changed; reload")
        row.revoked = True
        row.revision += 1
        self.commit(row.territory_id, "territory_assignment_revoked", assignment_id=row.id)
        return {"id": row.id, "revoked": True, "revision": row.revision}

    def farmer(self, ident, *, write=False, lock=False):
        row = self.owned(Farmer, ident, lock=lock)
        require_territory(self.db, self.principal, row.territory_id, write=write)
        return row

    def farmer_view(self, row, *, private=False):
        result = {
            "id": row.id,
            "territory_id": row.territory_id,
            "reference": row.reference,
            "display_name": row.display_name,
            "village": row.village,
            "synthetic": row.synthetic,
            "revision": row.revision,
            **row.profile,
            "verification": "unverified",
        }
        if private:
            require_admin(self.principal)
            result["private"] = json.loads(cipher().decrypt(row.private_ciphertext.encode()))
        return result

    def farmers(self, territory_id=None, search="", limit=25, offset=0):
        query = select(Farmer).where(
            Farmer.office_id == self.principal.office_id,
            Farmer.territory_id.in_(select(Territory.id).where(territory_scope(self.principal))),
        )
        if territory_id:
            require_territory(self.db, self.principal, territory_id)
            query = query.where(Farmer.territory_id == territory_id)
        if search:
            query = query.where(
                or_(
                    Farmer.reference.icontains(search, autoescape=True),
                    Farmer.display_name.icontains(search, autoescape=True),
                    Farmer.village.icontains(search, autoescape=True),
                )
            )
        rows, meta = page(self.db, query.order_by(Farmer.reference, Farmer.id), limit, offset)
        return {"items": [self.farmer_view(r) for r in rows], **meta}

    def save_farmer(self, payload, ident=None):
        require_territory(self.db, self.principal, payload.territory_id, write=True, lock=True)
        if payload.synthetic:
            require_admin(self.principal)
        row = self.farmer(ident, write=True, lock=True) if ident else None
        if row and (row.revision != payload.expected_revision or row.territory_id != payload.territory_id):
            raise ConnectorError("VERSION_CONFLICT", "Farmer changed or territory reassignment is required")
        duplicate = self.db.scalar(
            select(Farmer.id).where(
                Farmer.office_id == self.principal.office_id,
                Farmer.reference == payload.reference,
                Farmer.id != (ident or ""),
            )
        )
        if duplicate:
            raise ConnectorError("VERSION_CONFLICT", "Farmer reference already exists in this office")
        if not row:
            row = Farmer(
                office_id=self.principal.office_id, territory_id=payload.territory_id, created_by=self.principal.user_id
            )
            self.db.add(row)
        row.reference, row.display_name, row.village = payload.reference, payload.display_name, payload.village
        row.synthetic = payload.synthetic
        row.profile = {
            "language": payload.language,
            "channel": payload.channel,
            "consent": payload.consent,
            "consent_purpose": payload.consent_purpose,
            "consent_recorded_at": datetime.now(UTC).isoformat(),
        }
        private = json.loads(cipher().decrypt(row.private_ciphertext.encode())) if ident else {}
        for key in ("household", "phone", "email", "preferences", "notes"):
            if not ident or key in payload.model_fields_set:
                private[key] = getattr(payload, key)
        row.private_ciphertext = encrypt(private)
        if ident:
            row.revision += 1
        self.db.flush()
        self.commit(row.id, "farmer_updated" if ident else "farmer_registered", territory_id=row.territory_id)
        return self.farmer_view(row)

    def plot(self, ident, *, write=False, lock=False):
        row = self.owned(RegisteredPlot, ident, lock=lock)
        require_territory(self.db, self.principal, row.territory_id, write=write)
        return row

    def plot_view(self, row, *, details=False):
        record = self.db.get(WorkspaceRecord, row.id)
        season = self.db.scalar(
            select(CropSeason)
            .where(CropSeason.plot_id == row.id)
            .order_by(CropSeason.created_at.desc(), CropSeason.id)
            .limit(1)
        )
        associations = list(
            self.db.scalars(select(FarmerPlot).where(FarmerPlot.plot_id == row.id, FarmerPlot.ends_at.is_(None)))
        )
        result = {
            "id": row.id,
            "territoryId": row.territory_id,
            "name": record.data["name"],
            "geometry": row.boundary,
            "farmerIds": [a.farmer_id for a in associations],
            "status": row.status,
            "origin": "backend",
            "createdAt": timestamp(record.created_at),
            "revision": row.revision,
            "area_m2": row.area_m2,
            "centroid": row.centroid,
            "sampling_point": row.sampling_point,
            "overlaps": row.overlaps,
            "season": {"id": season.id, **season.data} if season else None,
            "home_plot": {
                "id": row.id,
                **{k: record.data[k] for k in ("name", "latitude", "longitude", "area", "area_unit", "synthetic")},
                "crop": season.data.get("crop") if season else None,
                "planting_date": season.data.get("planting_date") if season else None,
            },
        }
        if details:
            result["farmers"] = [self.farmer_view(self.farmer(a.farmer_id)) for a in associations]
            encrypted = record.data.get("private_registry")
            result.update(json.loads(cipher().decrypt(encrypted.encode())) if encrypted else {})
        return result

    def plots(self, territory_id=None, bbox=None, geometry=None, limit=50, offset=0):
        query = select(RegisteredPlot).where(
            RegisteredPlot.office_id == self.principal.office_id,
            RegisteredPlot.territory_id.in_(select(Territory.id).where(territory_scope(self.principal))),
        )
        if territory_id:
            require_territory(self.db, self.principal, territory_id)
            query = query.where(RegisteredPlot.territory_id == territory_id)
        if bbox or geometry:
            if bbox:
                from shapely.geometry import box, mapping

                if len(bbox) != 4 or not -180 <= bbox[0] < bbox[2] <= 180 or not -90 <= bbox[1] < bbox[3] <= 90:
                    invalid("Invalid WGS84 bounding box")
                geometry = json.loads(json.dumps(mapping(box(*bbox))))
            target, _ = validate_geometry(geometry)
            if self.db.bind.dialect.name == "postgresql":
                query = query.where(
                    text("ST_Intersects(registry_plots.geom, ST_SetSRID(ST_GeomFromGeoJSON(:registry_query),4326))")
                )
                query = query.params(registry_query=json.dumps(geometry))
            else:
                # Portable development only. Production uses the indexed predicate above.
                ids = [r.id for r in self.db.scalars(query) if shape(r.boundary).intersects(target)]
                query = query.where(RegisteredPlot.id.in_(ids))
        rows, meta = page(self.db, query.order_by(RegisteredPlot.id), limit, offset)
        return {"items": [self.plot_view(r) for r in rows], **meta}

    def save_plot(self, territory_id, payload, ident=None):
        territory = require_territory(self.db, self.principal, territory_id, write=True, lock=True)
        if payload.synthetic:
            require_admin(self.principal)
        request_digest = digest(payload.model_dump(mode="json"))
        prior = self.db.scalar(
            select(RegisteredPlot).where(
                RegisteredPlot.office_id == self.principal.office_id, RegisteredPlot.request_key == payload.request_key
            )
        )
        if prior and not ident:
            self.plot(prior.id)
            if prior.territory_id != territory_id or prior.request_digest != request_digest:
                raise ConnectorError("VERSION_CONFLICT", "Request key was already used for different data")
            return self.plot_view(prior, details=True)
        geometry, size = validate_geometry(payload.geometry, plot=True)
        if self.db.bind.dialect.name == "postgresql":
            valid, size = self.db.execute(
                text("""SELECT ST_CoveredBy(g, geom), ST_Area(g::geography)
                FROM registry_territories, LATERAL (SELECT ST_SetSRID(ST_GeomFromGeoJSON(:g),4326) AS g) q
                WHERE id=:id"""),
                {"g": json.dumps(payload.geometry), "id": territory.id},
            ).one()
        else:
            valid = shape(territory.boundary).covers(geometry)
        if not valid:
            invalid("The complete plot boundary must be within the assigned territory")
        overlaps = []
        candidates = select(RegisteredPlot).where(
            RegisteredPlot.office_id == self.principal.office_id, RegisteredPlot.id != (ident or "")
        )
        if self.db.bind.dialect.name == "postgresql":
            candidates = candidates.where(
                text("ST_Intersects(registry_plots.geom, ST_SetSRID(ST_GeomFromGeoJSON(:g),4326))")
            ).params(g=json.dumps(payload.geometry))
        for other in self.db.scalars(candidates):
            other_geometry = shape(other.boundary)
            if geometry.equals(other_geometry):
                raise ConnectorError("VERSION_CONFLICT", "An identical plot boundary is already registered")
            intersection = geometry.intersection(other_geometry)
            if (
                not intersection.is_empty
                and intersection.geom_type in ("Polygon", "MultiPolygon")
                and area(intersection) > 1
            ):
                overlaps.append(other.id)
        if overlaps and not payload.acknowledge_overlaps:
            raise ConnectorError(
                "APPROVAL_REQUIRED", "Plot overlaps an existing registration; explicitly acknowledge review"
            )
        for farmer_id in payload.farmer_ids:
            farmer = self.farmer(farmer_id)
            if farmer.territory_id != territory_id:
                invalid("Farmer must belong to the selected assigned territory")
        row = self.plot(ident, write=True, lock=True) if ident else None
        if row and (row.revision != payload.expected_revision or row.territory_id != territory_id):
            raise ConnectorError("VERSION_CONFLICT", "Plot changed; reload")
        sample = geometry.centroid if geometry.covers(geometry.centroid) else geometry.representative_point()
        data = {
            "name": payload.name,
            "latitude": sample.y,
            "longitude": sample.x,
            "area": size / 10000,
            "area_unit": "ha",
            "synthetic": payload.synthetic,
            "territory_id": territory_id,
            "registry": True,
        }
        prior_record = self.db.get(WorkspaceRecord, ident) if ident else None
        encrypted = prior_record.data.get("private_registry") if prior_record else None
        private = json.loads(cipher().decrypt(encrypted.encode())) if encrypted else {}
        for key in ("location", "notes", "observation"):
            if getattr(payload, key) is not None:
                private[key] = getattr(payload, key)
        if private:
            data["private_registry"] = encrypt(private)
        if not row:
            record = WorkspaceRecord(
                office_id=self.principal.office_id, kind="plot", data=data, created_by=self.principal.user_id
            )
            self.db.add(record)
            self.db.flush()
            row = RegisteredPlot(
                id=record.id,
                office_id=self.principal.office_id,
                territory_id=territory_id,
                request_key=payload.request_key,
                request_digest=request_digest,
            )
            self.db.add(row)
        else:
            record = self.db.get(WorkspaceRecord, ident)
            record.data, record.revision = data, record.revision + 1
            row.revision += 1
        row.boundary, row.area_m2, row.centroid, row.sampling_point = (
            payload.geometry,
            size,
            point(geometry.centroid),
            point(sample),
        )
        row.overlaps, row.status = overlaps, "review-required" if overlaps else "registered"
        self.db.flush()
        for link in self.db.scalars(
            select(FarmerPlot).where(FarmerPlot.plot_id == row.id, FarmerPlot.ends_at.is_(None))
        ):
            link.ends_at = datetime.now(UTC)
        for farmer_id in payload.farmer_ids:
            self.db.add(FarmerPlot(plot_id=row.id, farmer_id=farmer_id, role=payload.association_role))
        if payload.season:
            self.db.add(
                CropSeason(
                    office_id=self.principal.office_id, plot_id=row.id, data=payload.season.model_dump(mode="json")
                )
            )
        self.commit(
            row.id,
            "plot_updated" if ident else "plot_registered",
            territory_id=territory_id,
            revision=row.revision,
            overlap_review=bool(overlaps),
        )
        return self.plot_view(row, details=True)

    def summary(self, territory_id):
        territory = require_territory(self.db, self.principal, territory_id)
        return {
            "territory": self.territory_view(territory),
            "farmers": self.db.scalar(
                select(func.count()).select_from(Farmer).where(Farmer.territory_id == territory_id)
            ),
            "plots": self.db.scalar(
                select(func.count()).select_from(RegisteredPlot).where(RegisteredPlot.territory_id == territory_id)
            ),
            "area_m2": self.db.scalar(
                select(func.coalesce(func.sum(RegisteredPlot.area_m2), 0)).where(
                    RegisteredPlot.territory_id == territory_id
                )
            ),
        }

    def history(self, plot_id, limit=25, offset=0):
        authorized_plots(self.db, self.principal, [plot_id])
        indexed = ConnectorJob.id.in_(select(PlotRun.job_id).where(PlotRun.plot_id == plot_id))
        if self.db.bind.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB

            historical = cast(ConnectorJob.request, JSONB).op("->")("plot_ids").contains([plot_id])
        else:
            historical = cast(ConnectorJob.request["plot_ids"], Text).contains('"' + plot_id + '"', autoescape=True)
        query = (
            select(ConnectorJob)
            .where(
                ConnectorJob.office_id == self.principal.office_id,
                ConnectorJob.kind == "skill_run",
                or_(indexed, historical),
            )
            .order_by(ConnectorJob.created_at.desc())
        )
        rows, meta = page(self.db, query, limit, offset)
        from src.integrations.jobs import job_view

        return {"items": [job_view(self.owned(ConnectorJob, r.id)) for r in rows], **meta}
