"""Assignment predicates shared by HTTP, job/evidence reads and the controlled executor."""

from datetime import UTC, datetime

from sqlalchemy import and_, or_, select

from src.db.models.farm_registry import RegisteredPlot, Territory, TerritoryAssignment
from src.integrations.contracts import ConnectorError


def territory_scope(principal, *, write=False):
    clauses = [Territory.office_id == principal.office_id, Territory.status == "assigned"]
    if principal.role != "office_admin":
        clock = datetime.now(UTC)
        assignments = select(TerritoryAssignment.territory_id).where(
            TerritoryAssignment.office_id == principal.office_id,
            TerritoryAssignment.user_id == principal.user_id,
            TerritoryAssignment.revoked.is_(False),
            TerritoryAssignment.starts_at <= clock,
            or_(TerritoryAssignment.ends_at.is_(None), TerritoryAssignment.ends_at > clock),
        )
        if write:
            assignments = assignments.where(TerritoryAssignment.role == "manager")
        clauses.append(Territory.id.in_(assignments))
    if write and principal.role == "viewer":
        clauses.append(False)
    return and_(*clauses)


def require_territory(db, principal, territory_id, *, write=False, lock=False):
    query = select(Territory).where(Territory.id == territory_id, territory_scope(principal, write=write))
    row = db.scalar(query.with_for_update() if lock else query)
    if not row:
        raise ConnectorError("POLICY_DENIED", "An active office territory assignment is required")
    return row


def guard_plot(db, principal, plot_id, *, write=False):
    row = db.get(RegisteredPlot, plot_id)
    if row:
        if row.office_id != principal.office_id:
            raise ConnectorError("POLICY_DENIED", "Plot is outside the authenticated office")
        require_territory(db, principal, row.territory_id, write=write)
    return row


def guard_record(db, principal, row):
    """Also protects legacy evidence envelopes referencing a newly registered plot."""
    if row.data.get("territory_id"):
        require_territory(db, principal, row.data["territory_id"])
    ids = [row.id] if row.kind == "plot" else []
    ids += [row.data["plot_id"]] if row.data.get("plot_id") else []
    ids += row.data.get("permitted_plot_ids", [])
    for plot_id in set(ids):
        guard_plot(db, principal, plot_id)
