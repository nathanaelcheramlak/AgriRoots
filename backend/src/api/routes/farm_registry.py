"""Persistent registry contracts; all identifiers are resolved against authenticated scope."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from src.api.routes.integrations import service
from src.db.models.farm_registry import CropSeason, FarmObservation, TerritoryAssignment
from src.db.models.workspace import Membership
from src.registry.schemas import (
    AssignmentInput,
    FarmerEdit,
    FarmerInput,
    FarmRegistration,
    ObservationInput,
    PlotEdit,
    PlotInput,
    Review,
    SeasonInput,
    TerritoryEdit,
    TerritoryInput,
)
from src.registry.service import FarmRegistry, page
from src.tools.policy import require_admin

router = APIRouter(prefix="/api/v1/registry", tags=["Territory and farm registry"])


_service_dependency = Depends(service)


def registry(s=_service_dependency):
    return FarmRegistry(s.db, s.principal)


_registry_dependency = Depends(registry)


@router.get("/territories")
def territories(limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0), s=_registry_dependency):
    return s.territories(limit, offset)


@router.post("/territory-proposals", status_code=201)
def propose(payload: TerritoryInput, s=_registry_dependency):
    return s.propose(payload)


@router.post("/territories/{ident}/review")
def review(ident: str, payload: Review, s=_registry_dependency):
    return s.review(ident, payload)


@router.patch("/territories/{ident}")
def edit_territory(ident: str, payload: TerritoryEdit, s=_registry_dependency):
    return s.edit_territory(ident, payload)


@router.get("/members")
def members(s=_registry_dependency):
    require_admin(s.principal)
    return {
        "items": [
            {"user_id": r.user_id, "role": r.role}
            for r in s.db.scalars(select(Membership).where(Membership.office_id == s.principal.office_id))
        ]
    }


@router.get("/territories/{ident}/assignments")
def assignments(ident: str, s=_registry_dependency):
    require_admin(s.principal)
    from src.db.models.farm_registry import Territory

    s.owned(Territory, ident)
    return {
        "items": [
            {
                "id": r.id,
                "user_id": r.user_id,
                "role": r.role,
                "starts_at": r.starts_at,
                "ends_at": r.ends_at,
                "revoked": r.revoked,
                "revision": r.revision,
            }
            for r in s.db.scalars(select(TerritoryAssignment).where(TerritoryAssignment.territory_id == ident))
        ]
    }


@router.post("/territories/{ident}/assignments", status_code=201)
def assign(ident: str, payload: AssignmentInput, s=_registry_dependency):
    return s.assign(ident, payload)


@router.delete("/assignments/{ident}")
def revoke(ident: str, expected_revision: int = Query(ge=1), s=_registry_dependency):
    return s.revoke(ident, expected_revision)


@router.get("/territories/{ident}/summary")
def summary(ident: str, s=_registry_dependency):
    return s.summary(ident)


@router.get("/farmers")
def farmers(
    territory_id: str | None = None,
    search: str = Query("", max_length=100),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    s=_registry_dependency,
):
    return s.farmers(territory_id, search, limit, offset)


@router.post("/farmers", status_code=201)
def create_farmer(payload: FarmerInput, s=_registry_dependency):
    return s.save_farmer(payload)


@router.get("/farmers/{ident}")
def farmer(ident: str, include_private: bool = False, s=_registry_dependency):
    result = s.farmer_view(s.farmer(ident), private=include_private)
    if include_private:
        s.commit(ident, "farmer_private_read")
    return result


@router.patch("/farmers/{ident}")
def edit_farmer(ident: str, payload: FarmerEdit, s=_registry_dependency):
    return s.save_farmer(payload, ident)


@router.get("/plots")
def plots(
    territory_id: str | None = None,
    bbox: str | None = Query(None, max_length=150),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    s=_registry_dependency,
):
    values = None
    if bbox:
        try:
            values = [float(v) for v in bbox.split(",")]
        except ValueError:
            from src.registry.geometry import invalid

            invalid("Invalid bounding box")
    return s.plots(territory_id, values, limit=limit, offset=offset)


@router.post("/territories/{ident}/plots", status_code=201)
def register_plot(ident: str, payload: PlotInput, s=_registry_dependency):
    return s.save_plot(ident, payload)


@router.post("/territories/{ident}/farm-registrations", status_code=201)
def register_farm(ident: str, payload: FarmRegistration, s=_registry_dependency):
    from sqlalchemy.exc import IntegrityError

    from src.integrations.contracts import ConnectorError

    try:
        return s.register_farm(ident, payload)
    except IntegrityError:
        s.db.rollback()
        raise ConnectorError(
            "VERSION_CONFLICT", "A matching record already exists. Reload before saving again."
        ) from None
    except Exception:
        s.db.rollback()
        raise


@router.get("/plots/{ident}")
def plot(ident: str, s=_registry_dependency):
    return s.plot_view(s.plot(ident), details=True)


@router.patch("/plots/{ident}")
def edit_plot(ident: str, payload: PlotEdit, s=_registry_dependency):
    row = s.plot(ident, write=True)
    return s.save_plot(row.territory_id, payload, ident)


@router.get("/plots/{ident}/crop-seasons")
def seasons(ident: str, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), s=_registry_dependency):
    s.plot(ident)
    rows, meta = page(
        s.db,
        select(CropSeason).where(CropSeason.plot_id == ident).order_by(CropSeason.created_at.desc()),
        limit,
        offset,
    )
    return {"items": [{"id": r.id, "revision": r.revision, **r.data} for r in rows], **meta}


@router.post("/plots/{ident}/crop-seasons", status_code=201)
def add_season(ident: str, payload: SeasonInput, s=_registry_dependency):
    s.plot(ident, write=True, lock=True)
    row = CropSeason(office_id=s.principal.office_id, plot_id=ident, data=payload.model_dump(mode="json"))
    s.db.add(row)
    s.db.flush()
    s.commit(ident, "crop_season_recorded", season_id=row.id)
    return {"id": row.id, "revision": row.revision, **row.data}


@router.get("/plots/{ident}/observations")
def observations(
    ident: str, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), s=_registry_dependency
):
    s.plot(ident)
    rows, meta = page(
        s.db,
        select(FarmObservation).where(FarmObservation.plot_id == ident).order_by(FarmObservation.created_at.desc()),
        limit,
        offset,
    )
    return {
        "items": [{"id": r.id, "provenance": r.provenance, "observed_at": r.observed_at, **r.data} for r in rows],
        **meta,
    }


@router.post("/plots/{ident}/observations", status_code=201)
def add_observation(ident: str, payload: ObservationInput, s=_registry_dependency):
    s.plot(ident, write=True)
    row = FarmObservation(
        office_id=s.principal.office_id,
        plot_id=ident,
        provenance=payload.provenance,
        observed_at=payload.observed_at,
        data=payload.model_dump(exclude={"provenance", "observed_at"}),
        created_by=s.principal.user_id,
    )
    s.db.add(row)
    s.db.flush()
    s.commit(ident, "farm_observation_recorded", observation_id=row.id)
    return {"id": row.id, "provenance": row.provenance, "observed_at": row.observed_at, **row.data}


@router.get("/plots/{ident}/investigations")
def history(ident: str, limit: int = Query(25, ge=1, le=100), offset: int = Query(0, ge=0), s=_registry_dependency):
    return s.history(ident, limit, offset)
