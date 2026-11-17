# Phase 2 Plugins integration report

Scope: the current `agrilo-fieldops-frontend`, actual office-scoped backend connection/tool registry and its existing secure management lifecycle. Phase 1 was reverified before work; no critical Home regression was found. No Skills, Monitoring or Outreach integration was started.

## Integration matrix

| Feature | Frontend state | Backend state | Integration state | Next action |
| --- | --- | --- | --- | --- |
| Home | Existing map/auth/jobs/evidence retained | Existing LangGraph executor unchanged | Four Home API tests and four browser regressions pass | Live-model/account configuration still required |
| Provider catalog | Fourteen implemented adapters with distinct configured/tested/approved/enabled states | Current operator handler mapping merged with historical inventory | Authenticated provider/template contract tested for all fourteen | Individual live tests remain separate |
| Custom REST | Disabled configuration, schema/mapping editor, preview, diagnostics and revisions | Existing approved-host/read-only/validation services | Actual backend/browser fixture flow verified | Operator provisions credentials/host policy where needed |
| MCP | Registration, discovery, tool inspection/review, tests | Existing official SDK, durable discovery and exact-version gates | Real local MCP protocol tested through browser and executor | Real endpoint/credentials/network authorization needed for live servers |
| Approval and activation | Separate exact-version approval and tool/connection controls | Existing admin-only tests, credential-scope checks and version gates | Officer rejection and preapproval activation rejection tested | Separate review queue is absent |
| Local drafts | Original local editor/storage retained; explicit metadata migration | Ordinary disabled connection registration | Draft preservation and migration browser-tested | No atomic deduplication/migration endpoint |
| Credentials | Metadata only; no browser credential values | Existing encrypted write-only API reused by interactive operator helper | No readback or browser persistence; helper input policy checked | Actual writes intentionally not performed |
| Skills / Monitoring / Outreach | Existing local/draft behavior retained | No new integration | Out of scope | Wait for review and explicit next-phase instruction |

## Verification record

Initial Phase 1 verification: **4 Home backend tests and 4 Home browser tests passed** before implementation.

Post-change checks observed so far:

- `npm run check`: typecheck and lint passed; **104 unit tests passed**, production build passed.
- Backend REST/MCP/Home/catalog/role regression: **28 passed** in `backend/validation/phase2-plugins.xml`. This includes actual executor calls after approval and denial/revocation safeguards, not just API request mocks.
- Additional targeted catalog/role/credential-helper policy run: **3 passed** in `backend/validation/phase2-catalog-and-roles.xml` (two overlap with the 28-test run; **29 distinct backend tests** verified across these runs).
- First full-stack Plugins+Home browser run: **8 passed**: four Home scenarios plus REST full lifecycle, actual MCP discovery/review/test/approval/enablement, officer denial/logout isolation and explicit draft migration.
- Default demo browser regression: **29 passed, 8 skipped** in its first Phase 2 run. Dedicated backend scenarios skip by design in default mock mode and run separately.
- API/worker rebuilt and restarted using the existing Compose project with `--no-deps --no-build` after build. No migration, seeding, reset or private environment change. Current `/health/ready` returned **200**; unauthenticated provider and connection endpoints returned **401**. The deployed catalog resolves **14** reviewed adapters. The service restart does not establish live provider/model reachability.
- Changed backend files pass Ruff; provider templates preserve historical verification; UI fixture screenshots retain the dark shell/modal design. New credential helper `--help` works without collecting a secret. Actual credential writes were not made.
- Exact-value scan of 75 changed text files against seven known local environment secrets found no matches; this bounded check is not a comprehensive security audit. Both repositories pass `git diff --check` (including staged retirements). Phase 2 documentation links resolve.

The extended final browser verification passed **all 10 scenarios** (four Home and six Plugins), including mobile registry, blocked destination and same-job refresh after the last UI change. No live paid API, external MCP endpoint, cloud model or real-farm efficacy is claimed. Historical provider checks are not fresh Phase 2 probes.

## Contract and limitations

See the [frontend guide](../agrilo-fieldops-frontend/docs/PHASE2_PLUGINS_INTEGRATION.md) for every actual route, setup, lifecycle walkthrough, credential helper and security/persistence limits.

Minimal production backend correction: `src/providers/inventory.py` resolves stable provider IDs to the actual operator-reviewed factory. Existing provider listing, template and verification routes use it. The immutable historical import stays unchanged. Existing approvals, executor policy, models, skills, review/release and jobs are reused without exemptions.

Remaining gaps: no separate review submission queue, backend deletion, atomic migration/deduplication, creation idempotency, direct Plugins runtime API, interactive MCP OAuth, tenant stdio or REST OpenAPI import. No browser credential input/readback is added; use the existing write-only backend service through the interactive helper. The local catalog remains historical metadata, not runtime authority. Very large office performance and every provider-specific browser workflow are not verified. The existing operational live model and interactive account blockers remain.

Stop after Phase 2 for user review. No commit, push, Skills integration, recurring scheduling or message sending is included.

## Phase 2 files

Paths are relative to their respective repositories. Previous uncommitted Phase 1 and frontend-retirement changes are preserved; they are not newly attributed to Phase 2.

### AgriRoots

- `backend/src/providers/inventory.py` — current implementation metadata with historical evidence preserved.
- `backend/src/api/routes/integrations.py` — existing provider routes use current catalog; prior Home progress change retained.
- `backend/scripts/configure_connection_credential.py` — optional hidden-prompt operator client for existing write-only credential API.
- `backend/scripts/check_home_browser.py` — optional `--plugins` isolated suite; original Home mode retained.
- `backend/tests/home_browser_server.py` — opt-in disposable administrator and real MCP fixture; original Home flow retained.
- `backend/tests/test_plugins_integration.py` — fourteen current templates, historical preservation, role/approval gate and helper origin policy checks.
- `backend/validation/phase2-plugins.xml` — actual 28-test regression result.
- `backend/validation/phase2-catalog-and-roles.xml` — actual targeted three-test result.
- `docs/PHASE2_PLUGINS_INTEGRATION.md` — this report.
- `docs/README.md`, `docs/testing.md` — links/current verification commands.

### agrilo-fieldops-frontend

- `src/api/home-api.ts` — restricted shared authenticated connector transport; token stays private/in memory.
- `src/features/plugins/managed-api.ts` — actual routes, runtime contracts, pagination and metadata safety checks.
- `src/features/plugins/managed-store.ts` — office-scoped memory snapshots, cancellation/stale-response protection and real job polling.
- `src/features/plugins/managed-runtime.ts` — shares Home session and clears managed state on identity changes.
- `src/components/plugins/ManagedPluginsPage.tsx` — existing dark shell with authoritative catalog/connections and explicit migration.
- `src/components/plugins/ManagedConnectionDetails.tsx` — inspection, tests, approval and activation.
- `src/components/plugins/ManagedForms.tsx` — disabled REST/MCP registration and exact operation revision editors.
- `src/components/plugins/PluginsPage.tsx` — explicit HTTP mode; original local page retained.
- `src/styles/plugins-managed.css` — scoped styles, including narrow layouts.
- `src/app/App.tsx` — account label reflects Home and Plugins scope; no navigation/lifecycle change.
- `tests/plugins-managed.test.ts` — seven meaningful pagination/session/version/failure/duplicate/metadata tests.
- `e2e/plugins-backend.spec.ts` — real backend fixture browser scenarios.
- `playwright.plugins.config.ts` — separate backend-connected browser suite/report.
- `.gitignore` — ignore new browser report/screenshot output.
- `docs/PHASE2_PLUGINS_INTEGRATION.md`, `README.md`, `docs/PLUGINS_FRONTEND.md` — guide/current status and historical demo boundary.
