# Registered agricultural API skills

> This page records the initial disabled registration snapshot. The [current priorities and activation report](../../docs/PROVIDER_PRIORITIES.md) now records three enabled skills and the CHIRPS timeout.

Registered 2026-11-16T11:49:34.576595+00:00 in the running local PostgreSQL backend, office `da25ffd4-7ab3-4d6c-ac68-d38e1294ba9e`.

Installed the immutable `provided_agri_apis` v1 pack: **9 disabled connection drafts, 8 disabled skill definitions, 6 implemented tool definitions, and 2 encrypted connection credentials**. Nothing was automatically tested, approved, enabled, or sent to a provider/model.

The originally supplied iSDAsoil username/password and Kindwise Crop.health key were read from the ignored local test environment and attached through the same office-scoped credential service. Neither is embedded in the pack or this report. Existing credentials remain in their original local store.

The running backend was empty. Its initial local API workspace uses an office-scoped setup service identity, with no global administrator role and no saved interactive password. A real deployment should install the same pack under its actual office administrator.

## Counts from the previous API report

- 7 key-free successful checks, counting NASA REST and NASA MCP separately.
- 2 additional key-free candidates were partial: GAEZ metadata only, ASIS raster access denied.
- iSDAsoil and Kindwise were also verified previously using the credentials supplied by the user.
- Those historical outcomes are separate from this registration, which made zero upstream requests.

## Initial registrations

| API | Skill | Local status |
| --- | --- | --- |
| Open-Meteo | `provided_agri_apis_v1_weather_forecast` | Draft registered; test/review/enable required |
| NASA POWER | `provided_agri_apis_v1_climate_history` | Draft registered; test/review/enable required |
| CHIRPS / ClimateSERV | `provided_agri_apis_v1_rainfall_history` | Draft registered; test/review/enable required |
| iSDAsoil | `provided_agri_apis_v1_soil_profile` | Draft registered; test/review/enable required |
| FAO WaPOR | `provided_agri_apis_v1_water_productivity` | Draft connection; instrumented raster transport pending |
| FAO FPMA | `provided_agri_apis_v1_market_context` | Draft registered; test/review/enable required |
| NASA POWER public MCP | `provided_agri_apis_v1_climate_history` | Draft connection; discovery, review and testing required |
| Kindwise Crop.health | `provided_agri_apis_v1_crop_health` | Encrypted credential attached; authorized image workflow pending |
| FAO Locust Hub | `provided_agri_apis_v1_locust_context` | Draft registered; test/review/enable required |

## Complete API inventory

| API | Needs credentials for the tested path? | Previous result | Current registration |
| --- | --- | --- | --- |
| Open-Meteo | No | VERIFIED_LIVE | Draft registered |
| NASA POWER | No | VERIFIED_LIVE | Draft registered |
| CHIRPS / ClimateSERV | No | VERIFIED_LIVE | Draft registered |
| iSDAsoil | Yes | VERIFIED_LIVE | Draft registered |
| FAO WaPOR | No | VERIFIED_LIVE | Draft registered |
| Copernicus Sentinel Hub | Yes | AUTH_REQUIRED | Inventory only |
| FAO FPMA | No | VERIFIED_LIVE | Draft registered |
| NASA POWER public MCP | No | VERIFIED_LIVE | Draft registered |
| FAO GAEZ | No | PARTIAL | Inventory only |
| Google Earth Engine | Yes | AUTH_REQUIRED | Inventory only |
| FAO ASIS | No | PARTIAL | Inventory only |
| DeepLeaf | Yes | AUTH_REQUIRED | Inventory only |
| Kindwise Crop.health | Yes | VERIFIED_LIVE | Draft registered |
| Plantix Intelligence | Yes | AUTH_REQUIRED | Inventory only |
| FAO Locust Hub | No | VERIFIED_LIVE | Draft registered |
| EPPO Global Database | Yes | AUTH_REQUIRED | Inventory only |
| CABI PMDG | Yes | AUTH_REQUIRED | Inventory only |
| WFP / HDX HAPI | Yes | AUTH_REQUIRED | Inventory only |
| OpenRouteService | Yes | AUTH_REQUIRED | Inventory only |
| KoboToolbox | Yes | AUTH_REQUIRED | Inventory only |
| ODK Central | Yes | NOT_TESTED | Inventory only |
| Africa's Talking | Yes | AUTH_REQUIRED | Inventory only |

NASA REST and NASA MCP can provide the same reviewed climate-history capability; they share one skill rather than inflating the skill count. The other registered skills cover forecast, rainfall, soil, water productivity, prices, locust observations and crop health.

## Remaining activation work

- Six implemented operations need exact-version tests, approval and explicit enablement in this office. Historical tests do not grant new-office runtime permissions.
- NASA MCP needs SDK discovery in this office before its reviewed operation can be registered/tested.
- WaPOR needs the reviewed range/raster transport; a catalogue connection is not a numerical evidence adapter.
- Kindwise needs the authorized image workflow; the stored key alone does not enable a paid diagnosis.
- Gemini is the additional model service, not one of the 22 agricultural inventory entries. Its key/model remain unconfigured.
- Use the optional `compose.policy.yaml` override with this local stack; it mounts the exact-host policy including the verified WaPOR and Kindwise origins.

Registration checks: two registry/credential/bootstrap tests passed. The actual running HTTP API confirmed the registered counts, disabled/unapproved states, dependency readiness, no connector jobs and zero provider attempts.
