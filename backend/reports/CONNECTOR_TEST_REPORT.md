# Connector implementation test report

Generated 2026-11-16T10:08:17.188650+00:00. Branch `agri-mcp`, base `676b0fafb5a36a55d7f68489f6b3f619be282f5a`, implementation 0.4.0.

Final full regression: **124 passed, 0 failed, 1 skipped**. PostgreSQL/Redis connector suite: **65 passed, 0 failed, 0 skipped**. These suites overlap and must not be added together.

The default-suite skip is the opt-in dedicated Redis contract; that contract ran against real local Redis in the PostgreSQL/Redis suite. Real English/Amharic speech is included in the full run. No paid diagnosis call or real Gemini request was made.

New live verification: **Open-Meteo REST and independently maintained NASA POWER MCP** both returned actual evidence through the management API/shared executor. The official SDK negotiated protocol 2025-03-26 with NASA POWER MCP Server 1.1.0-beta. Eight HTTP attempts were recorded. The saved NASA response also passed numeric, date, coordinate and unit validation; its time standard is LST. Real Gemini remains credential-blocked.

Deployment verification used actual PostgreSQL 16, Redis 7, separate migration owner/application roles and the running API/worker/internal-MCP containers. Both health routes passed with zero provider calls; forbidden audit mutation was denied; checkpoints persisted across saver sessions; encrypted Redis data and real local speech passed. Deployed security/graph/main source hashes match the workspace.

## Acceptance matrix

| ID | Observed result |
| --- | --- |
| REST-01 | PASSED_FIXTURE |
| REST-02 | PASSED_FIXTURE |
| REST-03 | PASSED_FIXTURE |
| REST-04 | PASSED_FIXTURE |
| REST-05 | PASSED_FIXTURE |
| REST-06 | PASSED_FIXTURE |
| REST-07 | PASSED_FIXTURE |
| REST-08 | PASSED_FIXTURE |
| MCP-01 | PASSED_FIXTURE |
| MCP-02 | PASSED_FIXTURE |
| MCP-03 | PASSED_FIXTURE |
| MCP-04 | PASSED_FIXTURE |
| MCP-05 | PASSED_FIXTURE |
| MCP-06 | PASSED_FIXTURE |
| MCP-07 | PASSED_FIXTURE |
| MCP-08 | PASSED_FIXTURE |
| POLICY-01 | PASSED_FIXTURE |
| POLICY-02 | PASSED_FIXTURE |
| POLICY-03 | PASSED_FIXTURE |
| POLICY-04 | PASSED_FIXTURE |
| POLICY-05 | PASSED_FIXTURE |
| POLICY-06 | PASSED_FIXTURE |
| REGISTRY-01 | PASSED_FIXTURE |
| REGISTRY-02 | PASSED_FIXTURE |
| REGISTRY-03 | PASSED_FIXTURE |
| CACHE-01 | PASSED_FIXTURE |
| MODEL-02 | PASSED_FIXTURE |
| LIVE-01 | VERIFIED_LIVE |
| LIVE-02 | VERIFIED_LIVE |
| MODEL-01 | BLOCKED |

REST-07 covers bounded retry, response expansion and deadline behavior; generic pagination is unavailable. MCP-06 covers structured/text/error and unsupported-artifact handling; interactive capabilities remain unsupported and are never granted.

## Reproduction

Run from `backend/`. The PostgreSQL helper uses only the fixed disposable `agrilo_test` database on the dedicated localhost test port; its fixtures drop application tables. Never substitute an operational database.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short --junitxml=validation/agri-mcp-final.xml
.\.venv\Scripts\python.exe scripts/test_connectors_postgres.py
.\.venv\Scripts\python.exe scripts/demo_connectors.py
.\.venv\Scripts\python.exe scripts/demo_connectors.py --live
docker compose -p agrilo-connectors-test -f compose.yaml -f compose.test.yaml --env-file private-data/compose.env up -d --build api worker mcp
Get-Content scripts/check_connector_runtime.py -Raw | docker compose -p agrilo-connectors-test -f compose.yaml -f compose.test.yaml --env-file private-data/compose.env exec -T api python -
.\.venv\Scripts\python.exe scripts/import_provider_inventory.py ..\..\f-test\reports\results.json
```

## Artifacts and provenance

- [Full JUnit result](../validation/agri-mcp-final.xml)
- [PostgreSQL/Redis JUnit result](../validation/agri-mcp-postgres-redis.xml)
- [Machine-readable acceptance, test cases and exact dependency versions](connector_test_results.json)
- [Saved live requests/results and attempt trace](connector_live_results.json)
- [Actual deployment probes](connector_deployment_results.json)
- [Persistent fixture demo](connector_fixture_demo.json)
- [Historical API inventory](provider_inventory.json)

Final working-tree code/dependency fingerprint: `5bfbb4dbd4b2f63e09c6e14a643619dae5ceb50338a84cedef78283a93e349fd`. Test timestamps are retained in JUnit. Earlier incremental reports are journaled separately; they include failures fixed during implementation and are not represented as current failures.

## Blocked and deferred

- MODEL-01: no configured Gemini API key or verified model access; only SDK/model fixtures ran.
- Plantix credential issuance and other inventory entries requiring account access remain outside configured office connections.
- Bounded OpenAPI importer
- Generic REST pagination
- Interactive OAuth/elicitation/sampling
- Tenant stdio/code plugins
- Private image asset workflow and new Kindwise credit calls
- Instrumented WaPOR raster/range transport
- CHIRPS geometry beyond the historical synthetic Adama fixture
- Full map/PostGIS FieldOps workflows and frontend
- Automatic companion advisory approval/release or external messaging

## Limits

- Final schema hardening rejects regex patterns, quadratic uniqueness checks and unchecked formats; its separate fixture result is included rather than folded into an earlier full-suite count.
- Fixtures do not prove live availability or agronomic accuracy.
- Old report failures are retained as historical execution evidence; only latest runs determine acceptance.
- The live report predates final provenance/audit hardening; final changes were verified with protocol/database fixtures. Its real responses were not fabricated or relabeled.
- Live public checks used a synthetic plot context and real provider evidence. NASA MCP uses LST, not the REST adapter UTC request.
- Actual/estimated monetary costs remain unknown/null unless supplied; request caps are not dollar limits.
- Generic read-only POST and remote implementation behavior require administrator/provider trust.
- Legacy third-party Fetch subprocess HTTP traffic is bounded by its proxy but not individually counted as common-executor attempts.
- SQLite development cannot establish production cross-process revocation locking.
