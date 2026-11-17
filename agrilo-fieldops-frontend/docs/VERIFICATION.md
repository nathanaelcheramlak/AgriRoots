# Observed verification — 16 November 2026

Verified locally on Windows using Node 24.13.1 and npm 11.8.0, including Home, Plugins, Monitoring and Outreach. Work was confined to `agrilo-fieldops-frontend/`. Existing unrelated changes in `AgriRoots/` and the API evaluation project were left untouched.

| Check executed | Observed result |
| --- | --- |
| `npm run typecheck` | Passed, strict TypeScript |
| `npm run lint` | Passed, no errors or warnings |
| `npm test` | 9 suites, 85 unit/component tests passed |
| `npm run build` | Passed; production assets emitted to `dist/` |
| Browser workflows with permitted Chromium executable override | 29 distinct workflows passed: 21 existing checks and 8 Outreach checks |
| `npm audit --audit-level=low` | 0 vulnerabilities in the resolved dependency tree |
| HTTP request to local app | Served on independent port 5175 |

The initial browser launch using downloaded Chromium 1255 failed because Windows Application Control blocked its Chrome DLL. No policy was modified. The browser suite used the already installed Chromium 1208 executable via the documented `PLAYWRIGHT_EXECUTABLE_PATH` override.

Browser checks exercised actual Leaflet/Geoman rectangle drawing, dragging a real corner to resize, removing selection, the Google satellite basemap/attribution or an explicit tile-error notice, marker and row selection, differentiated candidate details, assistant filters synchronized with markers and rows, a genuine empty area, satellite/street switching while retaining farms, local draft review/persistence, and a 390px mobile viewport with no horizontal overflow. The new coordinate test clicked the real map, acquired LAT/LNG, submitted a 5km-wide area, and verified a 25km² rectangle with the `manual_area` payload. The advisory browser test observed no non-GET requests.

Plugin checks cover catalog availability and independent draft/health/approval/enablement states; custom MCP/API creation, validation, editing and removal; persistence and storage failure; unsupported backend operations without requests; mobile drawers, dialog focus and browser history. Home state remains intact across Plugins navigation, and pending analysis/assistant replies finish while Home is hidden. Direct Plugins entry makes no external requests, and custom endpoints are never contacted. Skills has been removed from navigation; Monitoring replaces Scheduled.

Monitoring checks exercised the complete seven-step wizard, invalid threshold rejection, recurrence/timezone editing, save/reload, duplication, local pause/return-to-draft and deletion. They verified deterministic partial evidence and history filters, sample report download, chronological crop illustrations and comparison, session-only raster intake, version-specific feedback review and invalidation on edit, storage failures, mobile focus/navigation and no horizontal overflow. Pending Home analysis and assistant replies completed while Monitoring was open; the wizard could inspect a Home area snapshot without changing it. Direct Monitoring scenarios and configuration made no external requests; feedback actions transmitted nothing.

Outreach checks exercised the six-step campaign wizard, 2,000-person selection and pagination, agricultural filters, exclusions, source scope, weekly action editing, correction/original preservation, exact-version demo review and invalidation, duplicate/archive/delete, synthetic delivery states, response-note reload persistence, source handoffs and all four channel previews. Direct Outreach workflows made no external requests; no communication was sent. HTML input remained plain text. Unknown variables held review, and real Home IDs were never substituted with synthetic contacts.

The full browser regression run passed 28 workflows. The new Home/Outreach test's pending-chat section incorrectly looked for a quick-action button hidden after existing conversation messages. It was corrected to use the normal composer; that complete workflow then passed separately. All 29 distinct workflows are therefore verified. The initial Plugins component timeout was resolved by testing URL/name paste instead of slow per-character entry; its validation/edit/removal assertions remain intact.

Desktop empty states, campaign setup, groups and review, Monitoring overview/comparison and 390px mobile layouts were rendered and visually inspected. Sidebar collapse/expand and focus-managed mobile drawers were checked. New Outreach/Monitoring code loads on demand.

The Home visual shell, original CSS modules, map label tiers, coordinate interactions, satellite configuration and report presentation were adapted from AgroSphere commit `77070f0615f8b529633f8c2c96ade1378ded057a`. Source attribution and the original MIT notice are preserved in `THIRD_PARTY_NOTICES.md` and `licenses/AgroSphere-MIT.txt`. The Plugins shell, socket icon and components are original AgriLo implementations inspired by the supplied reference images.

Desktop and mobile screenshots were rendered and inspected. Tests retain screenshots in ignored `test-results/`. Build output contains harmless upstream Zod pure-comment annotation notices; compilation and bundling succeed.

Dependency audit findings in initial development-tool versions were fixed before final verification: Vite 7.3.8, Vitest 4.1.12, patched esbuild, and a scoped minimatch override for the TypeScript lint parser. The lockfile captures the tested resolution.

These checks validate the frontend demo and adapters, not real agricultural advice, provider availability, authenticated officer identity, a deployed backend, or field agronomic effectiveness.
