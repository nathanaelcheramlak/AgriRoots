# Extension-office advisory implementation plan

Status: Phases 1–3 and final code-gap work are implemented. The application includes office-controlled versioned advice, MCP/LangGraph drafting on local Qwen, explicit reviewed planting/hold rules, per-plot checkpoints, local released-only speech and audio auditing, pinned one-command startup, CI, and submission documents. Final verification: 60 tests pass on each of SQLite/PostgreSQL, frontend lint/build pass, isolated-source startup passes, real five-plot task completes in 219.75 seconds, and an 85.56-second continuous planting/hold demo includes weather recovery and audio playback. Original code is Apache-2.0 with owner-confirmed redistribution rights. External gates remain: named participating office/feedback (none collected), agronomist assessment, public hosting, verified host country and organizer eligibility/deadline decisions. A completely uncached separate-host CI job is provided but remote execution is not claimed. See `EVALS.md` for actual artifacts and limits.

Project: Farmly, subsequently found at `/home/natcher/Projects/AgriRoots`.

## Objective and scope

Build a functional climate-smart advisory workspace for an Ethiopian extension office using the existing FastAPI backend, React frontend, LangGraph agent, weather/soil integrations, crop diagnosis, farmer profiles, voice, and alerts.

End-to-end workflow:

Officer selects a household cluster -> agent gathers evidence -> agent validates and drafts advice -> officer reviews and approves -> officer explicitly releases the approved version.

The agent must not have tools for sending messages to farmers, ordering inputs, or requesting credit. Every phase ends with a usable workflow and passing acceptance checks.

This plan is based on previously inspected project code. Confirm the current checkout, local instructions, dependencies, and route inventory before implementation. Do not claim that planned functionality or evaluations already exist.

## Phase 1: Officer workspace and controlled advisory workflow

### Functional outcome

An officer can register households and plots, create a sourced advisory manually, submit it for review, approve it, and explicitly release it to the correct farmer. Autonomous drafting is introduced in Phase 2.

### 1. Extension-office permissions

- Add offices, office memberships, and explicit administrator, officer, and farmer roles.
- Reuse existing authentication and enforce authorization on the server.
- Require an authorized administrator to assign officer roles; provide a controlled initial administrator provisioning procedure.
- Scope officer access to their office's households, plots, evidence, and advisories.
- Restrict farmers to their own released advisory versions.
- Do not use the editable profile `user_type` field as an authorization mechanism.

### 2. Household and plot records

Add records for:

- Households and linked farmer accounts.
- Plots, coordinates, area, and agroclimatic zone.
- Crops, planting dates, harvest dates, and previous yields.
- Crop calendars and locally reviewed agronomic guidance.
- Household clusters and assigned officers.

Validate coordinates, area and yield units, date ordering, and household ownership. Distinguish missing values from zero yields. Use labelled synthetic household records for development and public demonstrations. Exclude personal records and production databases from the public repository.

### 3. Versioned advisories

Store target households and plots, proposed actions, evidence references, uncertainty, missing information, creator, assigned officer, version, timestamps, approval history, and release history.

Lifecycle: Draft -> Pending review -> Approved -> Released.

Also support rejection, cancellation, and replacement by a newer advisory. An edit to content, evidence, recipients, or language after approval creates a new version requiring approval again. Preserve previously released versions and their histories.

### 4. Evidence storage

Each evidence record includes:

- Source name and source URL or internal record identifier.
- Observation time, retrieval time, and validity period.
- Location, crop, units, and relevant values.
- Stored snapshot or permitted extract of supporting data.
- Classification as live, historical, synthetic, or officer-entered data.

Require individual recommendations to reference specific evidence records. A general source list alone is insufficient.

### 5. Officer and farmer interfaces

Add household and plot management, cluster selection, advisory drafting, evidence attachment, review queues, edit/reject/approve actions, and a separate release action. Add a farmer view showing only released advisory versions. Enforce permissions in FastAPI as well as in the UI.

### 6. Approval controls across existing delivery paths

Inventory chat, recommendation, diagnosis, alert, and voice endpoints and services.

- Route consequential household-specific farming advice into the advisory review workflow.
- Prevent existing endpoints from exposing unapproved household-specific recommendations.
- Generate farmer-facing advisory audio from released content only.
- Include translations in the reviewed version; do not translate new advice after approval without review.
- Preserve general educational chat with an explicit boundary from household-specific recommendations.
- Keep OTP authentication messages separate from agricultural advisory delivery.
- Use explicit officer-controlled in-app publication initially. SMS and USSD are optional future integrations.

### 7. Migrations and auditing

- Use versioned database migrations instead of relying only on startup table creation.
- Record creation, edits, submission, rejection, approval, cancellation, and release events.
- Associate approval with the authenticated officer and exact advisory version.
- Make release operations transactional and idempotent, including concurrent requests.
- Preserve historical versions and audit records.

### Primary implementation areas

- `backend/src/db/models/`
- `backend/src/db/schema_migrations.py` and versioned migrations
- `backend/src/auth/dependencies.py`
- New office, household, plot, evidence, and advisory routes, schemas, repositories, and services
- Existing recommendation, chat, diagnosis, alert, and voice services
- `frontend/src/App.jsx`
- Officer pages, farmer advisory view, and advisory API helpers

### Acceptance checks

- An authorized officer can create, review, approve, and explicitly release a sourced advisory.
- Farmers cannot view drafts or another household's advisories.
- Officers cannot access another office's records.
- Unprivileged users cannot assign themselves officer or administrator roles.
- Editing an approved advisory invalidates approval and preserves historical versions.
- An unsourced recommendation cannot be approved.
- Repeated or concurrent release requests do not duplicate publication.
- Existing farmer-facing routes cannot bypass approval.
- Authentication and onboarding regression checks pass.
- Migrations work on a fresh database and a copy of the existing schema.

## Phase 2: MCP tools, autonomous drafting, and an open-weights model

### Functional outcome

An officer requests an advisory for a cluster. A genuine multi-step agent completes the task using MCP tools and an open-weights model, stores a sourced draft, and stops at officer review.

### 1. Farmly MCP server

Implement distinct reusable tools:

| Tool | Purpose |
| --- | --- |
| `get_cluster_plot_history` | Retrieve authorized household and plot history |
| `get_weather_evidence` | Retrieve dated observations and forecasts |
| `get_crop_risk_context` | Retrieve applicable crop calendars, guidance, and recorded pest signals |
| `save_advisory_draft` | Persist structured recommendations linked to evidence |

The draft tool is a real write action. Every tool requires validated inputs and outputs, office/run authorization, timeouts, structured errors, evidence identifiers, and success/failure audit events. Propagate the initiating officer's scope; MCP credentials must not bypass office boundaries.

### 2. Independently maintained MCP server

Integrate a third-party document-fetching MCP server for supporting public agricultural guidance.

- Verify the maintainer, licence, installation, and actual tool behavior before selection.
- Pin the tested version.
- Allow only approved public domains; block private-network destinations and unsafe redirects.
- Cache permitted source snapshots and record retrieval dates.
- Document why reuse is preferable to rebuilding document retrieval.
- Treat retrieved content as evidence, never as instructions capable of changing permissions or triggering actions.

### 3. Advisory LangGraph workflow

Extend the existing classify-and-execute design with a separate advisory graph:

1. Validate officer access and cluster scope.
2. Determine required evidence.
3. Retrieve plot history, weather, and applicable crop guidance.
4. Check freshness, geographic coverage, dates, and units.
5. Resolve missing information using bounded retries or a clarification result.
6. Produce structured recommendation candidates.
7. Validate citations and required fields.
8. Save the draft.
9. Mark the draft pending review and finish.

Limit retries, tool calls, execution time, and context size. Persist run state to survive interruption and avoid duplicate drafts. The model cannot approve its own output.

### 4. Open-weights model adapter

- Add a model interface alongside the Gemini adapter.
- Select a model after testing tool use, structured output, licence, memory requirements, and host latency.
- Run it locally or on infrastructure in the intended country.
- Record the exact model revision, serving configuration, and inference settings.
- Complete the full advisory path, including planning and drafting, without Gemini.
- Prevent household data from reaching public document retrieval or cloud model calls.

Existing local crop classifiers do not by themselves satisfy the requirement for an entire advisory task on an open-weights language model.

### 5. Deterministic evidence validation

Before a draft is reviewable, validate that every recommendation references existing evidence applicable to its location, plot, crop, season, and proposed action dates. Check freshness, reject invented identifiers, and flag unsupported precision. If critical evidence is missing, return an insufficient-evidence result or an officer follow-up request rather than fabricating advice.

### 6. Complete run logging

Record run identifier, initiating officer, tool name, validated inputs, timestamps, output or stored-result reference, errors, retries, model usage, duration, and estimated inference cost. Store sensitive logs with access control. Show readable synthetic-data logs in the public demo without credentials or personal details.

### 7. Run interface

Show the selected cluster, requested task, progress, tool calls, retrieved evidence, data-quality warnings, recommendation citations, failures, retry controls, and the link into the Phase 1 review workflow.

### Primary implementation areas

- `backend/src/agent/orchestrator.py`, `state.py`, and `tools.py`
- New advisory graph and MCP server/client modules
- `backend/src/integrations/llm/`
- Existing weather and advisory integrations
- Evidence validation and run repositories
- Officer run screens

### Acceptance checks

- A real cluster task completes through MCP tools using the open-weights model.
- The borrowed MCP server contributes meaningfully to the task.
- The write tool creates a persisted draft.
- Every recommendation has valid inspectable evidence.
- A weather timeout leads to bounded recovery or an explicit failure.
- Missing critical data blocks unsupported recommendations.
- Restarting or retrying does not duplicate drafts.
- Retrieved content and tool output cannot grant approval or publish advice.
- No draft reaches a farmer before officer approval and explicit release.

## Phase 3: Reliability, reproducibility, and submission packaging

### Functional outcome

A stranger can start the application, reproduce the demonstration, inspect genuine evaluation results, and complete the officer-to-farmer workflow.

### 1. One-command startup

Provide a documented command, preferably using container orchestration, for the frontend, FastAPI backend, database, custom MCP server, borrowed MCP server, and open-weights serving process.

Include dependency/model pins, health and readiness checks, automatic migrations, synthetic seed data, persistent database/model caches, secret-free configuration examples, and explicit hardware/download/first-start requirements. Startup succeeds only when the workflow is usable, not merely when processes exist.

### 2. Evaluation suite

| Task | Expected behavior |
| --- | --- |
| Complete consistent records | Produce a sourced draft |
| Missing plot history | Request information or limit advice |
| Stale weather | Refresh or block the affected recommendation |
| Weather service unavailable | Retry within limits, then report failure |
| Conflicting pest reports | Surface the conflict for officer review |
| Unsupported recommendation | Reject during evidence validation |
| Cross-office access attempt | Deny access |
| Unapproved release attempt | Deny release |
| Edit after approval | Require fresh approval |
| Repeated run or release | Avoid duplicates |
| Malicious retrieved document | Ignore embedded action instructions |
| Restart during a run | Recover recorded state safely |

Repeat representative model tasks and report variation, actual pass/fail outcomes, latency, failures, and cost assumptions. Measure the approximately 15-minute target against a defined household-cluster size and host configuration; do not claim it without measurement.

### 3. Integration and permission verification

Run appropriate backend tests, frontend lint/build checks, and end-to-end checks covering officer login, cluster selection, execution, evidence inspection, editing, approval, release, farmer viewing, voice playback, rejection, and correction. Test migrations on a fresh database and a copy of the existing schema.

### 4. Submission materials

- OSI-approved licence after checking rights to included code and assets.
- README covering startup, configuration, data provenance, and limitations.
- `ARCHITECTURE.md` explaining agent shape, model, built/borrowed MCP servers, and approval boundaries.
- `EVALS.md` with at least eight genuine tasks, pass/fail results, and an unresolved failure with a proposed next step.
- Approximately 300-word description identifying the theme, actual target office, and workflow.
- Public demo under three minutes showing an unedited real agent run, visible tool calls, evidence, and human review.

Use a real extension-office workflow where available. Record feedback and resulting changes. Do not invent interviews, deployments, evaluations, or successful executions.

### 5. Release gate

- One-command startup works from a clean environment.
- A full open-weights run produces a sourced draft.
- Approval and release boundaries pass their tests.
- Every required MCP tool works.
- Every action has a traceable log.
- Evaluation claims match saved execution results.
- Public artifacts contain no secrets or private household records.
- Deployment model capacity and data location are documented.

## Estimates and exclusions

Initial estimate: 8-10 substantial work packages, approximately 35-50 files added or modified including tests/configuration/documentation, and roughly 2,500-4,500 lines added or changed. These are planning ranges, not a verified patch count. Re-estimate after Phase 1 schema and route inventory; permissions, migrations, and existing delivery routes create the greatest uncertainty.

Market-price matching, credit assessment, post-harvest traceability, and USSD are excluded from these three phases. They are separate themes or optional integrations rather than requirements for this climate-smart workflow.

## Competition eligibility dependency

Source: https://agentic-africa-challenge.lovable.app/tracks/agriculture

The challenge requires new work during its submission period and excludes resubmission of an existing project. Confirm whether a newly built extension-office module inside this existing project qualifies before representing it as an eligible entry. The page previously showed a 15 October headline deadline while detailed dates remained TBC; verify the actual cutoff with the organizers.
