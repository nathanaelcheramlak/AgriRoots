# Backend API skill integration results

Recorded 2026-11-16T19:31:34.083160+00:00.

Fourteen reviewed provider operations and fifteen FieldOps skills are implemented. Thirteen providers have VALID live backend evidence and are enabled. Fourteen FieldOps skills are enabled, including the combined weather/soil/rainfall skill. Kindwise is implemented and fixture-tested but remains disabled pending a newly authorized credit-consuming request. These are officer-facing capabilities; farmer chat and automatic alert/release workflows were not changed.

| Provider | Implemented | Backend live check | Enabled |
| --- | --- | --- | --- |
| Open-Meteo | Yes | VALID | Yes |
| iSDAsoil | Yes | VALID | Yes |
| NASA POWER REST | Yes | VALID | Yes |
| CHIRPS / ClimateSERV | Yes | VALID | Yes |
| FAO FPMA | Yes | VALID | Yes |
| WFP / HDX HAPI | Yes | VALID | Yes |
| EPPO Global Database | Yes | VALID | Yes |
| FAO Locust Hub | Yes | VALID | Yes |
| FAO WaPOR | Yes | VALID | Yes |
| FAO GAEZ | Yes | VALID | Yes |
| FAO ASIS | Yes | VALID | Yes |
| Google Earth Engine | Yes | VALID | Yes |
| Kindwise Crop.health | Yes | NOT_RUN_CREDIT_AUTHORIZATION_REQUIRED | No |
| OpenRouteService | Yes | VALID | Yes |

## Validation evidence

Live checks use explicitly synthetic location records and real provider responses. They establish operation/access/schema success, not scientific accuracy or validation of registered farms. No previous standalone sample was substituted for a backend result.

- [Activation outcomes](verified_skill_activation.json): exact tool versions, jobs and evidence IDs.
- [Registry read-back](verified_registry_state.json): migration 5, fifteen skills, fourteen enabled skills and HTTP 200 readiness for PostgreSQL/Redis.
- Current API-container source hashes matched the local provider, executor, credential-contract, image-service and skill-registration source files. API, worker and MCP were rebuilt from the same source.
- Native dependency compatibility and changed-file lint checks passed; the shareable source/docs/reports scan found no supplied credentials in 248 files.

- [Full backend suite](../validation/verified-backend-final.xml): 161 passed, 1 failed, 0 errors, 1 skipped.
- [New integration checks on disposable PostgreSQL](../validation/verified-postgres.xml): 27 passed, 0 failed, 0 errors, 0 skipped.
- [Isolated recheck of the legacy advisory failure](../validation/verified-legacy-recheck.xml): 1 passed, 0 failed, 0 errors, 0 skipped.

- [Final advisory and integration regression group](../validation/verified-advisory-final.xml): 54 passed, 0 failed, 0 errors, 0 skipped.

The full backend batch had one existing advisory test fail with a generic upstream-failure result. That same test passed on isolated recheck and in the final 54-test advisory/integration group; the root cause was not established. The full-batch failure remains in its original XML and is not rewritten as an all-green full run. Initial migration assertions and activation-helper issues were corrected; earlier XML and activation outcomes remain available.

## Limits and corrections

- No live companion-model request was made: the configured Gemini key is absent. The real LangGraph/function-call/executor/evidence loop is exercised with explicitly labelled model and HTTP fixtures, including EPPO. This does not claim a real Gemini/Qwen investigation passed.
- No new Kindwise request or diagnosis credit was spent. Private image validation, office ownership, exact-version execution, ambiguous submission handling and duplicate receipts were tested with fixtures.
- Linux raster extraction initially failed because the container lacked libexpat.so.1. The final image installs libexpat1; WaPOR and GAEZ then passed exact-version backend checks.
- Earth Engine initially failed before SDK dispatch because its deadline setter was called before initialization. Initialization ordering was corrected; the seven accounted HTTP requests in the successful check include OAuth refresh, SDK discovery/algorithms and computation. No default SDK network transport is used.
- CHIRPS now passed through the backend with a plot-centred box; job identifiers are stored for explicit same-office/version/input resumption. An uncertain submission is not automatically sent again.
- WaPOR succeeded for the selected October 2026 composite, GAEZ for its fixed historical maize scenario, ASIS for a July 2025 dekad and Earth Engine for January 2025 MODIS composites. None is presented as a current farm-health measurement.
- Driving routes currently connect two authorized plot references. Arbitrary destination coordinates, isochrones, automatic market matching, scheduled surveillance and outbound messaging remain outside this increment.

See the [integration guide](../../docs/VERIFIED_API_INTEGRATION.md) for interfaces, data flow and operator commands.
