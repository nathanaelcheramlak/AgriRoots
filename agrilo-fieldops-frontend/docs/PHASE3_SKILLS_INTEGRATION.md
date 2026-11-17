# Phase 3 — Skills workspace

Skills now has its own navigation page in AgriLo's existing dark design. It lists the authenticated office's actual versioned registry, not one skill per provider or a static count. A provider connection owns tools; explicitly authored skill manifests depend on capabilities. Installing or approving a REST/MCP tool never creates an agricultural skill automatically.

## Availability and detail contracts

`GET /api/v1/skills?include_execution=true&limit=100&offset=0` is the existing listing route with an optional read-only projection. Without the flag its response is unchanged. `GET /api/v1/skills/{id}?include_execution=true` supports the same projection. Responses are runtime-validated in `src/features/skills/service.ts`, paginated with an explicit 10,000-record ceiling, and kept only in memory.

Each item retains the actual current definition:

```text
id, name, revision, version, version_id, digest, manifest,
approved, enabled, enabled_version
```

The optional `execution` object contains:

```text
available, blocked_reason, blocked_code,
version, approved, manifest,
dependencies: [{capability, required, available}],
missing_optional_capabilities,
tools: [{name, version_id, capabilities, input_schema,
         plot_scoped, requires_image, optional,
         source: {name, host}}]
```

`execution.version` refers to the enabled/last selected version when one exists, otherwise the current definition. The backend resolves availability with its actual role-specific `Registry`, approved enabled tool versions, credential scope and owning-pack policy. Disabled skills, missing required capabilities, viewers and internal-action workflows remain unavailable. A newer unapproved draft can coexist with an older approved executable version; these are shown separately. The current definition and runtime target must not be conflated.

Source metadata is limited to connection name and hostname, not credential references, full configuration, secret paths or headers. Input schemas remove server-bound farm coordinates/image references in the same way as Home. Candidate sources for an unavailable skill identify eligible dependency tools, not a guarantee of a successful run. Browsing makes no provider/model request; runtime still rechecks authorization and dispatch policy.

Registry availability is separate from model readiness, UI-supported inputs, required farm context and actual provider reachability. Home rejects unsupported required parameters and applies its existing scope/date/data-policy constraints. One-point operations require one authorized farm; route operations require two authorized endpoints. Arbitrary bulk iteration, surveyed boundaries and unsupported combinations of tool scopes are not implemented.

## Officer experience

1. Start explicit HTTP mode with the existing API/connector worker as described in the [Home guide](PHASE1_HOME_INTEGRATION.md). Sign in on Home using an existing authorized account.
2. Choose **Skills**. Search by name/description/capability, filter by category or registry availability, and inspect a skill. Default demo mode shows a clear backend-required state rather than fake executable skills.
3. Details show agricultural purpose, current and enabled versions, required/optional dependencies, public input schemas, eligible evidence sources, farm scope and scientific limitations. The scientific caveats are explanatory UI guidance, not newly measured farm evidence or proof that a skill's authored instructions are agronomically valid.
4. Select authorized farm references and provide the public supported parameters. Required fields use the actual schemas. Existing Home farm selection and same-skill parameters are preselected. Private image upload and paid-diagnosis consent remain in Home.
5. Choose **Open skill in Home**. This refreshes the authorized Home context, verifies the selected skill/farms/parameter names and updates only the preparation controls. It does not submit a job. Map geometry, filters, map focus, conversation and prior investigation records are retained. Network/model/credit consent is reset for explicit review. A currently active or uncertain investigation blocks replacement and offers return to the existing run.
6. In Home, enter the question, inspect required dates/scope, and explicitly authorize the configured model and provider requests. Existing `investigationBlock`, `HomeApi.start`, durable polling, cancellation, same-request-key recovery, evidence retrieval, source cards and numerical charts perform the complete investigation. There is no second Skills execution engine or duplicated run HTTP client.
7. Navigate to Skills or Plugins and back while work continues. Skill details link to matching investigations retained in the current memory-only Home session. Reload/logout clears the browser session; the server job remains durable. A backend per-skill history listing is absent, so the UI does not fabricate older runs.

The actual run contract remains:

```text
POST /api/v1/skills/{id}/runs
{task, plot_ids, parameters, request_key,
 authorize_network, authorize_model, authorize_credit_use,
 image_asset_id?}
```

Status, cancellation, results/evidence and image contracts remain those verified in [Phase 1](PHASE1_HOME_INTEGRATION.md). No coordinates, client office authority, transcript or credentials are sent as skill parameters. The backend derives authorized plot coordinates and rechecks every request. A model must propose valid public arguments from the supplied task context; submitting parameters does not bypass tool validation or prove real-model reasoning quality.

## Administrator authoring

The audit confirmed that these APIs already exist:

| Method / route | Actual behavior |
| --- | --- |
| `POST /api/v1/skills` | Create an unapproved, disabled skill definition |
| `POST /api/v1/skills/{id}/versions` | New immutable manifest version using `{expected_revision, manifest}`; stable name unchanged |
| `POST /api/v1/skills/{id}/test` | Exact-version configuration validation; resolves approved tool dependencies, **no provider/model execution** |
| `POST /api/v1/skills/{id}/approve` | Admin approval of `{version, digest, request_key}` after successful exact configuration validation |
| `PATCH /api/v1/skills/{id}/enabled` | Explicit activation/revocation using `{enabled, expected_revision, version}` |

Administrators can create a backend draft or revise the current manifest using the JSON editor. Saving, validating, approving and enabling remain separate actions. Current approval errors come from the backend; the UI does not infer that an old browser validation message approves a new version. Validation messages name their version/job. An existing enabled version remains usable while a new draft is reviewed. On this screen changing activation to a newer version requires explicit disable and then enable of the approved current version.

Skill manifests declare `name`, `description`, `instructions`, `required_capabilities`, `optional_capabilities`, `allowed_internal_actions`, `max_followup_rounds` and `triggers`. They are configuration data, not executable code or authority to bypass policies. Metadata editors reject recognizable credential-bearing fields/text; never paste credentials into instructions. No local skill draft can be restored as an approval. Officer/viewer roles have no authoring controls and backend authorization remains decisive.

No separate review-submission queue, skill deletion UI, bulk authoring/import, scheduled trigger execution, complete immutable-version browser/history endpoint or per-skill run listing is invented. Internal draft-write/release workflows remain outside Home/Skills investigation execution even if their underlying definitions exist. Trigger metadata does not activate Monitoring or messaging.

## Verification

From the frontend repository:

```powershell
npm run check
npm run test:e2e
```

From `AgriRoots/backend` with installed test dependencies and frontend Chromium:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_skills_workspace.py tests/test_home_integration.py tests/test_plugins_integration.py tests/test_connectors_rest.py tests/test_connectors_mcp.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_companion_skills.py -q
.\.venv\Scripts\python.exe scripts/check_home_browser.py --skills
```

The final runner includes all Home, Plugins and Skills integration scenarios. It creates only disposable auth/database/worker/provider fixtures, uses the real official MCP SDK fixture server and actual REST HTTP responses, and labels the deterministic model fixture. The fixture now copies supplied reviewed parameters into matching public function-argument fields; production graph/executor logic was not modified. Missing/malformed tool arguments remain actual failed/partial outcomes. No fresh cloud-model reasoning, paid diagnosis, expensive Earth Engine request or real-farm efficacy is claimed.

See the [Phase 3 report](../../docs/PHASE3_SKILLS_INTEGRATION.md) for actual outcomes, changed files, remaining gaps and the stop boundary.

## Unresolved Phase 1 live verification

An authorized real-model investigation against operational farm data is still unverified. The saved operational configuration lacks the Gemini key/explicit model and has model execution disabled; an interactive authorized officer account is still needed for a live walkthrough. No account/password was reset and no operational data was seeded. These are unchanged configuration/verification gaps, not reasons to substitute a synthetic success.

Stop after Phase 3. Monitoring scheduling, Outreach delivery and farmer messaging remain out of scope.
