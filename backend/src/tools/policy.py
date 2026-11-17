"""Identity and geography are obtained from application records, never model declarations."""

import math
from sqlalchemy import select
from src.db.models.user import User
from src.db.models.workspace import Membership, WorkspaceRecord
from src.integrations.contracts import ConnectorError, Principal

ROLES = {
    "administrator": "office_admin",
    "officer": "extension_officer",
    "office_admin": "office_admin",
    "extension_officer": "extension_officer",
    "viewer": "viewer",
}


def principal_for(db, user_id):
    user = db.get(User, user_id)
    member = db.scalar(select(Membership).where(Membership.user_id == user_id))
    if not user or not user.is_active or not member or member.role not in ROLES:
        raise ConnectorError("POLICY_DENIED", "An active office membership is required")
    return Principal(user_id, member.office_id, ROLES[member.role])


def require_admin(principal):
    if principal.role != "office_admin":
        raise ConnectorError("POLICY_DENIED", "Office administrator permission is required")


def authorized_plots(db, principal, plot_ids):
    if len(set(plot_ids)) != len(plot_ids) or len(plot_ids) > 5:
        raise ConnectorError("INPUT_VALIDATION_FAILED", "Use at most five distinct authorized plot IDs")
    output = []
    for plot_id in plot_ids:
        plot = db.get(WorkspaceRecord, plot_id)
        if not plot or plot.office_id != principal.office_id or plot.kind != "plot":
            raise ConnectorError("POLICY_DENIED", "Plot is outside the authenticated office")
        household = db.get(WorkspaceRecord, plot.data["household_id"])
        if not household or household.office_id != principal.office_id:
            raise ConnectorError("POLICY_DENIED", "Plot household scope is invalid")
        output.append(
            {
                "id": plot.id,
                "latitude": plot.data["latitude"],
                "longitude": plot.data["longitude"],
                "synthetic": household.data.get("synthetic") is True,
            }
        )
    return output


def bind_and_check_arguments(spec, arguments, plots, *, image_asset_id=None):
    result = dict(arguments)
    for name, binding in spec.get("context_bindings", {}).items():
        if name in arguments:
            raise ConnectorError("INPUT_VALIDATION_FAILED", "A server-bound field cannot be supplied by the caller")
        if binding == "run.image_asset_id":
            if not image_asset_id:
                raise ConnectorError("INPUT_VALIDATION_FAILED", "This skill requires an uploaded image asset")
            result[name] = image_asset_id
            continue
        if len(plots) != 1:
            raise ConnectorError("POLICY_DENIED", "This operation requires exactly one authorized plot")
        result[name] = plots[0][binding.split(".")[1]]
    from src.integrations.schema_translation import validate

    validate(result, spec["input_json_schema"])
    # A coordinate is not authorized just because it is in latitude/longitude range.
    pairs = [
        (result[a], result[b]) for a, b in (("latitude", "longitude"), ("lat", "lon")) if a in result and b in result
    ]
    for lat, lon in pairs:
        if (
            not isinstance(lat, (int, float))
            or isinstance(lat, bool)
            or not math.isfinite(lat)
            or not isinstance(lon, (int, float))
            or isinstance(lon, bool)
            or not math.isfinite(lon)
            or not any(abs(lat - plot["latitude"]) < 1e-7 and abs(lon - plot["longitude"]) < 1e-7 for plot in plots)
        ):
            raise ConnectorError("POLICY_DENIED", "Coordinates must resolve to an authorized plot")
    if pairs and "plot_coordinates" not in spec.get("required_data_classes", []):
        raise ConnectorError("POLICY_DENIED", "Tool lacks a reviewed coordinate-egress classification")
    return result
