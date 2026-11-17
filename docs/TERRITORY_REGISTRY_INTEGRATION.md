# Territory, Farm Registry and Companion Integration

## Audit of the actual frontend

The new UI was inspected in the standalone frontend served on port 5179, based on commit `4d54677` plus uncommitted territory changes. Its 28 changed/new files were copied into the canonical `AgriRoots/agrilo-fieldops-frontend` without changing the standalone checkout. Existing uncommitted Gemini validation work was preserved. No commit/push is part of this task.

| Operation | Actual pre-integration implementation | Backend gap addressed |
| --- | --- | --- |
| Assigned territory | `territoryService.getAssigned(HomeContext)` read optional metadata that the backend did not supply | Persistent proposals, approval, assignments and authoritative capability metadata |
| Territory proposal | `store.saveTerritory()` saved local geometry only | Explicit authenticated submission; separate administrative review and staff assignment |
| Plot registration | `farmPlotService.prepareRegistration` produced metadata; store saved local IDs | Transactional permanent plot identity, spatial containment, farmer association and crop persistence |
| Farmer registration | `saveFarmer` kept profiles in memory | Independent server farmer identity; optional phone, encrypted contacts and consent metadata |
| Directory | Local filtering/slicing over optional 2,000-profile fixtures | Server-scoped search/count/pagination; contacts excluded |
| Investigation | Only existing Home point IDs were accepted | Registered polygon IDs resolve through the same authorization/execution path |
| History | Home investigation array stayed in memory | Indexed persistent plot/job history and reopening saved evidence |
| Analysis rectangle | Client point filtering | Authorized PostGIS polygon intersection; selection never grants access |

The repository actually used recorded custom revisions 1–5, not Alembic. PostgreSQL 16 originally had no PostGIS. This integration adds an additive revision 6 and an Alembic bridge rather than replacing the migration history. Legacy point-only records retain their IDs and receive no invented boundary or household.

## Architecture and privacy

The hierarchy is office → assigned territory → registered plot → farmer associations → crop seasons/observations → existing investigation jobs/evidence.

New tables: `registry_territories`, `registry_assignments`, `registry_farmers`, `registry_plots`, `registry_farmer_plots`, `registry_seasons`, `registry_observations`, and `registry_plot_runs`. `registry_plots.id` references the canonical `workspace_records.id`. New farmer profiles do not require login accounts or fabricated legacy households. Relationships and assignments retain effective history.

Territories/plots store validated WGS84 Polygon/MultiPolygon GeoJSON and native generated PostGIS geometry columns with SRID 4326, topology/type checks and GiST indexes. Coordinates are `[longitude, latitude]`; rings must close, values must be finite, and self-intersections/antimeridian crossings are rejected. Geometry is bounded to 4,000 vertices/150 KB, minimum 1 m², maximum territory 10,000 km²/plot 1,000 ha. [ST_CoveredBy](https://postgis.net/docs/ST_CoveredBy.html) includes shared boundary edges. [ST_Area(geography)](https://postgis.net/docs/ST_Area.html) measures spheroidal square metres. SQLite checks are development support, not production spatial verification.

Complete plot geometry must fit the assigned territory. Exact duplicates are rejected; overlaps require explicit review acknowledgement and remain flagged. The server records both centroid and an interior sampling point; point tools use the latter, which is not a whole-farm measurement. Territory edits cannot exclude existing registered plots. Plot registration uses an idempotency key; edits use optimistic revisions and territory row locks.

Approval never grants an officer access automatically. `status=assigned` denotes an office-approved territory boundary; officers additionally require an active staff assignment. Office administrators manage their own office's territories. Assignments support manager/reader roles, effective dates and revocation. Viewers/readers cannot register farms. The shared plot resolver, graph/executor reauthorization, job reads and evidence reads check current assignment state. Supplied coordinates, local IDs and localStorage grant no authority.

Farmer contact/household/preference/private-note fields and plot free-text details use the existing encryption service. Map/directory projections omit these fields; administrator-only private contact reads are audited. Farmer names/localities remain searchable within authorized registry scope. Audits record IDs/revisions, not private profile payloads. Official profiles and backend records never enter browser storage.

The user's clarified policy is preserved: **synthetic farm records and actual provider evidence are separate concepts**. A labelled synthetic sample farm can retrieve real approved weather/soil/rainfall/satellite evidence. `classification=live|fixture` describes provider evidence; `input_synthetic` describes the farm. Dates, units, uncertainty, resolution metadata when supplied, response digests and evidence references stay in the existing envelope. Missing provider metadata is not invented.

Real registered farms are supported by the registry and controlled agricultural executor. `CLOUD_MODEL_DATA_POLICY=synthetic_only` remains unchanged: real private farm contexts/coordinates/names/contacts/household identifiers/notes must not reach Gemini. The graph checks this before model construction. It receives only permitted crop/area/structured-observation context and opaque plot references, never farmer/contact/free-text profile details. No provider or model call occurs on registration, map movement or directory search. Real-farm Gemini investigations are honestly blocked under the current policy.

## Endpoint contracts

All paths below are under `/api/v1/registry`, use existing bearer authentication, and derive office/user from membership. No request body selects an arbitrary office. Lists return `items,total,limit,offset`, maximum 100; farmer default 25, plot default 50.

| Method/path | Contract |
| --- | --- |
| GET `/territories` | Assigned territories plus own pending proposals; office admins can review all office proposals |
| POST `/territory-proposals` | `{name,region?,district?,description?,boundary}` → permanent pending territory; no assignment |
| PATCH `/territories/{id}` | Same fields plus `expected_revision`; creator edits pending proposal, admin edits official boundary |
| POST `/territories/{id}/review` | Admin `{expected_revision,decision:approve|reject|deactivate}` |
| GET `/members` | Admin-only staff IDs/roles; no contacts |
| GET/POST `/territories/{id}/assignments` | Admin list/create; POST `{user_id,role?:manager|reader,starts_at?,ends_at?}` |
| DELETE `/assignments/{id}?expected_revision=N` | Audited revocation retaining history |
| GET `/territories/{id}/summary` | Authorized farmer/plot counts and registered area |
| GET `/farmers?territory_id=...&search=...&limit=25&offset=0` | Scoped reference/name/locality search; no private/contact payload |
| POST `/farmers` | `{territory_id,reference,display_name,village?,language?,channel?,consent?,consent_purpose?,phone?,email?,household?,preferences?,notes?,synthetic?}` |
| GET `/farmers/{id}` | Limited authorized profile; `include_private=true` additionally requires administrator and records an audit event |
| PATCH `/farmers/{id}` | Registration fields plus `expected_revision`; omitted private fields preserved; no implicit territory relocation |
| GET `/plots?territory_id=...&bbox=west,south,east,north&limit=100&offset=0` | Indexed authorized spatial intersection; true empty result distinct from failure |
| POST `/territories/{id}/plots` | `{name,geometry,farmer_ids,association_role?,season?,acknowledge_overlaps?,request_key,synthetic?,location?,notes?,observation?}` → permanent plot, safe Home projection and associations |
| GET `/plots/{id}` | Authorized geometry, farmer/current crop context and officer private plot notes |
| PATCH `/plots/{id}` | Registration fields plus `expected_revision`; stable plot identity/history |
| GET/POST `/plots/{id}/crop-seasons` | Paginated history; POST nullable crop, planting/harvest date, stage, irrigation/method, previous crop |
| GET/POST `/plots/{id}/observations` | POST `{provenance,observed_at?,metric,value,unit,source,uncertainty?}` with explicit scientific provenance |
| GET `/plots/{id}/investigations` | Paginated existing job views, current scope rechecked |

Existing `/api/v1/companion/context` adds territory/capability metadata and bounds its initial point page to 100. `?plot_ids=id,...` retrieves up to five explicitly authorized points. Existing `/api/v1/skills/{id}/runs`, `/connector-jobs/{id}`, `/runs/{id}/cancel` and `/evidence/{id}` remain the execution, polling, cancellation and evidence contracts. No second execution engine was created.

Errors: 401 missing login; 403 denied office/assignment/role; 404 absent office-owned record; 409 stale revision, duplicate identity/geometry, conflicting idempotency key or missing overlap acknowledgement; 422 invalid geometry/body. Synthetic marking requires an office administrator and grants no execution privilege.

## Frontend walkthrough

1. Open `http://127.0.0.1:5179/#home` and sign in. No territory is fabricated when none is assigned.
2. **My Territory → Set Up My Territory → Submit territory for approval**. An administrator reviews the boundary, then explicitly assigns an existing officer.
3. That officer's next Home load restores the boundary from PostgreSQL without redrawing it.
4. **Register Farmer** saves an independent profile; phone is optional. **Register Farm Plot** draws a contained parcel, links a farmer, and saves known crop inputs. It returns a permanent ID.
5. Refresh/relogin restores the territory, plot and associations. Select the plot for the existing companion; real-farm Gemini privacy blocks remain visible.
6. **Farm details → Investigations → Open saved findings and evidence** reuses Home polling and the evidence/chart renderer without starting another model/provider run.

The existing dark UI, separate map interaction modes, Home/Plugins/Skills and local geometry drafts remain. Only verified backend capability metadata enables server registration. Local drafts and the 2,000-profile synthetic directory are not silently migrated or uploaded. Map movement is debounced registry querying, not environmental-provider execution. Directory pagination fetches 25 limited profiles. Stale session/territory/search responses are discarded. Tokens remain in memory, so browser refresh requires sign-in again.

## Migration and setup

- Preserve existing volumes and ignored environment/encryption keys. A private `pg_dump -Fc` backup was taken locally before the upgrade.
- Build `backend/Dockerfile.postgis`: it uses the existing PostgreSQL-16 Debian base and installs PostgreSQL/PostGIS from the same repository. An older prebuilt image failed compatibility checks; the corrected deployment uses PostgreSQL **16.16 / PostGIS 3.7**, retaining the original collation family. Its extension was updated and the operational database reindexed. No volumes/accounts/providers were reset.
- Stop API/worker/MCP for the database upgrade, start PostgreSQL, run existing owner setup (`python -m src.cli.connector_setup`), then restart services. Alternatively `alembic upgrade head` uses an owner `MIGRATION_DATABASE_URL`; connector setup still grants restricted app permissions and prepares checkpoints.
- Revision 6 and `alembic/versions/0006_registry_bridge.py` preserve recorded revisions 1–5. The bridge is repeatable. Downgrade refuses destructive data loss; rollback requires a reviewed backup. Never use `docker compose down -v` here.
- Keep `SECRET_ENCRYPTION_KEY` and rotation keys outside Git. Do not regenerate them during deployment or put provider/model credentials into frontend variables.
- Canonical frontend: `npm ci`, `VITE_API_MODE=http`, existing `/backend` proxy, `npm run dev -- --port 5179 --strictPort`. The standalone checkout is retained as source backup.

## Verification and limits

Frontend verification is `npm run check`. Layout/territory browser verification is `npx playwright test --config playwright.layout.config.ts`.

`python scripts/check_registry_browser.py` from backend creates only a uniquely named disposable `agrilo_registry_browser_*` PostGIS database, temporary fixture accounts, loopback fixture providers and a fixture model. Auth/API/SQL/queue/LangGraph/evidence are real application code. Agricultural responses and model reasoning in this acceptance test are **fixtures**, not live observations. No Gemini/paid provider operation or operational-database seeding is performed. External basemap requests are blocked.

Native pytest uses explicitly disposable `agrilo_test`, never operational `agrilo`. XML reports are in `backend/validation/territory-registry-*.xml`. Existing live-Gemini verification remains separately documented in `backend/reports/LIVE_GEMINI_VALIDATION.md`; it is not evidence of a new real-farm cloud run.

### Final verification results (17 November 2026)

| Capability | Implemented | Verification |
| --- | --- | --- |
| Proposals, approval, effective assignments/revocation | Yes | Authenticated API/PostGIS checks and actual browser workflow |
| Farmer persistence, encrypted contacts, paginated directory | Yes | API/private-field tests, 2,000-record directory check and browser refresh/relogin |
| Spatial registration, crop/farmer association, permanent ID | Yes | Native PostGIS containment/area/index tests and browser registration |
| Existing LangGraph execution and source-linked evidence | Yes | Actual browser-to-PostGIS-to-LangGraph workflow with explicitly labelled model/provider fixtures |
| Isolation and real-farm cloud privacy | Yes | Second-office, reader/future assignment/revocation tests; real-farm cloud model blocked before construction |
| Home/Plugins/Skills shared behavior | Preserved | 64 backend regression tests passed; one native-PostGIS-only test skipped in SQLite run |
| Frontend type/lint/build/unit checks | Passed | 127 tests passed; final type/lint check passed after display-label correction |
| Responsive territory/map navigation | Passed | 11 desktop/tablet/mobile territory/layout browser checks |
| Fresh/legacy migration and Alembic bridge | Passed | Included in 18 actual-PostGIS checks; bridge verified repeatable |
| Full registry acceptance browser test | Passed | 1 passed in 17.9 seconds; real application/database, fixture agriculture/model outputs |

The later history compatibility check additionally verifies jobs without the new normalized association remain discoverable through their original stored plot IDs. PostgreSQL uses a GIN index over historical request plot IDs alongside the normalized lookup.

### Remaining limitations and explicit boundaries

- No new live Gemini/agricultural-provider run was performed in this integration. A passing fixture investigation is not live agricultural reasoning. Preserve the separate earlier live-Gemini report and synthetic-only cloud privacy restriction.
- Legacy point-only plots remain valid office-scoped records. Automatic polygon invention, territory reassignment and migration of legacy household/farmer identities are intentionally not performed. Existing IDs/advisories/evidence remain intact.
- The map fetches at most 100 plot polygons per viewport/query. More matches require zooming or API pagination; aggregation/clustering and a bulk map pagination interface are not implemented. The farmer directory does have server pagination.
- Territory API pagination exists; the current switcher loads the first 100 and reports truncation. Advanced assignment role/effective-date editing is available through the API; the basic administrative UI creates manager assignments and supports revocation.
- Server farmer search covers reference/name/locality. The directory's local-only crop/relationship filters are disabled for backend paging until server-side equivalents are implemented.
- Contact verification is not implemented; consent remains explicitly reported/unverified. Private contact retrieval is administrator-only. Blank hidden fields are preserved on profile edit, not treated as an instruction to erase contacts.
- Rectangle drawing remains the existing frontend interaction. Polygon/MultiPolygon persistence is supported by the backend; arbitrary boundary editing requires a richer map editor.
- Model numerical-claim validation remains conservative. Unknown crop dates/observations remain unknown; no agronomic thresholds, diagnoses or pesticide recommendations are inferred from map geometry.
- Monitoring scheduling, Outreach delivery, SMS/email, farmer messaging and automatic advisory release were not implemented.

### Changed-file groups

- New backend domain: `src/registry/{access,geometry,schemas,service}.py`, `src/db/models/farm_registry.py`, `src/api/routes/farm_registry.py`.
- Database/runtime: revision 6, model/migration registration, Alembic config/environment/bridge, `Dockerfile.postgis`, Dockerfile/Compose, dependency locks.
- Shared authorization/execution: existing plot policy, controlled dispatch gate, companion graph/context, integration ownership checks, skill-run history links, legacy workspace record guards.
- Frontend: imported territory/map/components/styles/types; new authenticated `features/territory/backend.ts`; updated store/runtime/forms/directory/admin/details; shared Home API/contracts/store and map selection wiring.
- Verification: `tests/test_farm_registry.py`, migration expectation in `test_workspace.py`, isolated browser fixture/runner, registry Playwright configuration/spec, frontend registry tests and ignored browser artifacts.
- Existing live-Gemini graph citation changes/test/report were retained rather than overwritten.

The standalone frontend checkout remains untouched; canonical code is in this repository. No Git commit/push or new operational office/farmer test seeding was performed by the browser harness.
