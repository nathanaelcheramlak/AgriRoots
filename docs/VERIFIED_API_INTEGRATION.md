# Verified agricultural API skills

This increment extends the existing officer companion, registry, executor and durable queue to fourteen reviewed provider operations. It does not connect farmer chat to these new skills, release advisories, send notifications or establish diagnostic accuracy. Standalone `f-test` evidence and backend execution results are separate.

## Operations and inputs

All run requests use `POST /api/v1/skills/{skill_id}/runs`. Supply `task`, a unique `request_key`, `plot_ids`, `authorize_network` and, for a model investigation, `authorize_model`. Optional `parameters` contains only the fields below. Missing dates or codes should cause the assistant to ask for them rather than invent them. The model cannot supply server-bound latitude, longitude or image IDs.

| Provider | Capability | Inputs and verified interpretation |
| --- | --- | --- |
| Open-Meteo | `weather.forecast` | One plot; three-day modelled forecast. |
| iSDAsoil | `soil.profile` | One plot; mapped properties at 0–20 cm, units and uncertainty. |
| NASA POWER REST | `climate.history` | One plot, `start`, `end`; historical daily climate. |
| CHIRPS / ClimateSERV | `rainfall.history` | One plot, `start`, `end`; daily averages over a 0.002-degree plot-centred box, not a farm boundary. Optional `resume_invocation_id` polls a previously saved matching job. |
| FAO FPMA | `market.prices` | Optional exact `market_name` and `commodity_name`; actual selected Ethiopian series metadata and recent records. |
| WFP / HDX HAPI | `market.wfp_prices` | `start`, `end`; five historical Ethiopian market-price records with source, period, currency, unit and price type. |
| EPPO | `pests.taxonomy` | `eppo_code`; names only, without occurrence or treatment claims. |
| FAO Locust Hub | `pests.regional_reports` | Public reported observations in the Ethiopian regional box; country is only confirmed when returned. |
| FAO WaPOR | `water.evapotranspiration` | One plot, `start`, `end`; scaled evapotranspiration pixel for an overlapping composite. A bounded catalogue scan may return no matching period. |
| FAO GAEZ | `crop.maize_suitability` | One plot; fixed v4 maize, high-input rain-fed, 1981–2010 scenario on a 5 arc-minute grid. No other crop/scenario is claimed. |
| FAO ASIS | `vegetation.condition` | One plot, `start`, `end`; raw normalized VCI from 0 to 1, with full dekadal dates. |
| Google Earth Engine | `vegetation.ndvi` | One plot, `start`, `end`; up to four MODIS/061/MOD13Q1 composites, SummaryQA=0, valid raw range and NDVI scaling, 250 m pixels in a 500 m buffer. |
| Kindwise Crop.health | `crop.diagnosis` | Run-level `image_asset_id` and `authorize_credit_use: true`; uncertain crop/disease candidates from a private image. |
| OpenRouteService | `logistics.route` | Two authorized plot IDs in `plot_ids`; `from_plot_id`, `to_plot_id` select them. Driving distance/duration; no arbitrary destination coordinates or isochrones. |

Historical tools accept a past inclusive window of at most 31 days. Composite observation periods can extend beyond that window and remain explicit. GAEZ has a fixed baseline, independent of task dates. NASA POWER MCP remains an alternative interface, not another corroborating dataset.

Focused skills accompany these operations. `fieldops_agricultural_context` requires weather and soil, with optional historical rainfall. It explains evidence; no crop calendar, fertilizer dose, pest alert or crop ranking is invented.

## Query and storage flow

1. Load the officer's office membership and authorized plots from PostgreSQL.
2. Resolve the skill's capabilities to approved, enabled registry versions and pin the run snapshot.
3. LangGraph sends reviewed instructions, opaque plot references and bounded task parameters to the configured companion model.
4. The model proposes a function. The executor validates its arguments, binds location/image context, checks budgets, credentials and current permissions, and dispatches the reviewed adapter.
5. Validate provider values, units, dates and geography; save source evidence and request/response digests in PostgreSQL. Large evidence stays intact while a compact validated projection reaches the model.
6. Return actual tool outcomes to the model for bounded follow-ups. The final answer must reference run evidence; missing data produces a partial result rather than a fabricated observation.

The existing PostgreSQL/SQLite LangGraph checkpointer supports resumption. Redis remains optional. There is no new vector database, automatic web search or automatic fallback model.

All provider HTTP, raster byte ranges, Earth Engine discovery, OAuth refresh and computation use the controlled transport. Rasterio opens Python file objects; GDAL is not given remote URLs. Earth Engine receives an injected HTTP transport and a refreshed token, with serialized SDK initialization and retries disabled. Worker cancellation and dispatch gates still apply to every remote request.

## Installation and activation

- Apply additive migration 5 before API/worker deployment. It creates private image metadata and diagnosis receipt tables without rewriting existing records. Use the migration-owner setup command so PostgreSQL grants include the new tables.
- Install locked dependencies with the `raster` and `earthengine` extras; the container lock includes both, and the Linux image installs the required `libexpat1` runtime. Rebuild API, worker and MCP from the same source version.
- `GET /api/v1/plugins/templates/verified-agriculture` returns a versioned pack with fourteen tools and fifteen skills. Installing it creates disabled drafts. Existing pack versions remain unchanged in the database.
- Existing offices should use `backend/scripts/sync_verified_skills.py`: it reuses reviewed handler connections, creates new tool versions only when needed, and registers focused skills idempotently. JSON input arrives on protected stdin, never command-line credentials. Supply an existing `principal_id`; this script creates no users or offices.
- Registration alone performs no provider or model requests. With `live_test: true`, `samples` selects exact operations to test through the queue. Only a `VALID` result is approved/enabled. Every outcome and evidence ID is returned; failed or missing checks are not called live successes.
- Provider keys use connection-owned encrypted credentials. iSDA uses `{username,password}`; EPPO, HAPI, Kindwise and ORS use their respective credential strings. Earth Engine uses `{project,refresh_token,client_id,client_secret}` from the authorized account. Never place those values in skill manifests, reports, images or model prompts.
- Set an explicit supported companion model and its key before a live model run. The current synthetic-only cloud plot policy remains in force unless the deployment operator changes it.

Example registration/test input, with credentials already stored:

```json
{
  "principal_id": "<existing-office-admin-id>",
  "providers": ["eppo"],
  "live_test": true,
  "samples": {
    "eppo": {"arguments": {"eppo_code": "LAPHFR"}, "plot_ids": []}
  }
}
```

The existing `LIVE_TESTS_ENABLED` deployment gate must permit external diagnostics. Reusing the same exact-version/account/day test key does not send a second request. A remote timeout is retained as an uncertain outcome, not automatically retried as a new submission.

## Private images and quota

Upload with multipart field `image` to `POST /api/v1/image-assets`. Only JPEG/PNG uploads up to 10 MB and 20 million decoded pixels are accepted. Images are re-encoded without EXIF/GPS/ICC metadata and saved in shared private storage; the response contains an opaque ID, type and byte count, never a public URL. Keep that storage private, backed up and available to both API and workers. There is no automatic retention deletion in this increment.

Attach the ID to the skill run, not to model-generated arguments. Cross-office access is rejected. Only the reviewed Kindwise handler can transmit it, with explicit credit authorization. A unique office/provider/image-digest receipt is committed before submission. If a request fails, loses its response or the worker stops, resubmitting that image is blocked for operator investigation. No exactly-once guarantee is claimed for the external provider.

## Verification and references

`backend/tests/test_verified_integration.py` covers pack installation, idempotent reconciliation, actual executor/HTTP fixtures, image validation, office isolation, duplicate/ambiguous submissions, raster range extraction, provider contracts and additive migration. Existing connector, companion, policy and advisory tests remain applicable. Fixtures are labelled and do not establish live availability or scientific accuracy.

See [activation outcomes](../backend/reports/verified_skill_activation.json) and [implementation results](../backend/reports/VERIFIED_API_INTEGRATION_REPORT.md) for the current run, including unresolved providers and model/credit checks.

Transport implementation follows [Rasterio custom openers](https://rasterio.readthedocs.io/en/stable/api/rasterio.html) and [Earth Engine Python initialization](https://developers.google.com/earth-engine/apidocs/ee-initialize). Provider-specific scientific limitations originate from the saved API capability plan and `f-test` evidence; backend activation must establish its own result.
