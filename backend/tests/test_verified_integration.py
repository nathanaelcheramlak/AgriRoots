"""Contract, real executor and private-image tests. All upstream responses here are fixtures."""

# ruff: noqa: F401, F811 -- pytest imports fixtures by name
import asyncio
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import numpy as np
import pytest
from rasterio.io import MemoryFile
from rasterio.transform import from_origin
from sqlalchemy import func, select

from src.config.settings import get_settings
from src.db.models.connectors import Integration, RegisteredSkill, RegisteredTool, ToolInvocation, ToolVersion
from src.db.models.image_asset import DiagnosisReceipt, ImageAsset
from src.db.session import SessionLocal
from src.integrations.contracts import ConnectorError, ExecutionContext, Principal, SkillRunRequest
from src.providers import agriculture, environment, references
from src.providers.factory import HANDLERS, template
from src.providers.raster_access import raster_pixel
from src.skills.plugins import PackManifest
from src.skills.verified_pack import PROVIDERS, verified_pack
from src.tools.policy import principal_for
from tests.test_connectors_rest import register, runtime, test_and_publish
from tests.test_workspace import office


@pytest.fixture(autouse=True)
def private_test_storage(monkeypatch, tmp_path):
    from cryptography.fernet import Fernet

    monkeypatch.setattr(get_settings(), "connector_artifact_root", str(tmp_path / "private"))
    monkeypatch.setattr(get_settings(), "secret_encryption_key", Fernet.generate_key().decode())


@pytest.fixture
def verified_http(monkeypatch):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from threading import Thread

    calls = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def dispatch(self):
            content = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            calls.append({"path": self.path, "content": content})
            if "/taxons/taxon/" in self.path:
                payload = [{"fullname": "Spodoptera frugiperda", "preferred": True, "lang_iso": "la"}]
                body, media = json.dumps(payload).encode(), "application/json"
            elif self.path.endswith(".tif"):
                body, media = tiff(), "image/tiff"
            elif "/identification" in self.path:
                body = json.dumps(
                    {
                        "result": {
                            "crop": {"suggestions": [{"name": "potato", "probability": 0.7}]},
                            "disease": {"suggestions": [{"name": "late blight", "probability": 0.8}]},
                        }
                    }
                ).encode()
                media = "application/json"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", media)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        do_GET = dispatch
        do_POST = dispatch

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    origin = f"http://127.0.0.1:{server.server_port}"
    monkeypatch.setattr(get_settings(), "connector_fixture_origins", [origin])
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield origin, calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


@pytest.mark.parametrize("handler,args", [("eppo.names", {"eppo_code": "LAPHFR"}), ("gaez.maize_suitability", {})])
def test_new_handlers_use_real_executor_transport_and_persist_fixture_evidence(
    client, office, verified_http, monkeypatch, handler, args
):
    origin, calls = verified_http
    monkeypatch.setitem(HANDLERS, handler, {**HANDLERS[handler], "base_url": origin})
    provider = template(handler)
    headers = office["users"]["admin"]["headers"]
    response = client.post("/api/v1/integrations", headers=headers, json=provider["connection"])
    assert response.status_code == 201, response.text
    connection = response.json()
    if handler == "eppo.names":
        response = client.put(
            f"/api/v1/integrations/{connection['id']}/credential",
            headers=headers,
            json={"value": "fixture-secret", "principal_scope": "fixture-account"},
        )
        assert response.status_code == 200
    tool = register(client, office, connection, provider["operations"][0])
    checked = test_and_publish(client, office, connection, tool, args)
    assert checked["status"] == "succeeded", checked
    result = runtime(office, tool, args)
    assert result["classification"] == "fixture" and result["evidence_ids"] and len(calls) == 2
    assert "fixture-secret" not in json.dumps(result)


def test_private_image_flows_through_exact_version_test_and_executor(client, office, verified_http, monkeypatch):
    from src.integrations.jobs import process_job
    from tests.test_connectors_rest import exact

    origin, calls = verified_http
    handler = "kindwise.diagnosis"
    monkeypatch.setitem(HANDLERS, handler, {**HANDLERS[handler], "base_url": origin})
    provider = template(handler)
    headers = office["users"]["admin"]["headers"]
    connection = client.post("/api/v1/integrations", headers=headers, json=provider["connection"]).json()
    client.put(
        f"/api/v1/integrations/{connection['id']}/credential",
        headers=headers,
        json={"value": "fixture-key", "principal_scope": "fixture-account"},
    )
    tool = register(client, office, connection, provider["operations"][0])
    ident = upload(client, office)
    response = client.post(
        f"/api/v1/integrations/{connection['id']}/tools/{tool['id']}/test",
        headers=headers,
        json={
            **exact(tool),
            "arguments": {"image_asset_id": ident},
            "plot_ids": [],
            "authorize_network": True,
            "authorize_credit_use": True,
            "request_key": "fixture-image-request",
        },
    )
    assert response.status_code == 202, response.text
    asyncio.run(process_job(response.json()["id"]))
    result = client.get(response.json()["status_url"], headers=headers).json()
    assert result["status"] == "succeeded", result
    assert result["result"]["evidence_ids"] and len(calls) == 1
    assert json.loads(calls[0]["content"])["images"]


def actor(o):
    with SessionLocal() as db:
        return principal_for(db, o["users"]["admin"]["id"])


def context(o):
    return ExecutionContext(
        actor(o),
        "fixture-budget",
        str(uuid4()),
        plots=[{"id": o["plot"]["id"], "latitude": 9.03, "longitude": 38.74, "synthetic": True}],
    )


def png():
    from PIL import Image

    out = BytesIO()
    Image.new("RGB", (32, 32), "green").save(out, format="PNG")
    return out.getvalue()


def upload(client, o):
    response = client.post(
        "/api/v1/image-assets",
        headers=o["users"]["admin"]["headers"],
        files={"image": ("private.png", png(), "image/png")},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_complete_pack_validates_and_is_disabled_on_install(client, office):
    pack = PackManifest.model_validate(verified_pack())
    assert len(pack.connections) == len(PROVIDERS) == 14 and len(pack.skills) == 15
    headers = office["users"]["admin"]["headers"]
    response = client.post("/api/v1/plugins", headers=headers, json=pack.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    registered = response.json()
    response = client.post(
        f"/api/v1/plugins/{registered['id']}/install", headers=headers, json={"digest": registered["digest"]}
    )
    assert response.status_code == 200, response.text
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(RegisteredTool)) == 14
        assert all(not x.enabled for x in db.scalars(select(Integration)))


def test_registry_reconciliation_is_idempotent_and_reuses_existing_provider(client, office, monkeypatch):
    from cryptography.fernet import Fernet

    monkeypatch.setattr(get_settings(), "secret_encryption_key", Fernet.generate_key().decode())
    path = Path(__file__).resolve().parents[1] / "scripts/sync_verified_skills.py"
    spec = importlib.util.spec_from_file_location("verified_sync", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    first = module.reconcile(actor(office), "eppo", "fixture-key")
    second = module.reconcile(actor(office), "eppo", "fixture-key")
    assert first["connection_id"] == second["connection_id"] and first["tool_version_id"] == second["tool_version_id"]
    with SessionLocal() as db:
        assert db.scalar(select(func.count()).select_from(ToolVersion)) == 1


@pytest.mark.parametrize(
    "content,media", [(b"not an image", "image/png"), (b"x" * (10 * 1024**2 + 1), "image/png"), (png(), "text/plain")]
)
def test_bad_image_is_rejected(client, office, content, media):
    result = client.post(
        "/api/v1/image-assets",
        headers=office["users"]["admin"]["headers"],
        files={"image": ("test.png", content, media)},
    )
    assert result.status_code == 422, result.text


def test_private_image_has_no_public_path_and_cannot_cross_offices(client, office):
    ident = upload(client, office)
    from PIL import Image

    from src.services.image_asset_service import asset_path, owned_image

    with SessionLocal() as db:
        row = owned_image(db, actor(office), ident)
        with Image.open(asset_path(row)) as image:
            assert not image.getexif() and image.format == "JPEG"
        stranger = Principal(actor(office).user_id, str(uuid4()), "office_admin")
        with pytest.raises(ConnectorError):
            owned_image(db, stranger, ident)


def test_diagnosis_receipt_prevents_repeat_credit_use(client, office):
    ident = upload(client, office)
    ctx = context(office)
    ctx.authorize_credit_use = True
    data = {
        "result": {
            "crop": {"suggestions": [{"name": "potato", "probability": 0.7}]},
            "disease": {"suggestions": [{"name": "late blight", "probability": 0.8}]},
        }
    }
    http = SimpleNamespace(json=AsyncMock(return_value=data))
    result = asyncio.run(
        references.kindwise(http, "https://crop.kindwise.com", {"image_asset_id": ident}, "fixture-key", ctx)
    )
    assert result.data["crop_candidates"][0]["name"] == "potato"
    with pytest.raises(ConnectorError) as error:
        asyncio.run(
            references.kindwise(http, "https://crop.kindwise.com", {"image_asset_id": ident}, "fixture-key", ctx)
        )
    assert error.value.code == "AMBIGUOUS_OUTCOME" and http.json.await_count == 1


def test_ambiguous_image_submission_is_not_retried(client, office):
    ident = upload(client, office)
    ctx = context(office)
    ctx.authorize_credit_use = True
    http = SimpleNamespace(json=AsyncMock(side_effect=ConnectorError("TIMEOUT", "fixture timeout")))
    with pytest.raises(ConnectorError):
        asyncio.run(
            references.kindwise(http, "https://crop.kindwise.com", {"image_asset_id": ident}, "fixture-key", ctx)
        )
    with pytest.raises(ConnectorError) as error:
        asyncio.run(
            references.kindwise(http, "https://crop.kindwise.com", {"image_asset_id": ident}, "fixture-key", ctx)
        )
    assert error.value.code == "AMBIGUOUS_OUTCOME" and http.json.await_count == 1


def test_credit_denial_sends_no_image(client, office):
    ctx = context(office)
    http = SimpleNamespace(json=AsyncMock())
    with pytest.raises(ConnectorError):
        asyncio.run(
            references.kindwise(http, "https://crop.kindwise.com", {"image_asset_id": str(uuid4())}, "fixture-key", ctx)
        )
    http.json.assert_not_awaited()


def test_eppo_validation_and_schema():
    http = SimpleNamespace(
        json=AsyncMock(return_value=[{"fullname": "Spodoptera frugiperda", "preferred": True, "lang_iso": "la"}])
    )
    result = asyncio.run(references.eppo(http, "https://api.eppo.int", {"eppo_code": "LAPHFR"}, "fixture-key", None))
    assert result.data["eppo_code"] == "LAPHFR" and "occurrence" in result.limitations[0]
    http.json = AsyncMock(return_value=[{"fullname": "bad"}])
    with pytest.raises(ConnectorError):
        asyncio.run(references.eppo(http, "https://api.eppo.int", {"eppo_code": "LAPHFR"}, "fixture-key", None))


def test_hapi_retains_price_metadata_and_rejects_mismatched_dates():
    row = {
        "location_code": "ETH",
        "price": 100,
        "commodity_name": "Maize",
        "market_name": "Adama",
        "currency_code": "ETB",
        "unit": "KG",
        "reference_period_start": "2025-07-01",
        "reference_period_end": "2025-07-31",
        "resource_hdx_id": "fixture-source",
        "price_type": "Retail",
        "price_flag": "actual",
    }
    http = SimpleNamespace(json=AsyncMock(return_value={"data": [row]}))
    args = {"start": "2025-07-01", "end": "2025-07-07"}
    result = asyncio.run(references.hapi(http, "https://hapi.humdata.org", args, "fixture-identifier", None))
    assert result.data["records"][0]["unit"] == "KG" and "fixture-identifier" not in json.dumps(result.data)
    row["reference_period_start"] = "2024-01-01"
    row["reference_period_end"] = "2024-01-31"
    with pytest.raises(ConnectorError):
        asyncio.run(references.hapi(http, "https://hapi.humdata.org", args, "fixture-identifier", None))


def test_route_uses_only_authorized_points_and_checks_returned_endpoints():
    plots = [{"id": "from", "longitude": 38.74, "latitude": 9.03}, {"id": "to", "longitude": 39.27, "latitude": 8.54}]
    response = {
        "features": [
            {
                "properties": {"summary": {"distance": 1000, "duration": 90}},
                "geometry": {"type": "LineString", "coordinates": [[38.74, 9.03], [39.27, 8.54]]},
            }
        ]
    }
    http = SimpleNamespace(json=AsyncMock(return_value=response))
    ctx = SimpleNamespace(plots=plots)
    result = asyncio.run(
        references.route(
            http, "https://api.heigit.org", {"from_plot_id": "from", "to_plot_id": "to"}, "fixture-key", ctx
        )
    )
    assert result.data["distance"] == 1000
    with pytest.raises(ConnectorError):
        asyncio.run(
            references.route(
                http, "https://api.heigit.org", {"from_plot_id": "from", "to_plot_id": "outside"}, "fixture-key", ctx
            )
        )
    assert http.json.await_count == 1


def tiff():
    with MemoryFile() as mem:
        with mem.open(
            driver="GTiff",
            height=32,
            width=32,
            count=1,
            dtype="int16",
            crs="EPSG:4326",
            transform=from_origin(38, 10, 1 / 12, 1 / 12),
            nodata=-9999,
        ) as dst:
            dst.write(np.full((1, 32, 32), 7515, dtype="int16"))
        return mem.read()


def test_raster_uses_controlled_range_requests_not_gdal_network():
    payload = tiff()

    async def raw(method, url, headers=None):
        start, last = map(int, headers["Range"][6:].split("-"))
        last = min(last, len(payload) - 1)
        return httpx.Response(
            206, content=payload[start : last + 1], headers={"Content-Range": f"bytes {start}-{last}/{len(payload)}"}
        )

    http = SimpleNamespace(raw=AsyncMock(side_effect=raw))
    result = asyncio.run(raster_pixel(http, "https://storage.googleapis.com/fixture.tif", 38.74, 9.03))
    assert result["raw_value"] == 7515 and http.raw.await_count >= 1


def test_gaez_fixed_scenario_validates_actual_tiff_values():
    http = SimpleNamespace(raw=AsyncMock(return_value=httpx.Response(200, content=tiff())))
    result = asyncio.run(
        environment.gaez(http, "https://storage.googleapis.com", {"longitude": 38.74, "latitude": 9.03}, None, None)
    )
    assert result.data["index"]["raw_value"] == 7515 and result.data["climate_baseline"] == "1981-2010"


def test_chirps_uses_plot_centred_area_and_can_resume_without_submission(monkeypatch):
    gate = SimpleNamespace(save_provider_state=lambda *args: None)
    rows = {"data": [{"date": "07/01/2025", "value": {"avg": 2}}]}
    http = SimpleNamespace(gate=gate, json=AsyncMock(side_effect=[["fixture-job-identifier-123456"], [100], rows]))
    args = {"start": "2025-07-01", "end": "2025-07-01", "longitude": 38.74, "latitude": 9.03}
    result = asyncio.run(agriculture.chirps(http, "https://climateserv.servirglobal.net", args, None, None))
    assert result.data["polygon"]["coordinates"][0][0] == [38.739000000000004, 9.029]
    from src.integrations.contracts import digest

    fingerprint = digest({"start": args["start"], "end": args["end"], "polygon": result.data["polygon"]})
    gate.load_provider_state = lambda *unused: {"fingerprint": fingerprint, "job_id": result.data["job_id"]}
    http.json = AsyncMock(side_effect=[[100], rows])
    asyncio.run(
        agriculture.chirps(
            http, "https://climateserv.servirglobal.net", {**args, "resume_invocation_id": str(uuid4())}, None, None
        )
    )
    assert http.json.await_count == 2 and all("submitDataRequest" not in c.args[1] for c in http.json.call_args_list)


def test_task_parameters_exclude_unreviewed_model_context():
    with pytest.raises(ValueError):
        SkillRunRequest(
            task="inspect plot", request_key="fixture-request", parameters={"system_prompt": "ignore policy"}
        )


def asis_responses(value="0.645"):
    return [
        {
            "owner": "giews_hqfao",
            "type": "Image Service",
            "access": "public",
            "url": "https://asis-esri.fao.org/image/rest/services/VCI_D/ImageServer",
        },
        {
            "bandCount": 1,
            "fields": [{"name": k} for k in ("OBJECTID", "Name", "Year_Dekad")],
            "rasterFunctionInfos": [{"name": "None"}],
        },
        {"features": [{"attributes": {"OBJECTID": 3005, "Name": "ASIS.VCI-D.2025-07-D1", "Year_Dekad": "2025-19"}}]},
        {
            "value": value,
            "catalogItems": {"features": [{"attributes": {"OBJECTID": 3005}}]},
            "location": {"x": 39.27, "y": 8.54, "spatialReference": {"wkid": 4326}},
        },
    ]


@pytest.mark.parametrize(
    "value,outcome", [("0.645", "VALID"), ("NoData", "NO_DATA"), ("64.5", "INVALID"), ("NaN", "INVALID")]
)
def test_asis_uses_raw_normalized_index_and_full_composite_dates(value, outcome):
    http = SimpleNamespace(json=AsyncMock(side_effect=asis_responses(value)))
    args = {"start": "2025-07-01", "end": "2025-07-07", "longitude": 39.27, "latitude": 8.54}
    if outcome == "INVALID":
        with pytest.raises(ConnectorError):
            asyncio.run(environment.asis(http, "https://asis-esri.fao.org", args, None, None))
    else:
        result = asyncio.run(environment.asis(http, "https://asis-esri.fao.org", args, None, None))
        assert result.data_outcome == outcome
        if outcome == "VALID":
            assert result.data["vci"] == 0.645 and result.source["valid_time_range"]["to"] == "2025-07-10"


def test_wapor_reports_missing_period_without_fabricating_pixel():
    http = SimpleNamespace(json=AsyncMock(return_value={"response": {"items": []}}), raw=AsyncMock())
    result = asyncio.run(
        environment.wapor(
            http,
            "https://data.apps.fao.org",
            {"start": "2025-07-01", "end": "2025-07-07", "longitude": 39.27, "latitude": 8.54},
            None,
            None,
        )
    )
    assert result.data_outcome == "NO_DATA"
    http.raw.assert_not_awaited()


def test_earth_engine_missing_credentials_never_uses_ambient_authentication():
    from src.providers.earth_engine import earth_engine

    http = SimpleNamespace(raw=AsyncMock())
    with pytest.raises(ConnectorError) as error:
        asyncio.run(
            earth_engine(
                http, "https://earthengine.googleapis.com", {"start": "2025-01-01", "end": "2025-01-31"}, None, None
            )
        )
    assert error.value.code == "AUTH_REQUIRED"
    http.raw.assert_not_awaited()


def test_additive_image_migration_preserves_existing_data():
    from sqlalchemy import create_engine, inspect, text

    from src.db.schema_migrations import migrate

    engine = create_engine("sqlite://")
    migrate(engine)
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO offices (id, name) VALUES ('fixture-office', 'Existing')"))
    migrate(engine)
    with engine.connect() as connection:
        assert connection.execute(text("SELECT name FROM offices WHERE id='fixture-office'")).scalar() == "Existing"
        assert connection.execute(text("SELECT max(version) FROM schema_revisions")).scalar() == 5
    assert "connector_image_assets" in inspect(engine).get_table_names()


def test_new_skill_runs_actual_langgraph_with_real_http_fixture_and_cited_evidence(
    client, office, verified_http, monkeypatch
):
    from src.integrations.jobs import process_job

    origin, calls = verified_http
    monkeypatch.setitem(HANDLERS, "eppo.names", {**HANDLERS["eppo.names"], "base_url": origin})
    spec = importlib.util.spec_from_file_location(
        "verified_graph_sync", Path(__file__).resolve().parents[1] / "scripts/sync_verified_skills.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    setup = asyncio.run(
        module.run(
            {
                "principal_id": actor(office).user_id,
                "providers": ["eppo"],
                "credentials": {"eppo": "fixture-key"},
                "live_test": True,
                "samples": {"eppo": {"arguments": {"eppo_code": "LAPHFR"}, "plot_ids": []}},
            }
        )
    )
    assert setup["providers"][0]["enabled"], setup
    skill_id = setup["providers"][0]["skill_id"]

    class ModelFixture:
        def configuration(self):
            return {"provider": "explicit-fixture", "model_request_executed": False}

        async def generate(self, contents, tools, system):
            responses = [
                p["function_response"]["response"]
                for c in contents
                for p in c.get("parts", [])
                if "function_response" in p
            ]
            if not responses:
                assert tools[0]["capability_tags"] == ["pests.taxonomy"]
                call = {"name": tools[0]["alias"], "arguments": {"eppo_code": "LAPHFR"}, "id": "fixture-eppo"}
                return {"calls": [call], "text": "", "content": {"role": "model", "parts": []}}
            evidence_id = responses[-1]["evidence_ids"][0]
            text = "Scientific name: Spodoptera frugiperda. Evidence: " + evidence_id
            return {"calls": [], "text": text, "content": {"role": "model", "parts": [{"text": text}]}}

    response = client.post(
        f"/api/v1/skills/{skill_id}/runs",
        headers=office["users"]["admin"]["headers"],
        json={
            "task": "Look up the scientific name for this EPPO code",
            "request_key": "fixture-eppo-investigation",
            "parameters": {"eppo_code": "LAPHFR"},
            "authorize_network": True,
            "authorize_model": True,
        },
    )
    assert response.status_code == 202, response.text
    asyncio.run(process_job(response.json()["id"], model=ModelFixture()))
    result = client.get(response.json()["status_url"], headers=office["users"]["admin"]["headers"]).json()
    assert result["status"] == "succeeded", result
    assert result["result"]["evidence_ids"][0] in result["result"]["answer"]
    assert len(calls) == 1  # Runtime reuses the permission-scoped cache from the HTTP test.
