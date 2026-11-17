"""Operator helper for the existing local Compose office; no account creation.

Credentials are read from explicit private files and transferred on stdin only.
The default registers adapters without network calls. --live authorizes bounded
provider checks, never Kindwise credit use or a model call.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.skills.verified_pack import PROVIDERS

CONTEXT = """
import json
from sqlalchemy import select
from src.db.session import SessionLocal
from src.db.models.workspace import Membership, WorkspaceRecord
from src.db.models.user import User
from src.services.workspace_service import WorkspaceService
from src.api.schemas.workspace import RecordInput
from src.config.settings import get_settings
with SessionLocal() as db:
    members=list(db.scalars(select(Membership).where(Membership.role.in_(['administrator','office_admin']))))
    if len(members)!=1: raise ValueError('Select a single existing local administrator before validation')
    actor=members[0]
    plots=list(db.scalars(select(WorkspaceRecord).where(WorkspaceRecord.office_id==actor.office_id, WorkspaceRecord.kind=='plot')))
    adama=next(p for p in plots if abs(p.data['latitude']-8.54)<.0001 and abs(p.data['longitude']-39.27)<.0001)
    household=db.get(WorkspaceRecord,adama.data['household_id'])
    if not household.data.get('synthetic'): raise ValueError('Validation requires explicitly synthetic context')
    addis=next((p for p in plots if p.data['name']=='SYNTHETIC Addis route validation point'),None)
    if addis is None:
        addis=WorkspaceService(db,db.get(User,actor.user_id)).save_record(actor.office_id,RecordInput(kind='plot',data={
            'name':'SYNTHETIC Addis route validation point','household_id':household.id,'latitude':9.03,'longitude':38.74,
            'area':1,'area_unit':'ha','agroclimatic_zone':'Synthetic routing context only'}))
    print(json.dumps({'principal_id':actor.user_id,'plot_id':adama.id,'route_plot_id':addis.id,
                     'model_key_present':bool(get_settings().gemini_api_key)}))
"""


def docker(container, code, payload=None):
    result = subprocess.run(
        ["docker", "exec", "-i", container, "python", "-c", code],
        input=json.dumps(payload) if payload is not None else "",
        capture_output=True,
        check=False,
        text=True,
        cwd=ROOT,
    )
    if result.returncode:
        raise RuntimeError("Local container operation failed; secret-bearing input/output was withheld")
    try:
        return json.loads(result.stdout)
    except ValueError:
        raise RuntimeError("Local container returned an invalid setup result") from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", default="agrilo-connectors-test-api-1")
    parser.add_argument("--provider-env", type=Path, required=True)
    parser.add_argument("--earth-engine-credentials", type=Path)
    parser.add_argument("--providers", nargs="+", choices=list(PROVIDERS))
    parser.add_argument("--live", action="store_true")
    args = parser.parse_args()
    identity = docker(args.container, CONTEXT)
    values = dotenv_values(args.provider_env)
    credentials = {}
    if values.get("ISDA_USERNAME") and values.get("ISDA_PASSWORD"):
        credentials["isda_soil"] = {"username": values["ISDA_USERNAME"], "password": values["ISDA_PASSWORD"]}
    for provider, name in {
        "eppo": "EPPO_API_TOKEN",
        "wfp_prices": "HAPI_APP_IDENTIFIER",
        "kindwise": "KINDWISE_CROP_HEALTH_API_KEY",
        "openrouteservice": "OPENROUTESERVICE_API_KEY",
    }.items():
        if values.get(name):
            credentials[provider] = values[name]
    if args.earth_engine_credentials:
        from ee.oauth import CLIENT_ID, CLIENT_SECRET

        stored = json.loads(args.earth_engine_credentials.read_text(encoding="utf-8"))
        credentials["google_earth_engine"] = {
            "project": values["EE_PROJECT"],
            "refresh_token": stored["refresh_token"],
            "client_id": stored.get("client_id", CLIENT_ID),
            "client_secret": stored.get("client_secret", CLIENT_SECRET),
        }
    plot = identity["plot_id"]
    historical = {"start": "2025-07-01", "end": "2025-07-07"}
    samples = {p: {"plot_ids": [plot], "arguments": {}} for p in PROVIDERS if p != "kindwise"}
    for p in ("nasa_power", "chirps", "wfp_prices", "fao_asis"):
        samples[p]["arguments"] = dict(historical)
    samples["chirps"]["arguments"]["end"] = "2025-07-01"
    samples["google_earth_engine"]["arguments"] = {"start": "2025-01-01", "end": "2025-01-31"}
    samples["fao_wapor"]["arguments"] = {"start": "2026-10-01", "end": "2026-10-10"}
    samples["eppo"] = {"plot_ids": [], "arguments": {"eppo_code": "LAPHFR"}}
    samples["openrouteservice"] = {
        "plot_ids": [identity["route_plot_id"], plot],
        "arguments": {"from_plot_id": identity["route_plot_id"], "to_plot_id": plot},
    }
    selected = args.providers or list(PROVIDERS)
    request = {
        "principal_id": identity["principal_id"],
        "providers": selected,
        "credentials": {p: c for p, c in credentials.items() if p in selected},
        "live_test": args.live,
        "samples": samples,
        "authorize_credit_use": False,
    }
    code = """import json,asyncio,sys
from src.config.settings import get_settings
get_settings().live_tests_enabled=True
sys.path.insert(0,'/app/scripts')
from sync_verified_skills import run
try:
 print(json.dumps(asyncio.run(run(json.load(sys.stdin)))))
except Exception as error:
 import traceback
 print(json.dumps({"setup_error_type":type(error).__name__,"frames":[[f.name,f.lineno] for f in traceback.extract_tb(error.__traceback__)]}))"""
    result = docker(args.container, code, request)
    if "setup_error_type" in result:
        raise RuntimeError(json.dumps(result))
    result["model_key_present"] = identity["model_key_present"]
    result["live_model_test"] = "NOT_RUN" if identity["model_key_present"] else "BLOCKED_MISSING_MODEL_KEY"
    result["kindwise_requests"] = 0
    for row in result["providers"]:
        if row["provider_id"] == "kindwise":
            row["backend_live_test"] = "NOT_RUN_CREDIT_AUTHORIZATION_REQUIRED"
    path = ROOT / "reports/verified_skill_activation.json"
    if path.exists():
        previous = json.loads(path.read_text(encoding="utf-8"))
        archive = path.with_name("verified_skill_activation.previous." + str(__import__("time").time_ns()) + ".json")
        archive.write_text(json.dumps(previous, indent=2), encoding="utf-8")
        retained = {r["provider_id"]: r for r in previous.get("providers", [])}
        retained.update({r["provider_id"]: r for r in result["providers"]})
        result["providers"] = list(retained.values())
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "providers": [
                    {k: r[k] for k in ("provider_id", "backend_live_test", "enabled", "error") if k in r}
                    for r in result["providers"]
                ],
                "model_test": result["live_model_test"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
