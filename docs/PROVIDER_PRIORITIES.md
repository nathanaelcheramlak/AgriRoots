# Agricultural API priorities and active skills

Current update: fourteen provider operations and fifteen FieldOps skills are implemented. Thirteen providers passed live backend checks and are enabled; Kindwise awaits explicit credit authorization. The combined weather/soil/rainfall skill is enabled. Live model investigation is blocked by the missing configured model key. See [current integration results](../backend/reports/VERIFIED_API_INTEGRATION_REPORT.md). The earlier increment/priority record below is retained as historical evidence.

This is an engineering priority for the first AgriLo FieldOps release, based on the project journeys, verified adapters, available credentials, and remaining implementation work. It is not a ranking of scientific accuracy.

## First wave: current result

**Three data skills are now live-verified, reviewed and enabled:** Open-Meteo forecast, iSDAsoil mapped soil profiles, and NASA POWER historical climate. Their exact tool versions were tested in the current office before approval. Runtime execution also passed using the permission-scoped cache populated by those live tests. No Gemini request or diagnosis call was made.

CHIRPS is a core next requirement, but it remains disabled. The legacy path failed JSON validation; the adapter was updated to the current documented `/api/` path and narrowly scoped JSON media-type compatibility. Local contract/policy tests passed, but the subsequent live submission timed out. The remote outcome is uncertain, so no further automatic submission was attempted and no old sample was substituted as a new result.

Validation uses an explicitly synthetic Adama plot context, with real provider evidence. This does not establish field accuracy or general polygon support. The CHIRPS adapter is still restricted to its synthetic Adama polygon.

## Recommended order

| Rank | API | Phase | Current state | Why |
| --- | --- | --- | --- | --- |
| 1 | Open-Meteo | now | Live-verified and enabled | Forecast weather for planting timing, inspection and short-term planning. |
| 2 | iSDAsoil | now | Live-verified and enabled | Mapped soil properties, depth and uncertainty for plot context; user credential is already stored. |
| 3 | NASA POWER | now | Live-verified and enabled | Historical temperature, radiation, humidity, wind and precipitation context through the existing REST adapter. |
| 4 | CHIRPS / ClimateSERV | now | Disabled; live CHIRPS timeout | Historical rainfall complements forecasts; current adapter remains restricted to the synthetic Adama polygon. |
| 5 | FAO FPMA | next | Registered draft | Economic context for crop planning after agricultural evidence; preserve market, currency, units and dates. |
| 6 | Kindwise Crop.health | next | Registered draft | Supports the crop-photo case and has a stored key; finish the authorized image workflow before any credit-consuming call. |
| 7 | Copernicus Sentinel Hub | next | Inventory only | Vegetation statistics for registered polygons and map-based follow-up; credentials and polygon/no-data handling are pending. |
| 8 | FAO WaPOR | next | Registered draft | Water and evapotranspiration evidence; add the controlled raster/range transport first. |
| 9 | FAO Locust Hub | next | Registered draft | Regional pest surveillance supplements field checks; reported observations are not plot diagnoses. |
| 10 | NASA POWER public MCP | alternative | Registered draft | Alternative interface to NASA POWER data and an MCP integration demonstration; not an independent corroborating dataset. |
| 11 | CABI PMDG | later | Inventory only | Reviewed crop/pest management knowledge once licensed access and provenance are available. |
| 12 | EPPO Global Database | later | Inventory only | Pest taxonomy and reference enrichment after the core field-evidence flow works. |
| 13 | FAO GAEZ | later | Inventory only | Potential crop-suitability context, but numerical extraction was not established by the prior tests. |
| 14 | FAO ASIS | later | Inventory only | Regional agricultural stress context; previously blocked raster retrieval must be resolved. |
| 15 | Google Earth Engine | later | Inventory only | Broader geospatial processing platform; introduces setup and overlaps the narrower satellite integrations. |
| 16 | WFP / HDX HAPI | alternative | Inventory only | Additional price context after the first FPMA market skill is validated. |
| 17 | Plantix Intelligence | alternative | Inventory only | Alternative diagnosis provider; API access is pending and Kindwise is already available for the image workflow. |
| 18 | DeepLeaf | alternative | Inventory only | Additional diagnosis provider; issued access and a verified operation schema are missing. |
| 19 | KoboToolbox | later | Inventory only | External field-data synchronization after the existing workspace plot/household records are in use. |
| 20 | ODK Central | later | Inventory only | External field-data synchronization requires an actual configured Central server. |
| 21 | OpenRouteService | later | Inventory only | Travel/logistics is outside the first agricultural-evidence workflow. |
| 22 | Africa's Talking | out_of_scope | Inventory only | Outbound messaging remains outside the authorized companion capabilities. |

NASA REST and MCP are two access paths to the same underlying provider, not independent corroboration. Forecast, historical climate, rainfall estimates and mapped soil estimates keep their separate meaning and dates. Crop recommendations additionally require reviewed crop/calendar rules and registered farm context.

## Implementation and verification

- Added the operator activation helper `backend/scripts/activate_priority_skills.py`; it targets only four reviewed first-wave handlers and requires explicit live-test authorization.
- Added freshness policies in new immutable tool versions: forecast 1 hour, mapped soil 30 days, historical climate/rainfall 1 day. Cache hits retain original source retrieval and validity metadata.
- Tests go through the durable job queue and shared controlled executor. Approval and enablement happen only after valid evidence is saved; failed checks receive no approval.
- Approved/enabled the forecast, soil and climate-history skill configurations. Configuration tests do not pretend to be LLM runs.
- Repaired the ClimateSERV route prefix and added provider-only handling for strictly parsed JSON labelled text/plain or text/html. This exception is limited to three reviewed ClimateSERV paths and cannot be selected by generic REST configuration. Actual HTML bodies still fail JSON parsing.
- Verification: 48 adapter/policy fixture checks passed in `backend/validation/priority-adapters.xml`; includes successful activation/cache reuse, failed-auth non-activation, and generic REST media-type isolation.
- Current office registry was read back through the running HTTP API: 3 enabled connections and 3 approved/enabled skills; database and Redis readiness passed.

The activation trace records 15 actual HTTP attempts across successful checks and the failed CHIRPS attempts. Successful API checks and cache-based runtime checks are distinguished. Requests to Kindwise, Gemini and outbound-delivery services: zero.

## Evidence and reproduction

- [Complete ranking JSON](../backend/reports/api_priorities.json)
- [Current activation outcomes and actual response data](../backend/reports/priority_skill_activation.current.json)
- [Read-back of the running registry](../backend/reports/priority_registry_state.json)
- [Initial activation, including the first CHIRPS failure](../backend/reports/priority_skill_activation.json)
- [Updated-route CHIRPS attempt](../backend/reports/priority_chirps_activation.json)
- [Final CHIRPS timeout](../backend/reports/priority_chirps_legacy_activation.json)
- [Fixture test results](../backend/validation/priority-adapters.xml)

The local operator command ran `activate_priority_skills.py` in the API container with `LIVE_TESTS_ENABLED=true`, a 40-request per-job cap and a 180-second deadline. Only existing connection/skill IDs and the administrator ID were supplied on stdin; credentials were decrypted from their connection-owned store. The main API diagnostic switch was not globally enabled. The helper does not automatically resubmit a failed job with the same office/version/credential/day idempotency key.

For fixture checks, from `backend/`:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_provider_adapters.py tests/test_connectors_rest.py tests/test_connector_policy.py tests/test_priority_activation.py -q --tb=short --junitxml=validation/priority-adapters.xml
```

Provider references checked for this work: [Open-Meteo forecast documentation](https://open-meteo.com/en/docs), [NASA POWER Daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [iSDAsoil API documentation](https://api.isda-africa.com/isdasoil/v2/docs), and [current ClimateSERV developer API](https://climateserv.servirglobal.net/develop-api). These documents support interface selection, not claims that a live request passed. The saved execution results establish the observed outcomes.
