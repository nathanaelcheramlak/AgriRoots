# Phase 1 Home integration

Implemented in the newer `agrilo-fieldops-frontend`. Phase 0 audit and Phase 1 Home code are complete; the operational live-model milestone is blocked by missing backend model configuration and an available interactive officer login. No operational account, farm or provider credential was created or reset. No Phase 2 work was started.

## Current behavior

HTTP Home uses the existing officer password login, keeps its bearer token in memory, and loads an office-scoped projection of authorized farm records, approved enabled skills, supported inputs and configured model readiness. Selecting a farm, panning, typing or drawing a rectangle does not invoke a provider or model. The rectangle filters already-authorized farm points locally; it is not a server spatial query or a surveyed boundary.

An explicit submission sends a task, authorized plot IDs, supported parameters, consent flags and a unique request key to the existing skill-run route. The backend reauthorizes records, binds their coordinates and uses its existing durable LangGraph worker and controlled tool executor. Home polls actual job/invocation states, retrieves results and evidence, and preserves partial failures. An uncertain submission can recover using the same request key. Cancellation uses the backend cancellation route; it cannot undo a provider operation already dispatched.

Home renders recorded answers, tool outcomes, source references, evidence IDs, observation periods, retrieval dates, units, soil depths/uncertainty and limitations. Charts use numerical evidence only. Market series are separated by market, commodity, currency, unit and price type. Missing data never creates an agricultural risk score, crop recommendation or numerical chart. The recorded crop comes from the latest saved season and is not independently verified as current. Basemap tiles are visual context and may fail independently of agricultural evidence; the map displays a warning and offers Street tiles.

Map state, farm selection, task controls, jobs and local conversation identity remain mounted across navigation. Each submission is an independent server investigation; no shared server conversation history exists. Reload/logout clears the memory-only session and local conversation, although submitted jobs remain durable in the backend. No provider credential, model key, image bytes or bearer token is written to browser storage.

## Feature matrix

| Feature | Frontend state | Backend state | Integration state | Next action |
| --- | --- | --- | --- | --- |
| Farm map | Existing Leaflet/Geoman reused; authorized points, local filter, details | Office records and minimal Home projection | Verified with disposable authorized synthetic records | Confirm operational officer login; server spatial queries remain absent |
| AI investigations | Registry controls, explicit consent, real status, cancel/recover | Existing LangGraph jobs and executor | Real backend flow verified with explicit fixture model/providers | Supply authorized backend model configuration for live milestone |
| Agricultural skills | Displays approved enabled versions and unavailable reasons | Existing registry and secure executor | Supported parameter mapping; no invented endpoints | Verify chosen runtime skill/input availability |
| Evidence/charts | Actual envelope, source links, quality, tables/charts | Existing office-scoped evidence store | Successful and partial paths browser verified | Larger-office/data-volume testing remains |
| Photo upload | Opaque image reference, size/type validation, credit consent | Existing private image and receipt routes | Backend image fixtures previously verified; new browser upload path not exercised | Kindwise remains disabled pending explicit credit authorization |
| Plugins / Skills management | Existing local catalog/drafts; Home only lists executable skills | Existing management/review routes unchanged | Management integration deferred | Wait for Phase 2 instruction |
| Monitoring | Existing local drafts/demo | No integration added | Deferred | Later phase |
| Outreach | Existing local drafts/demo; sends nothing | No integration added | Deferred | Later phase |

## Routes actually used

| Method / path | Purpose |
| --- | --- |
| `POST /api/auth/login` | Existing password login |
| `GET /api/v1/companion/context` | New read-only authorized Home projection |
| `POST /api/v1/skills/{id}/runs` | Existing durable investigation submission |
| `GET /api/v1/connector-jobs/{id}?include_progress=true` | Existing job read, optional recorded invocation projection |
| `GET /api/v1/runs/{id}/results` | Existing results |
| `GET /api/v1/evidence/{id}` | Existing evidence envelope |
| `POST /api/v1/runs/{id}/cancel` | Existing backend cancellation |
| `POST /api/v1/image-assets` | Existing private image upload |

The [OpenAPI subset](contracts/home.openapi.json) was exported from the actual running backend. Existing job/evidence responses are not fully typed in its OpenAPI; `src/api/home-contracts.ts` validates them at runtime, supplemented by real backend/browser checks. No backend migrations or model/execution policy changes were required. Only context and optional job progress were added to production routes.

## Run and demonstrate

1. Start the existing AgriRoots API and connector worker with their authorized configuration. Preserve the existing private environment and databases. API defaults to `http://127.0.0.1:8000`.
2. In PowerShell:

```powershell
cd C:\Users\fraol\Documents\Agri-roots\AgriRoots\agrilo-fieldops-frontend
npm ci
$env:VITE_API_MODE = 'http'
$env:VITE_API_BASE_URL = '/backend'
$env:FIELDOPS_BACKEND_URL = 'http://127.0.0.1:8000'
npm run dev
```

3. Open `http://127.0.0.1:5175/` and use an existing authorized officer's phone/password. The proxy handles development origin routing; hosted deployments need an equivalent reverse proxy or an explicitly allowed origin. Do not put secrets in any `VITE_*` value.
4. Inspect office/model readiness. Select an authorized farm and an available skill. For a combined investigation, choose the enabled skill with the needed weather/soil capabilities and provide any actual required dates. Per-plot tools require exactly one selected plot; routing requires two authorized endpoints. The backend permits at most five plot IDs.
5. Review the explicit network/model authorizations, ask an agricultural question, and submit once. Observe real queued/running/terminal states and recorded operations; inspect the returned answer, source/evidence references, numerical data and limitations.
6. Navigate to Plugins and back: the same Home/map/job remains. Refresh/resume a stopped polling session or cancel an active job using its controls. Other pages remain local demos/drafts.

To return to the default demo, remove `VITE_API_MODE` from the process environment (or set it to `mock`) and restart Vite. HTTP errors never trigger demo fallback.

At the audited operational snapshot, health returned HTTP 200 and unauthenticated Home context returned HTTP 401. Two saved plots were synthetic. Gemini had no configured model/key and model execution was disabled. Do not claim the live agricultural milestone until an authorized login and an explicitly configured, permitted model are available. Existing Qwen advisory behavior and the chosen model provider were preserved.

## Verification (2026-11-17)

| Check | Actual result / boundary |
| --- | --- |
| `npm run check` | Typecheck/lint/build passed; 97 unit tests passed |
| Backend targeted regression | 62 tests passed, including the 4 new Home integration tests |
| Existing browser suite | 29 passed; 4 dedicated backend tests skipped in default mock mode |
| Dedicated Home full-stack suite | 4 passed: authorized login/job/two-provider evidence/navigation, mobile, real provider HTTP 503 partial result, backend cancellation |
| Operational read-only checks | Health 200; unauthenticated context 401; current registry/model projection inspected |
| Real cloud model / fresh live provider investigations | Not executed; missing model configuration; no paid Kindwise or Earth Engine calls |

The full-stack suite uses a real disposable FastAPI database, existing auth, durable LangGraph execution, actual HTTP fixture servers and persisted evidence. Its model is an explicitly labelled deterministic fixture, not Gemini/Qwen reasoning or fresh provider data. It never seeds the operational database. Browser screenshots/reports are local ignored test artifacts; basemap availability is not proof of provider success.

Run checks:

```powershell
cd C:\Users\fraol\Documents\Agri-roots\AgriRoots\agrilo-fieldops-frontend
npm run check
npm run test:e2e
cd ..\backend
.\.venv\Scripts\python.exe -m pytest tests/test_home_integration.py -q
.\.venv\Scripts\python.exe scripts/check_home_browser.py
```

The disposable runner requires installed backend test dependencies and frontend Playwright Chromium; it creates its own temporary account/password and cleans up its test database. Backend JUnit results and provider readiness are saved in `AgriRoots/backend/validation/home-*.xml` and `AgriRoots/backend/reports/home_operational_audit.json`. The complete changed-file inventory is in the backend repository audit.

## Remaining limits and next phase

There is no server spatial intersection, surveyed farm overlay, automatic risk/crop scoring, shared server conversation, browser model selector, image download API or Home pagination. Multiple single-plot operations are not silently expanded into bulk jobs. Very large office performance is not benchmarked. Synthetic plots, fixture evidence, cached evidence and failures retain their classifications. Registry availability does not prove provider reachability. Photo upload and each individual provider are not all covered by this phase's four browser scenarios; consult the per-provider audit.

Stop before Plugins integration. The next phase requires the explicit instruction: **“Proceed to Phase 2 — Plugins integration.”**
