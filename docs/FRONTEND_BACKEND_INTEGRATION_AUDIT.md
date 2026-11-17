# FieldOps integration audit — Phase 0 and Phase 1

The frontend being integrated is the separate `agrilo-fieldops-frontend` repository (React 19, TypeScript, Vite, Zustand, TanStack Query, Zod, Leaflet/Geoman). `AgriRoots/frontend` was left untouched during Phase 1 and subsequently retired at the user's request; see [workspace restructuring](WORKSPACE_STRUCTURE.md). Both repositories were clean on `main` at the start of Phase 1.

## Verified contract matrix

| Frontend requirement | Existing contract | Authorization / async behavior | Initial status and required change |
| --- | --- | --- | --- |
| Officer login | `POST /api/auth/login` `{phone_number,password}` → `AuthResponse` with bearer token and user | Existing password login; no new accounts required | Requires a small frontend adapter; hold token in memory, never in browser persistence |
| Office identity | `GET /api/v1/me`, `GET /api/workspace/me` | Current membership determines office and role | Ready; do not accept a client-supplied office as authority |
| Authorized farms | `GET /api/workspace/offices/{office_id}/records?kind=plot` | Membership required; returns workspace records | Implemented; a small read-only Home projection will omit household PII and retain synthetic provenance |
| Farm details | Plot/season workspace records | Authorized office records; no provider call | Requires a frontend adapter; absent observations remain missing |
| Area selection | No server spatial-intersection endpoint | Run submission reauthorizes every supplied plot ID and binds coordinates from records | Requires a backend feature for server spatial queries; retain rectangle as a clearly labelled local filter of already authorized points |
| Executable skills and inputs | `GET /api/v1/skills`; `Registry.snapshot` resolves approved enabled versions and public model input schemas | Office, role, pack, approval and credential scope are checked | Requires small read-only projection; existing list shows current draft versions and is insufficient to infer runtime availability |
| Model selection | Configured `LLM_PROVIDER=gemini|local`, explicit model settings; no browser model-selection endpoint | Existing Gemini synthetic-only/approved-context policy and local Qwen mechanism | Display the configured model and readiness without changing it; no invented model selector |
| Start investigation | `POST /api/v1/skills/{skill_id}/runs` → durable job | `{task,plot_ids,parameters,request_key,authorize_network,authorize_model,authorize_credit_use,image_asset_id}`; at most five plots; model-driven function proposals use controlled executor | Ready; replace nonexistent `/assistant/query` and `/areas/analyze` calls |
| Job state/results | `GET /api/v1/connector-jobs/{id}`, `GET /api/v1/runs/{id}/results` | Same office; queued/running/succeeded/partial/failed/cancelled; no SSE | Ready; polling only, with a minimal optional recorded-invocation progress projection |
| Cancellation | `POST /api/v1/runs/{id}/cancel` | Initiating officer or office admin; dispatch may already have begun | Ready; cancelling a fetch alone is not cancelling a job |
| Evidence | `GET /api/v1/evidence/{id}` → `{id,data}` | Office scoped; full source/provenance and values | Ready; render actual numeric payloads, dates, units, quality, limitations and evidence IDs |
| Crop photograph | `POST /api/v1/image-assets` multipart `image`; opaque asset reference on skill run | Office ownership, validated image, explicit credit flag, durable duplicate receipt | Implemented/fixture verified; Kindwise is disabled in saved live evidence and must remain unavailable unless currently enabled |
| Conversation | Each skill investigation has its own job/checkpoint thread; no shared Home conversation API | Request contains one task, not an arbitrary transcript | Preserve a local conversation identity and job links across navigation; disclose that separate investigations do not share server conversation memory |
| Home charts | Numerical values in evidence and normalized tool outcomes | Preserve dates, units and provider classifications | Requires frontend renderer; do not derive chart values from answer text |
| Plugins / Skills pages | Separate local catalog/drafts; no dedicated Skills navigation currently | Existing localStorage stores plugin drafts, not a secure credential store | Out of scope; keep unchanged. Home may list backend skills for investigation only |
| Monitoring / Outreach | Separate local stores and demo/draft pages | No verified recurring scheduler or bulk-delivery integration | Out of scope; keep unchanged and do not send messages |

The old `HttpFieldOpsApi` assumed `/api/v1/areas/analyze`, `/analysis/{id}` and `/assistant/query`, none of which exists. It had no authentication. Existing Home overview, farm risk/crop candidates, chat commands and local advisories are synthetic. The map is mounted across navigation already and calls `invalidateSize` on return; preserve this behavior. Leaflet's basemap is visual context, not agricultural evidence.

## Provider verification boundary

All fourteen reviewed adapters exist. Prior backend evidence records thirteen enabled/live-tested provider operations and fourteen enabled FieldOps skills (including the combined skill), with Kindwise disabled pending credit authorization. Those are saved results, not proof of current office availability. Runtime Home availability must come from the current registry, not this table or `f-test`. NASA POWER MCP is an alternative access path to NASA POWER.

For individual adapter/tool/skill/fixture/live/enablement evidence see `backend/reports/verified_skill_activation.json`, `verified_registry_state.json`, `provider_inventory.json` and `VERIFIED_API_INTEGRATION_REPORT.md`. New runtime reads and Phase 1 test outcomes are recorded in the delivery section when verified.

## Environment and blockers

- Frontend commands: `npm run dev` (5175), `npm run check`, `npm run test:e2e`. Existing routes use URL hashes; Home remains mounted when visiting other pages. No frontend login/session system existed.
- Backend: FastAPI API (8000), connector worker, PostgreSQL, optional Redis, migration owner and internal MCP service. Reuse the existing Compose deployment and private configuration. Do not seed or modify operational records for a demo.
- CORS defaults omit 5175; use Vite's same-origin `/backend` development proxy instead of broadening production CORS. Hosted deployments need an equivalent reverse proxy or explicitly configured allowed origin.
- Docker Desktop was stopped at initial inspection. Starting the existing services is operational verification, not permission to seed data. Previous checks show the live Gemini key missing; a model call must be reported blocked if that remains true. Local Qwen must not be selected simply to make a demonstration pass.
- The authorized local setup identity has no known interactive password. Do not reset it, mint a development bearer token into the browser, or create an officer without approval. Browser integration uses the existing login form; full-stack tests use a disposable labelled fixture database.

## Phase 1 implementation boundary

Added a read-only `/api/v1/companion/context` projection and optional recorded progress on the existing job read route. Reused existing job creation, execution, cancellation, image upload and evidence routes. Preserved authentication, model choice, Qwen advisory rules, review/release and registry policies. There is no new scheduler, geospatial database, conversation executor or message-delivery service.

Phase 2 requires the explicit instruction **“Proceed to Phase 2 — Plugins integration.”**

## Per-provider evidence matrix

Snapshot source: `backend/reports/home_operational_audit.json`. All rows have an implemented adapter, registered tool and registered skill. Enabled means the current audited office registry, not a guarantee of reachability. Saved live validation belongs to the prior backend integration work; no fresh provider/model investigation was performed in this phase.

| Provider | Adapter / tool / skill | Fixture or unit coverage established | Saved backend live check | Enabled / Home registry |
| --- | --- | --- | --- | --- |
| Open-Meteo | Yes / yes / yes | HTTP transport and combined LangGraph/browser run | VALID | Yes / available |
| iSDAsoil | Yes / yes / yes | HTTP transport, combined run and HTTP503 partial path | VALID | Yes / available |
| NASA POWER | Yes / yes / yes | Parser/normalization; not complete request coverage | VALID | Yes / available |
| CHIRPS | Yes / yes / yes | Request, asynchronous poll/resume | VALID | Yes / available |
| FAO FPMA | Yes / yes / yes | Dedicated positive operation fixture coverage not established | VALID | Yes / available |
| WFP prices / HDX HAPI | Yes / yes / yes | Schema/contract validation | VALID | Yes / available |
| EPPO | Yes / yes / yes | HTTP fixture, executor and graph | VALID | Yes / available |
| FAO locust | Yes / yes / yes | Dedicated positive operation fixture coverage not established | VALID | Yes / available |
| FAO WaPOR | Yes / yes / yes | Range reader and no-data behavior | VALID | Yes / available |
| FAO GAEZ | Yes / yes / yes | TIFF extraction and executor fixture | VALID | Yes / available |
| FAO ASIS | Yes / yes / yes | Normalized evidence contract | VALID | Yes / available |
| Google Earth Engine | Yes / yes / yes | Credential boundary; numerical success not fixture-verified here | VALID | Yes / available |
| Kindwise | Yes / yes / yes | Private image, receipt and executor fixtures | NOT_RUN_CREDIT_AUTHORIZATION_REQUIRED | No / unavailable |
| OpenRouteService | Yes / yes / yes | Scope and routing contract | VALID | Yes / available |

## Delivery and verification

The newer frontend now has authenticated live Home, approved runtime skill controls, bounded authorized plot selection, explicit consent, actual durable jobs, recorded invocation progress, cancellation/recovery, evidence provenance and numerical charts. Existing Leaflet geometry/layers and demo Home remain; other pages retain local drafts/demo behavior. The token and live session stay in memory. No automatic fallback, provider secrets, fabricated agricultural values, model switch or operational seeds were introduced.

| Feature | Frontend | Backend | Integration | Next action |
| --- | --- | --- | --- | --- |
| Map and farms | Authorized points/details; local rectangle filtering | Office projection implemented | Fixture browser verified | Operational login; server spatial queries deferred |
| AI investigations | Explicit skill/task/consent; real polling/cancel | Existing LangGraph executor reused | Actual backend + fixture model/providers verified | Configure authorized live model before claiming milestone |
| Agricultural skills | Approved enabled version/input display | Existing registry/policy retained | Contract and scope checks passed | Provider-specific live checks remain separate |
| Evidence | Actual sources, classifications, tables/charts, partial errors | Existing scoped store | Success/partial browser verified | Large-office performance unmeasured |
| Plugins / Skills management | Local catalog/drafts unchanged | Existing routes unchanged | Deferred | Explicit Phase 2 instruction |
| Monitoring | Local drafts/demo unchanged | No scheduler added | Deferred | Later phase |
| Outreach | Local drafts/demo unchanged | No delivery added | Deferred | Later phase |

Verification on 2026-11-17:

- Frontend `npm run check`: typecheck, lint and production build passed; **97 unit tests passed**.
- Backend targeted regression: **62 passed**, including **4 new Home tests**. JUnit artifacts: `backend/validation/home-backend-regression.xml`, `home-integration.xml`.
- Dedicated full-stack Home browser suite: **4 passed**, using actual login, SQLite, LangGraph worker, HTTP provider fixtures and persisted evidence. Covers two-provider successful run/navigation, mobile layout, HTTP503 partial evidence and backend cancellation.
- Existing default browser suite: **29 passed, 4 skipped**. Skips are the dedicated Home backend suite, intentionally run separately with its isolated server.
- Operational read-only checks: readiness **HTTP200**, unauthenticated context **HTTP401**, two saved plots both synthetic; 23 registered skills and 17 available in the inspected registry. No operational records seeded/reset.
- Both repositories passed `git diff --check`. Exact-value scanning of 37 changed files against seven local environment secrets found zero matches; this is a bounded check, not a comprehensive security audit.
- Live model remains blocked: Gemini key and explicit model missing, model execution flag false. Model reachability is unverified. No fresh paid Kindwise or Earth Engine request was made. Existing model/provider/Qwen policies were not changed to make a demonstration pass.

The real agricultural milestone is therefore **not yet demonstrated with a live model and real farm data**. Phase 1 implementation is reviewable; it must not be described as a completed live deployment. The full-stack fixture model selects actual approved tools but does not establish natural-language reasoning quality. Photo upload and every individual provider are not all browser-tested. Basemap tile loading depends on external tile servers and is independent of agricultural evidence.

The frontend [run guide](../agrilo-fieldops-frontend/docs/PHASE1_HOME_INTEGRATION.md) contains exact commands, routes, walkthrough, persistence and security/scientific limitations. Remaining backend capabilities include server spatial intersection, shared conversation, image retrieval and Home pagination. No Phase 2 work, new commit or push is included.



## Changed-file inventory

Updated after the requested frontend retirement. Paths are relative to the named repository; removed paths are explicitly marked. Ignored local artifacts are excluded. See [workspace structure](WORKSPACE_STRUCTURE.md) for the retirement verification and local parent-level workspace files.

### AgriRoots

- `.github/workflows/verify.yml`
- `ARCHITECTURE.md`
- `EVALS.md`
- `README.md`
- `THIRD_PARTY_NOTICES.md`
- `backend/src/api/routes/integrations.py`
- `backend/src/main.py`
- `docs/README.md`
- `docs/code-guide.md`
- `docs/configuration.md`
- `docs/getting-started.md`
- `docs/testing.md`
- `frontend/.env.example` (removed)
- `frontend/.gitignore` (removed)
- `frontend/README.md` (removed)
- `frontend/android/.gitignore` (removed)
- `frontend/android/app/.gitignore` (removed)
- `frontend/android/app/build.gradle` (removed)
- `frontend/android/app/capacitor.build.gradle` (removed)
- `frontend/android/app/proguard-rules.pro` (removed)
- `frontend/android/app/src/androidTest/java/com/getcapacitor/myapp/ExampleInstrumentedTest.java` (removed)
- `frontend/android/app/src/main/AndroidManifest.xml` (removed)
- `frontend/android/app/src/main/java/com/agriroots/app/AgriRootsPermissionsPlugin.java` (removed)
- `frontend/android/app/src/main/java/com/agriroots/app/MainActivity.java` (removed)
- `frontend/android/app/src/main/res/drawable-land-hdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-land-mdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-land-xhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-land-xxhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-land-xxxhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-port-hdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-port-mdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-port-xhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-port-xxhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-port-xxxhdpi/splash.png` (removed)
- `frontend/android/app/src/main/res/drawable-v24/ic_launcher_foreground.xml` (removed)
- `frontend/android/app/src/main/res/drawable/ic_launcher_background.xml` (removed)
- `frontend/android/app/src/main/res/drawable/splash.png` (removed)
- `frontend/android/app/src/main/res/layout/activity_main.xml` (removed)
- `frontend/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` (removed)
- `frontend/android/app/src/main/res/mipmap-anydpi-v26/ic_launcher_round.xml` (removed)
- `frontend/android/app/src/main/res/mipmap-hdpi/ic_launcher.png` (removed)
- `frontend/android/app/src/main/res/mipmap-hdpi/ic_launcher_foreground.png` (removed)
- `frontend/android/app/src/main/res/mipmap-hdpi/ic_launcher_round.png` (removed)
- `frontend/android/app/src/main/res/mipmap-mdpi/ic_launcher.png` (removed)
- `frontend/android/app/src/main/res/mipmap-mdpi/ic_launcher_foreground.png` (removed)
- `frontend/android/app/src/main/res/mipmap-mdpi/ic_launcher_round.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xhdpi/ic_launcher.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xhdpi/ic_launcher_foreground.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xhdpi/ic_launcher_round.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxhdpi/ic_launcher_foreground.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxhdpi/ic_launcher_round.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_foreground.png` (removed)
- `frontend/android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.png` (removed)
- `frontend/android/app/src/main/res/values/ic_launcher_background.xml` (removed)
- `frontend/android/app/src/main/res/values/strings.xml` (removed)
- `frontend/android/app/src/main/res/values/styles.xml` (removed)
- `frontend/android/app/src/main/res/xml/file_paths.xml` (removed)
- `frontend/android/app/src/test/java/com/getcapacitor/myapp/ExampleUnitTest.java` (removed)
- `frontend/android/build.gradle` (removed)
- `frontend/android/capacitor.settings.gradle` (removed)
- `frontend/android/gradle.properties` (removed)
- `frontend/android/gradle/wrapper/gradle-wrapper.jar` (removed)
- `frontend/android/gradle/wrapper/gradle-wrapper.properties` (removed)
- `frontend/android/gradlew` (removed)
- `frontend/android/gradlew.bat` (removed)
- `frontend/android/settings.gradle` (removed)
- `frontend/android/variables.gradle` (removed)
- `frontend/capacitor.config.json` (removed)
- `frontend/eslint.config.mjs` (removed)
- `frontend/index.html` (removed)
- `frontend/jsconfig.json` (removed)
- `frontend/package-lock.json` (removed)
- `frontend/package.json` (removed)
- `frontend/postcss.config.mjs` (removed)
- `frontend/public/file.svg` (removed)
- `frontend/public/globe.svg` (removed)
- `frontend/public/img-4.jpg` (removed)
- `frontend/public/next.svg` (removed)
- `frontend/public/vercel.svg` (removed)
- `frontend/public/window.svg` (removed)
- `frontend/src/App.jsx` (removed)
- `frontend/src/app/alerts/page.jsx` (removed)
- `frontend/src/app/auth-options/page.jsx` (removed)
- `frontend/src/app/globals.css` (removed)
- `frontend/src/app/main-page/page.jsx` (removed)
- `frontend/src/app/onboarding/farming/page.jsx` (removed)
- `frontend/src/app/onboarding/language/page.jsx` (removed)
- `frontend/src/app/onboarding/location/page.jsx` (removed)
- `frontend/src/app/page.jsx` (removed)
- `frontend/src/app/settings/page.jsx` (removed)
- `frontend/src/app/workspace/RunPanel.jsx` (removed)
- `frontend/src/app/workspace/page.jsx` (removed)
- `frontend/src/app/workspace/released.jsx` (removed)
- `frontend/src/app/workspace/workspace.css` (removed)
- `frontend/src/components/chat/ChatArea.jsx` (removed)
- `frontend/src/components/chat/ChatInput.jsx` (removed)
- `frontend/src/components/chat/ChatSidebar.jsx` (removed)
- `frontend/src/components/chat/MessageBubble.jsx` (removed)
- `frontend/src/components/ui/button.jsx` (removed)
- `frontend/src/components/ui/card.jsx` (removed)
- `frontend/src/components/ui/input.jsx` (removed)
- `frontend/src/components/ui/label.jsx` (removed)
- `frontend/src/contexts/AuthContext.jsx` (removed)
- `frontend/src/contexts/LanguageContext.jsx` (removed)
- `frontend/src/lib/account.js` (removed)
- `frontend/src/lib/alerts.js` (removed)
- `frontend/src/lib/api.js` (removed)
- `frontend/src/lib/chat.js` (removed)
- `frontend/src/lib/errors.js` (removed)
- `frontend/src/lib/nativePermissions.js` (removed)
- `frontend/src/lib/profile.js` (removed)
- `frontend/src/lib/utils.js` (removed)
- `frontend/src/lib/voice.js` (removed)
- `frontend/src/lib/workspace.js` (removed)
- `frontend/src/main.jsx` (removed)
- `frontend/vercel.json` (removed)
- `frontend/vite.config.js` (removed)
- `scripts/browser/package-lock.json` (removed)
- `scripts/browser/package.json` (removed)
- `scripts/browser/workflow.mjs` (removed)
- `scripts/demo.py` (removed)
- `scripts/verify_clean_start.py` (removed)
- `backend/reports/home_operational_audit.json`
- `backend/scripts/check_home_browser.py`
- `backend/src/api/routes/companion.py`
- `backend/tests/home_browser_server.py`
- `backend/tests/home_fixture.py`
- `backend/tests/test_home_integration.py`
- `backend/validation/home-backend-regression.xml`
- `backend/validation/home-integration.xml`
- `docs/FRONTEND_BACKEND_INTEGRATION_AUDIT.md`
- `docs/WORKSPACE_STRUCTURE.md`
- `scripts/README.md`
- `scripts/legacy/README.md`
- `scripts/legacy/browser/package-lock.json`
- `scripts/legacy/browser/package.json`
- `scripts/legacy/browser/workflow.mjs`
- `scripts/legacy/demo.py`
- `scripts/legacy/verify_clean_start.py`

### agrilo-fieldops-frontend

- `.env.example`
- `.gitignore`
- `README.md`
- `docs/FRONTEND_BACKEND_CONTRACT.md`
- `src/app/App.tsx`
- `src/app/HomeWorkspace.tsx`
- `src/components/map/CoordinateWidget.tsx`
- `src/components/map/FieldOpsMap.tsx`
- `vite.config.ts`
- `.github/workflows/verify.yml`
- `docs/PHASE1_HOME_INTEGRATION.md`
- `docs/contracts/home.openapi.json`
- `e2e/home-backend.spec.ts`
- `playwright.home.config.ts`
- `src/api/home-api.ts`
- `src/api/home-contracts.ts`
- `src/app/LiveHomeWorkspace.tsx`
- `src/components/home/EvidencePanel.tsx`
- `src/components/home/InvestigationControls.tsx`
- `src/components/home/InvestigationResults.tsx`
- `src/components/map/map-binding.ts`
- `src/features/home/evidence.ts`
- `src/state/home-store.ts`
- `src/state/useHome.ts`
- `src/styles/home-live.css`
- `tests/home-fixtures.ts`
- `tests/home.test.ts`
