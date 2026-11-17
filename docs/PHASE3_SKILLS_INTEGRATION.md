# Phase 3 Skills integration report

The current FieldOps frontend now has an authenticated Skills workspace. It uses actual office-specific skill definitions and approved capability dependencies, and hands investigation preparation to the existing Home workflow. Phase 2's connection/tool management remains intact. No Monitoring, Outreach or farmer-message integration is included.

## Integration matrix

| Feature | Frontend state | Backend state | Integration | Remaining action |
| --- | --- | --- | --- | --- |
| Skill discovery | Searchable/filterable catalog and detail view | Existing paginated skill routes, optional public execution projection | Current draft, approved/enabled version and runtime availability shown independently | Very large office performance unmeasured |
| Tool dependencies | Required/optional capabilities, public schemas and eligible source names/hosts | Actual role-specific Registry resolution and approval/version policy | Missing tools, disabled skills, unsupported internal actions and viewers stay unavailable | Source metadata does not prove provider health |
| Farm/input preparation | Authorized point references and required public inputs | Existing bounded `SkillRunRequest` and server bindings | Fresh Home context checked before explicit handoff | Unsupported parameters/scopes remain blocked or require a future workflow |
| Investigation execution | Existing Home controls, durable jobs, cancel/recover, evidence and charts reused | Existing LangGraph, controlled executor and evidence store | No new engine or direct execution path | Operational real-model/farm walkthrough still blocked |
| Home/Plugins preservation | Home stays mounted, map/conversation/job state retained; Plugins unchanged | Existing auth and exact tool lifecycle | Regressions exercised together | Memory session clears on reload as before |
| Skill authoring | Admin-only backend JSON draft/revision, validate/approve/enable controls | Existing actual versioned authoring APIs | No tool-to-skill auto-promotion, local approval or implicit activation | No separate review queue/deletion/history UI |
| Skill run history | Current browser's existing Home investigations linked by skill | Job-by-ID routes exist; no per-skill list | Session history only; no invented historical records | Backend listing required for complete durable history browsing |
| Monitoring / Outreach | Existing local drafts/demos retained | No scheduling/delivery integration | Out of scope | Await later explicit instruction |

## Audited contracts

The original `/api/v1/skills` list returns current definitions, not necessarily the active executable version. Approval is exact-version; a newly authored draft can coexist with a previous enabled version. Existing `SkillService.test_skill` resolves a configuration using approved tools without invoking a provider/model. Runtime `queue_run` resolves a fresh authorized snapshot; the worker reauthorizes the principal, skill, pack, plots and lease, and the executor validates individual calls.

Minimal read-only change: `GET /api/v1/skills` and `GET /api/v1/skills/{id}` accept `include_execution=true`. Their default response stays unchanged. `src/skills/projection.py` uses the existing Registry to return available/blocked states, active/last-selected manifest version, dependencies, public tool schemas and source names/hostnames. It excludes connection configuration, credential references/digests and secret-bearing URLs. No migrations, new service, model switch, executor exemptions or permission changes were introduced.

See the [frontend contract and walkthrough](../agrilo-fieldops-frontend/docs/PHASE3_SKILLS_INTEGRATION.md) for exact response fields, authoring request bodies and execution routes. Browsing/authoring never implies model/provider success. Category labels and scientific caveats are presentation guidance, not measured farm observations or new backend capability claims.

## Verification

Final observed results on 2026-11-17:

- Frontend `npm run check`: **109 unit tests passed**, typecheck/lint/build passed. The five new Skills tests cover active/draft separation, consent-renewing Home preparation, geometry/conversation/history/focus preservation, foreign/duplicate/active-work denial, refreshed availability/input constraints and stale office-state rejection.
- Backend catalog/Home/Plugins/REST/MCP suite: **32 passed**, `backend/validation/phase3-backend.xml`.
- Existing companion/skills graph suite: **11 passed**, `backend/validation/phase3-companion.xml`. These verify actual controlled tool dispatch, durable evidence, unknown-tool rejection, numerical-claim restrictions, model blockers, versioned snapshots and pack lifecycle.
- Post-fixture-update targeted Skills/Home run: **7 passed**, `backend/validation/phase3-skills.xml` (overlaps the 32-test suite; the two main backend suites cover **43 distinct tests**).
- Final real backend-connected browser suite: **15 passed** — four Home, six Plugins and five Skills scenarios. This includes successful controlled dated-parameter execution, evidence/charts, active navigation, draft/unsupported dependency states, exact authoring lifecycle, mobile layout, logout and REST/MCP regressions.
- Existing default demo browser suite: **29 passed, 15 skipped**. Dedicated backend scenarios skip by design in demo mode and pass separately above.
- Local API and worker rebuilt/restarted with the existing Compose project using `--no-deps --no-build` after building. No migrations, database seeds/resets, credentials or model settings changed. `/health/ready` returned **200** and unauthenticated `/api/v1/skills?include_execution=true` returned **401**; deployed OpenAPI exposes the optional flag on both existing read routes.
- Scoped mobile screenshot inspected: dark modal, source/limitation text, farm controls and Home handoff fit within the viewport. Source/evidence failures remain explicit rather than becoming successful observations.
- Final typecheck/lint and both repositories' diff checks passed. Exact-value scanning of 97 changed UTF-8 text files against seven known local environment secrets found zero matches; this bounded scan does not prove universal secret absence. Phase 3 documentation links resolve and all three saved Phase 3 JUnit artifacts contain zero failures/errors.

An initial dated-input browser case correctly returned `INPUT_VALIDATION_FAILED`/partial because the deterministic fixture model proposed empty arguments. The fixture was corrected to copy reviewed task parameters into matching public schema fields; production parameter binding/execution policy was not changed. A preview regression run overlapped development hot reload, which cleared the intentionally memory-only session; final stable-source regression is authoritative. Generated Playwright trace assets are now excluded from ESLint alongside the other generated report directories, rather than being treated as application source.

No live provider, external MCP endpoint, real cloud-model reasoning, paid Kindwise or expensive Earth Engine execution was performed. Real auth/API/database/worker/executor and real local HTTP/MCP transport are tested with explicitly labelled synthetic fixtures. Provider scientific accuracy, real-office utility and very large datasets are not established.

## Remaining gaps and Phase 1 blocker

The operational live-model/account milestone remains **unverified**: Gemini key and explicit model are missing and model execution remains disabled in the saved local deployment; no interactive operational officer login was supplied. No new operational account, password reset, seed or credential write is included. The existing Qwen advisory path and selected model policy remain unchanged.

Other limits: registry availability is not provider reachability, model readiness or a guarantee that every required input/scope is supported by Home. There is no server spatial intersection/bulk single-plot engine, direct per-skill durable run listing, full version-history browser, review-submission queue, delete/bulk import UI or scheduled skill activation. Unsupported internal draft-write/release actions remain outside this investigation workspace. Required arguments still depend on valid model proposals and executor validation; the fixture is not proof that a real model will infer them correctly.

Stop after Phase 3 for review. No commit/push, Monitoring scheduling, Outreach delivery or farmer messaging is included.

## Phase 3 changed files

Previous uncommitted Phase 1, Phase 2 and frontend-retirement changes remain preserved. This phase changes only the following areas.

### AgriRoots

- `backend/src/api/routes/skills.py` — optional execution projection on existing authenticated reads.
- `backend/src/skills/service.py` — default-compatible optional view composition.
- `backend/src/skills/projection.py` — credential-free role/version/dependency resolution.
- `backend/tests/test_skills_workspace.py` — current/active version, no provider probes, dependency, office and viewer checks.
- `backend/tests/skills_browser_fixture.py` — opt-in disposable draft/unsupported/dated skills and approved HTTP fixture tool.
- `backend/tests/home_browser_server.py` — opt-in Skills fixtures and controlled pause for active-navigation checks.
- `backend/tests/home_fixture.py` — explicit fixture proposals include matching reviewed parameters.
- `backend/scripts/check_home_browser.py` — `--skills` mode retains the original Home and Plugins modes.
- `backend/validation/phase3-backend.xml`, `phase3-companion.xml`, `phase3-skills.xml` — actual JUnit outcomes.
- `docs/PHASE3_SKILLS_INTEGRATION.md`, `docs/README.md`, `docs/testing.md` — delivery, contracts and commands.

### agrilo-fieldops-frontend

- `src/app/App.tsx` — Skills route/navigation; Home remains mounted and existing page routes retained.
- `src/api/home-api.ts` — restricted skill-management transport shares existing private in-memory auth/error handling.
- `src/state/home-store.ts` — fresh-context `prepareSkill` handoff without starting a run or clearing existing work.
- `src/features/skills/service.ts` — actual skill contracts, pagination and authoring API adapter.
- `src/features/skills/store.ts`, `runtime.ts` — office/role-scoped memory catalog and existing-session integration.
- `src/features/skills/presentation.ts` — skill purpose/category/scope, supported inputs and scientific caveats.
- `src/components/skills/SkillsPage.tsx` — new workspace using existing dark layout.
- `src/components/skills/SkillDetails.tsx` — dependency/input/source/version detail, Home handoff, history links and admin lifecycle.
- `src/components/skills/SkillEditor.tsx` — explicit backend manifest drafts/revisions.
- `src/components/plugins/ManagedPluginsPage.tsx` — footer identifies the now-available Skills workspace; connection management behavior unchanged.
- `src/styles/skills.css` — scoped desktop/mobile styles.
- `tests/skills.test.ts` — five targeted contract/handoff/isolation tests.
- `e2e/skills-backend.spec.ts`, `playwright.skills.config.ts` — five new browser scenarios plus Home/Plugins regressions.
- `.gitignore`, `eslint.config.js` — exclude generated browser reports/traces from Git and lint.
- `docs/PHASE3_SKILLS_INTEGRATION.md`, `README.md` — current setup, contract and walkthrough.
