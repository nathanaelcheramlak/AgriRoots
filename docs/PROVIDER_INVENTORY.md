# Agricultural provider inventory

Before implementation, the existing `f-test/reports/results.json` and saved agricultural evidence were inspected. The imported inventory retains source timestamps, original scope, limitations and SHA-256 references. Its 22 checks include 21 providers plus a separate NASA MCP check: **9 WORKING, 10 AUTH_REQUIRED, 2 PARTIAL, 1 NOT_TESTED** in that historical report. These are not all newly verified results.

The historical report contract audit produced 10 passes, two failures and 11 skips. The two failures correspond to GAEZ metadata-only coverage and ASIS raster HTTP 403; they were not converted into successful agricultural measurements. Existing `f-test` source, credentials and response reports were preserved. No provider credential was automatically copied between projects or offices.

| Source | Backend disposition | Verification boundary |
| --- | --- | --- |
| Open-Meteo | Reviewed forecast handler through shared executor | Newly verified live through actual management/test/approval path; fixture contract also exercised |
| NASA POWER REST | Reviewed historical-climate handler | Prior live verification retained; parser/date/unit/location fixtures validate new adapter behavior |
| NASA POWER MCP | Generic official-SDK HTTP connector | Newly discovered and called live with SDK 1.29.0, negotiated protocol 2025-03-26, actual historical daily values validated offline from the saved response |
| iSDAsoil | Reviewed login/layers/property handler | Prior live result retained; new controlled HTTP fixture verifies login, units, depths, uncertainty and missing layers. No new credential request was made |
| CHIRPS / ClimateSERV | Reviewed asynchronous submission/polling handler | Prior live area result retained; currently limited to the previously tested synthetic Adama polygon. Registered farm-geometry generalization deferred |
| FAO FPMA | Reviewed Ethiopian series/price handler | Prior live result retained. New live availability has not been rechecked |
| FAO Locust Hub | Reviewed owner-checked ArcGIS observation handler | Prior live result retained. Reported historical observations are not a current outbreak warning |
| FAO WaPOR | Historical range-read adapter preserved in `f-test` | New shared-executor raster/range integration deferred; no unlabeled replacement |
| Kindwise crop.health | Existing production/legacy code and one historical real photo result retained | New companion image-asset workflow deferred. No additional credit-consuming diagnosis call; no Ethiopian-field accuracy claim |
| Copernicus/Sentinel Hub, Earth Engine | Disabled inventory | Missing configured account/client credentials/project access |
| Plantix | Disabled inventory | Access request submitted; no issued credential available |
| DeepLeaf, EPPO, CABI | Disabled inventory | Missing issued provider credentials |
| WFP/HAPI, OpenRouteService, Kobo | Disabled inventory | Missing the respective identifier/key/token |
| ODK Central | Disabled inventory | No configured Central server URL/account; no invented public server |
| Africa's Talking | Outbound actions unavailable to companion | Separate sandbox/access diagnostics retained; sending is outside this release |
| GAEZ, ASIS | Explicit partials | Suitability extraction/raster access remains incomplete |

`GET /api/v1/providers` exposes the sanitized inventory. `GET /providers/{id}/template` returns a template only for an implemented reviewed handler; unsupported inventory entries return an explicit blocker. `POST /providers/{id}/verify` targets an existing exact office-owned operation and uses the same controlled diagnostic job as other tests. Inventory import never enables a connection or substitutes old evidence for a live runtime request.

Machine-readable records are `backend/reports/provider_inventory.json` and `backend/reports/connector_live_results.json`. The latter records actual URLs without secret query strings, timestamps, SDK/server/protocol metadata, values and eight HTTP attempts. NASA's MCP result uses **LST**; the REST adapter requests **UTC**. That difference is retained. Both new live checks use a synthetic Adama plot context with real provider evidence, a mixed provenance explicitly recorded rather than described as real field observations.
