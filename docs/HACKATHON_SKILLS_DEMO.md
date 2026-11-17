# Crop health and monthly rainfall demo

Implemented November 17, 2026 in the canonical `agrilo-fieldops-frontend` and existing backend. Open `http://127.0.0.1:5179/#skills` after signing in on Home.

| Skill | Inputs | Provider report | Ask AI |
|---|---|---|---|
| Crop health | JPEG/PNG up to 10 MB; optional authorized registered farm | Real Kindwise Crop.health crop and disease candidates with provider confidence, source and limitations | Gemini explains the saved candidates and offers general crop-care guidance and field checks |
| Monthly rainfall | Assigned territory; inclusive historical interval of 28–31 days | Real CHIRPS/ClimateSERV daily rainfall, recorded sum in mm, chart and daily table | Gemini explains the saved month and gives qualified crop-planning considerations |

The featured skills use actual office approval/enablement state. The remaining registry stays available under **Browse all registered skills**. Home remains focused on weather and soil.

## Walkthrough

1. Sign in on Home, then open Skills.
2. Crop health: choose a clear plant photo, optionally select a registered farm, authorize the photo request and diagnosis credit, and select **Assess crop photo**.
3. Review candidates, authorize the configured model, enter a question and select **Ask AI**.
4. Monthly rainfall: select an assigned territory, authorize the provider request and select **Generate rainfall report**. July 1–31, 2025 is the explicitly labelled default historical demo interval. Dates are editable.
5. Review the daily bar chart and monthly total. Ask AI to interpret the evidence and discuss crop-planning considerations.

Switching between Home and Skills retains report state during the signed-in session. Refresh report resumes polling; cancellation uses the existing backend cancellation route. An uncertain submission can be recovered with the original idempotency key. A full browser reload ends the in-memory session and report selection; backend jobs remain durable, but a saved-report browser/history is not included in this focused demo.

## Actual contracts

Existing authentication and request client are reused. No provider keys or photos enter localStorage.

| Operation | Endpoint and body |
|---|---|
| Discover authoritative skills | `GET /api/v1/skills?include_execution=true` |
| Upload and sanitize image | `POST /api/v1/image-assets`, multipart `image` |
| Collect photo evidence | `POST /api/v1/skills/{id}/evidence-runs`: `request_key`, `image_asset_id`, optional `plot_ids` (maximum one), `authorize_network: true`, `authorize_credit_use: true` |
| Collect rainfall evidence | Same evidence-runs route: `request_key`, `territory_id`, `start`, `end`, `authorize_network: true` |
| Explain saved evidence | `POST /api/v1/skills/{id}/explanations`: `request_key`, `evidence_job_id`, `task`, `authorize_model: true` |
| Poll / cancel / sources | Existing `GET /api/v1/connector-jobs/{id}`, `POST /api/v1/runs/{id}/cancel`, `GET /api/v1/evidence/{id}` |

Both phases create the existing `skill_run` durable jobs. Evidence collection invokes the approved controlled executor without a model. Explanations run the existing LangGraph workflow with saved source outcomes and **no provider tools exposed to the model**. Ask AI cannot resubmit a photo or consume a diagnosis credit. A completed identical photo assessment can be reused only for the same office, officer, approved tool version and credential scope, with original evidence provenance retained. Ambiguous earlier submissions remain protected against automatic repeat spending.

Territory sampling is resolved by the server from an active authorized territory. It creates no artificial farm record. Assignment checks protect dispatch, job reads, evidence reads and AI explanations. Private farm records, exact coordinates and image identifiers are excluded from cloud-model context; the model receives the provider evidence and officer's question.

## Live verification

These are actual provider/model runs, distinct from automated fixtures:

- Crop.health exact-version approval test: `4aa98937-35fa-4049-882d-a7f0ee43e3b2`, live evidence `07860607-26a0-4fd4-9ceb-3a022415281f`. A genuine sample plant photo was sanitized before transmission. One diagnosis receipt was created.
- Browser photo report: `43148bbf-63a0-4b9c-a873-71ab9d10aef8`, reusing that completed assessment without another diagnosis request. Real Gemini explanation: `736977c2-bd35-471c-8304-d72fceb3ab0e`, succeeded and rendered crop-care guidance.
- CHIRPS exact-version month test: `e0a45654-5303-4dc5-a630-8cdac163c639`, succeeded.
- Territory rainfall report: `18743464-6e79-46cf-8cb3-a75557493451`, live evidence `ff936821-3c19-4460-ab52-ae0bfdbffccd`: 31 validated daily records for July 2025, summed to **175.796 mm** at the tested territory sampling point.
- Browser rainfall report: `54cf1a60-dd48-4e96-982e-27f5b3cb39d0`, reused that real rainfall evidence. Gemini explanation `6dc9a7db-8fa8-403e-a231-5b087181ea04` succeeded and rendered a complete concise answer.
- Desktop browser exercised upload, optional no-farm photo workflow, provider report, Ask AI, territory selection and the daily rainfall graph. Separate navigation verification retained the saved report and AI answer across Home → Skills; mobile document width was 390 px at a 390 px viewport.

Initial failed/incomplete jobs are retained. A photo uncertainty disclaimer containing Markdown emphasis was initially misclassified as a confirmed diagnosis; the claim validator now recognizes the explicit negation while still blocking affirmative claims. An earlier overly long rainfall answer ended mid-heading; explanation instructions now request a concise complete answer and avoid repeating the daily table already shown in the UI.

## Automated verification and boundaries

- Final targeted Home/environment/Skills regression: **13 passed**, including preservation of the three Home weather/soil choices after the new skills were enabled.
- 56 selected backend tests passed across demo skills, provider adapters, private images/credit receipts, environment policy, evidence citations and Home integration. Tests use explicit provider/model fixtures, not live observations.
- 127 existing frontend tests and 3 additional demo tests passed. New checks cover saved-evidence explanation, no repeated photo upload, recovery with the same key and discarding responses after logout. Type checking, frontend lint and production build passed.
- Backend workflow tests cover optional farm linkage, territory assignment/revocation, office/role isolation, required consent and date validation, private-context minimization and no extra provider calls during Ask AI.
- The old 0.002-degree CHIRPS request box could miss raster-cell centres. Reviewed sampling now uses a 0.05-degree box and the changed tool version was live-tested and approved. Complete daily coverage is required; missing values are never replaced with zeros. An empty response reports no data. [ClimateSERV API reference](https://climateserv2.servirglobal.net/develop-api).
- Rainfall is an estimate for a small box around the territory's representative point, not a whole-territory average or a forecast. The historical month alone cannot establish current crop suitability.
- Photo candidates are uncertain model assessments, not field-confirmed diagnoses. AI guidance does not supply verified pesticide prescriptions, doses, guaranteed yields or a comprehensive crop-suitability ranking.
- Monitoring scheduling, Outreach delivery, farmer messaging and additional provider activation are outside this change.

## Main changed files for this demo

- Frontend: `components/skills/DemoSkills.tsx`, `features/skills/demo-runtime.ts`, `styles/skills-demo.css`, `components/skills/SkillsPage.tsx`, `tests/demo-skills.test.ts`.
- Backend: `skills/demo.py`, skill routes, existing job worker and companion graph, environment policy, provider adapters/factory, shared executor/context/policy and territory authorization guards; `tests/test_demo_skills.py` and related provider regression tests.
