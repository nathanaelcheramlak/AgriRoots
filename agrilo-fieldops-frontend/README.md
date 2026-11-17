# AgriLo FieldOps — independent frontend test

The Leaflet-first frontend inside the AgriRoots repository, alongside `backend/`. This directory has its own package, lockfile, configuration, browser storage key, and port. Demo mode remains the default. Explicit HTTP mode connects Home, Plugins and Skills to the existing AgriRoots backend through a development proxy. It does not read sibling environment files.

This is now the only active frontend. The old `AgriRoots/frontend` and its Android wrapper were retired; backend history and services remain intact. See the [workspace structure](../docs/WORKSPACE_STRUCTURE.md). The root repository workflow runs frontend checks, demo browser regression and layout checks from this folder. The Home/Plugins/Skills fixture runner uses the backend in the same checkout.

The frontend adapts [AgroSphere](https://github.com/Leoul39/AgroSphere)'s map sidebar, coordinate widget, report layout, and original CSS modules. All workspaces share AgriLo's charcoal theme through `src/styles/workspace-theme.css`. Its Leaflet satellite configuration, click-coordinate selection, fly-to behavior and zoom-dependent geographic labels are adapted to the FieldOps use case. See [source attribution and MIT notice](THIRD_PARTY_NOTICES.md).

## Start (PowerShell)

Requires Node.js 22.12+ (Node 24 supported). No API keys or backend required.

```powershell
cd C:\Users\fraol\Documents\Agri-roots\AgriRoots\agrilo-fieldops-frontend
npm ci
npm run dev
```

Open **http://127.0.0.1:5175/**. The independent production preview uses port 4175:

```powershell
npm run build
npm run preview
```

Default mode is `mock`; `.env` is optional. To configure it:

```powershell
Copy-Item .env.example .env
# Edit .env, then restart the dev server.
```

Never put secrets in `VITE_*` variables: these are public client configuration. `VITE_API_MODE=http` connects Home, Plugins and Skills to actual authenticated backend routes. See the [Home guide](docs/PHASE1_HOME_INTEGRATION.md), [Plugins guide](docs/PHASE2_PLUGINS_INTEGRATION.md) and [Skills guide](docs/PHASE3_SKILLS_INTEGRATION.md). Plugins preserves local drafts with explicit migration; Monitoring and Outreach retain local demo/draft behavior. The older proposed contract describes the historical demo adapter only.

## Manual demo

### Plugins (phase one)

Use the **Plugins** rail item or open **http://127.0.0.1:5175/#plugins**. Browse 22 agricultural providers, search or filter by source, and save catalog drafts or add your own MCP/API configuration. Installed starts empty; saved entries are labeled **Saved locally**, **Not connected**, **Not submitted**, and **Not enabled**. Editing, removal and reload persistence work locally. No credentials or live connections are created.

**Home** returns to the current map, selected farm, filters, analysis, assistant session and expanded map state. Pending screening and replies continue while Plugins is open. See [Plugins design, safety and future service mapping](docs/PLUGINS_FRONTEND.md).

### Monitoring

Open **http://127.0.0.1:5175/#monitoring** or choose Monitoring in the rail. Create a local monitor with the seven-step wizard: purpose, farm scope, example capabilities, timezone/recurrence, editable AND/OR thresholds, outputs and review. Edit, duplicate, pause and delete saved drafts. Home retains its workspace while Monitoring is open.

Four opt-in synthetic scenarios demonstrate rainfall warnings, crop photo review, missing submissions and partial satellite coverage. Inspect source evidence, history, illustrative crop comparisons and a downloadable sample report. Farmer feedback can be edited and reviewed locally with version-specific decisions. Scheduling, provider calls, diagnosis and delivery require future backend services. Selected sample images stay in memory and are never persisted. See the [Monitoring walkthrough and integration notes](docs/MONITORING_FRONTEND.md).

### Outreach

Open **http://127.0.0.1:5175/#outreach** to prepare local communication campaigns. The six-step wizard covers purpose/source, paginated recipient selection, channels, guidance editing, advisory groups and review. The 2,000-person synthetic dataset demonstrates deduplication, consent/contact exclusions and group exceptions. Edit weekly actions, preserve original observations alongside officer corrections, and preview SMS, voice scripts, email and messaging.

Start with **Prepare Farmer Guidance** on Home, **Prepare Outreach** on a Monitoring result, or **Prepare Feedback in Outreach** after writing crop-photo notes. Local decisions bind to exact saved versions and are explicitly **not valid for delivery**. Sample delivery history and response follow-ups remain separate from real provider activity. All channels are not configured, no photos/contacts/credentials are collected, and no messages are sent. See the [Outreach walkthrough, privacy and future backend boundary](docs/OUTREACH_FRONTEND.md).

### Map and officer workspace

1. Choose **Try demo area**. This selects a rectangle near Adama containing exactly 12 fixed synthetic farms. Screening takes about one second and reports partial evidence coverage.
2. Alternatively choose the dashed rectangle tool, then click two opposite corners near Adama. Editing uses the pencil tool: drag a corner, then click the checkmark. Each completed edit cancels old work and starts one debounced screening. Panning and zooming never screen an area.
   You can also click a coordinate on the satellite map, or enter LAT/LNG, set the square area width in kilometres, and choose **Analyze area**. This constructs and displays a real geographic rectangle before screening; a point is never silently substituted for an area.
3. Select a marker or farm row. Inspect coordinates, current crop, planting date, irrigation, risk reasons, soil, rainfall, candidate constraints, and source records. F-007 has illustrative Sorghum/Teff candidates; F-008 has Vegetables/Maize candidates. F-009 has missing soil/rainfall and unknown risk, with no candidate crops.
4. Open **Assistant** and try `Show high-risk farms`: the map shows 3 markers. Open **Farms** to see the same 3 of 12 records. `Clear filters` restores all 12. Try `Zoom to farm F-007`, `Show only maize farms`, `Which farms are candidates for sorghum?`, `Explain why Farm F-007 is high risk`, or `Summarize this area`.
5. Choose **Prepare advisory draft** on a farm. Enter an officer name in Advisories, submit for local review, then approve or reject. Drafts and review history survive reload in this browser. Approval sends nothing.
6. Use the trash tool to clear the area. This also clears farm details, results, filters, and chat context; drafts remain saved. **Clear filters** changes filters only. **Reset view**, **Fit selection**, and **Fit visible farms** are distinct map actions.

The map layer button switches between **Satellite** (the reference frontend's Google imagery) and **Street** (OpenStreetMap) without clearing the selected area. Country/region/city context follows AgroSphere's zoom levels, while farm-level zoom hides those labels. Reference administrative boundaries are illustrative, not surveyed farm boundaries.

Choose **Expand map** above the map for a 50/50 desktop layout: a larger, taller map on the left and the extension officer workspace on the right. **Compact map** restores the sidebar layout. Selection, filters and current results are preserved. On mobile, expansion makes the map taller while keeping the officer workspace below it.

The map has keyboard-focusable controls and markers. At small widths, the panel stacks below the map and scrolls independently. Area boundaries and marker layers can be toggled; unavailable soil/rainfall/satellite/pest overlays are explicitly labeled.

## Checks

```powershell
npm run typecheck
npm run lint
npm test
npm run build
npx playwright install chromium
npm run test:e2e
npm run test:layout
```

`npm run check` runs typechecking, lint, unit/component tests, and the build. Playwright starts/reuses port 5175, exercises real Geoman drawing and corner editing, and writes screenshots/traces to ignored `test-results/` and a report to `playwright-report/`. Browser tests use desktop and mobile viewports; no agricultural API calls are involved.

`npm run test:layout` starts an isolated HTTP-mode frontend on port 5177 with browser-intercepted test responses. It checks normal-zoom Home layouts at 1366×768, 1280×600, 820×720 and mobile 390×844, the expanded map, long results, consistent workspace surfaces and form controls, and preservation of Home state during navigation. It uses no real office credentials or provider calls. Desktop Home keeps its question and action visible while the map pane and results scroll separately; mobile uses normal page scrolling.

On this Windows machine, Application Control blocked the newly downloaded Chromium 1255 DLL. The complete browser suite was successfully executed with the existing permitted Chromium 1208 installation, without changing Windows policy:

```powershell
$env:PLAYWRIGHT_EXECUTABLE_PATH='C:\Users\fraol\AppData\Local\ms-playwright\chromium-1208\chrome-win64\chrome.exe'
npm run test:e2e
```

You can use `PLAYWRIGHT_EXECUTABLE_PATH` for another permitted Chromium installation, or leave it unset to use Playwright's bundled browser. See [verification notes](docs/VERIFICATION.md) for observed results.

Developer fixture scenarios: set `VITE_DEMO_SCENARIO=partial` to simulate rainfall failure (risks become unknown and candidates are withheld), or `error` to exercise the failed-screening/retry UI. Restart Vite after changing these. Empty areas are genuine spatial queries: draw outside the fixed fixture footprint. There is no public control claiming that these scenarios represent live monitoring.

## Code map

| Location | Responsibility |
| --- | --- |
| `src/app/App.tsx`, `src/app/HomeWorkspace.tsx` | Shared addressable workspace navigation and preserved AgroSphere-derived Home |
| `src/styles/agrosphere-base.css`, `src/styles/agrosphere-fieldops.css`, `src/styles/fieldops-panels.css`, `src/styles/fieldops-responsive.css` | Original dark palette, adapted workflow styling and mobile layout |
| `src/components/intelligence/IntelligencePanel.module.css` | Original AgroSphere report/card styles |
| `src/components/map/CoordinateWidget.tsx`, `GeographicContext.tsx`, `map-config.ts` | Coordinate-to-area workflow, six zoom label tiers, satellite/street configuration |
| `src/components/map/FieldOpsMap.tsx` | Real Leaflet/Geoman geometry, markers, controls, layer visibility, attribution |
| `src/lib/geo.ts` | Validated full-precision WGS84 selection, bbox, spatial point inclusion |
| `src/state/store.ts` | Shared map/panel/chat state, cancellation, debouncing, query caching, review actions |
| `src/api/` | Strict Zod contracts, mock and HTTP adapters, cancellable background-job polling contract |
| `src/demo/synthetic-farms.ts` | Fixed 12-farm geography, differentiated fixture profiles, missing-data example |
| `src/features/assistant/parser.ts` | Bounded deterministic commands, no LLM or arbitrary execution |
| `src/features/advisories/local-drafts.ts` | Local draft creation/persistence with validated review history |
| `src/features/outreach/`, `src/components/outreach/` | Campaigns, paginated synthetic recipient scope, sourced guidance, channel previews, exact-version demo review and local response follow-up |
| `src/components/sidebar/`, `src/components/farms/` | Overview, farms, evidence/candidates, assistant, advisory review |
| `tests/`, `e2e/` | Geometry, state races, adapters, components and actual browser interaction |

## Intentional limits

- All agricultural records, risks, weather/soil values, crop candidates, and simulated analysis stages are synthetic. Evidence fixtures are dated July 2026 and explicitly do **not** describe current conditions. The screening timestamp records local execution, not new evidence acquisition.
- Candidates are illustrative, unvalidated options for officer/agronomist comparison. There are no yield forecasts, confidence percentages, disease diagnoses, pesticide or fertilizer prescriptions.
- No FastAPI service, LangGraph agent, MCP server, database, live agricultural API, photo upload/diagnosis, authentication, farmer communications, or consequential external actions are implemented.
- Named review is a local placeholder, not authenticated approval. Storage is browser-local under `agrilo-fieldops:isolated-demo-drafts:v1`; at most 100 drafts are retained. Private browsing/storage restrictions can prevent persistence; the UI reports this.
- Point inclusion is **centroid inside, boundary inclusive**. Only one axis-aligned rectangle is supported. Maximum 2,500 km² and 2° per side; antimeridian-spanning selections are not supported. Production polygon inclusion could use `ST_Intersects` behind the adapter.
- The HTTP adapter is a proposed integration boundary. Server auth, pagination beyond 100 farms, validation of real agronomic rules and real analytical overlay discovery remain future integration work. Advisory creation/review remains disabled in HTTP mode.
- The default satellite layer uses the same public Google tile endpoint as AgroSphere, upgraded to HTTPS. This is not a configured Maps Platform API and no production support, permission, quota or availability guarantee is asserted. Configure a licensed imagery provider using `VITE_SATELLITE_TILE_URL` and `VITE_SATELLITE_ATTRIBUTION` before production deployment. Imagery is visual context only; it does not supply NDVI or validate crop advice.
- Satellite and Street tiles need internet. Tile failure/loading is visible and geometry/demo workflows still operate. Street mode uses attributed OpenStreetMap tiles. Its public server offers no production SLA; configure `VITE_TILE_URL` and `VITE_TILE_ATTRIBUTION` for another permitted provider. No offline download or bulk prefetch is implemented.

Implementation references: [React Leaflet map API](https://react-leaflet.js.org/docs/api-map/), [Leaflet](https://leafletjs.com/), [Geoman drawing](https://geoman.io/docs/leaflet/modes/draw-mode), [Geoman editing](https://geoman.io/docs/leaflet/modes/edit-mode), [OSM tile policy](https://operations.osmfoundation.org/policies/tiles/). React Leaflet 5's React 19 / Leaflet 1.9 peers were checked before installation. Dependency versions are recorded in `package-lock.json`.
