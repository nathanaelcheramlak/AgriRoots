# Phase 2 — Plugins integration

Implemented in the existing dark Plugins shell, modal system, provider cards, sidebar and forms. Default demo mode and local drafts remain. In explicit HTTP mode the screen now uses the same memory-only officer session as Home and displays the actual office registry. No Skills management, Monitoring or Outreach integration was started.

## Verification before starting

Phase 1 was rechecked before implementation: four Home backend tests and four real backend-connected browser scenarios passed. No critical regression was found. The existing live-model/account configuration gaps remain; fixture success is not a live cloud-model demonstration.

## Connected behavior

- The provider catalog displays all 14 currently implemented backend adapters, their implemented capability, configured office connections, registered tools, latest-definition approval, enabled tool versions and last recorded office test. Eight other catalog entries remain explicitly without reviewed built-in adapters. Historical provider verification retains its source dates and never enables a connection.
- Office connections and operations come from paginated authenticated reads, including configuration revisions, enabled configuration/version, recorded health and credential presence/revision metadata. A newer draft and an older enabled version remain distinct.
- Custom REST registration creates an office-owned disabled connection on the backend. Administrators declare one fixed read-only JSON operation, schemas, data classes and JSON-pointer mappings. Preview is a backend operation that executes no provider request. REST operation discovery/OpenAPI import is unsupported; there is no arbitrary request proxy.
- MCP registration supports the backend's Streamable HTTP transport. Explicit network-authorized discovery queues a real durable backend job. Discovered descriptions are displayed as untrusted data. Administrators review descriptions and capabilities in a new operation version while preserving the actual upstream name, discovered schema and discovery digest. Discovery grants no execution authority.
- Test/discovery jobs poll genuine queued/running/terminal states and preserve actual results, errors, timestamps and partial outcomes. Refreshing an existing job reads its ID rather than resubmitting it. Registration/revision writes have no backend idempotency key; after an uncertain outcome, refresh and inspect before retrying.
- Approval submits the displayed exact tool version, connection revision and digest. Activation uses optimistic record revisions, and tool and connection enablement are separate explicit actions. Successful tests alone do not activate anything. The server rechecks successful exact-version tests, credential scope/rotation and administrator authority. Past test success is not proof of current credential health.
- Administrators may explicitly authorize diagnostic test execution before approval; that is the backend's review workflow. Normal executor runtime requires approval/enablement and authorization. Plugins does not expose a made-up direct runtime endpoint. Existing backend tests verify runtime rejection before approval and actual invocation after approval; Skills orchestration remains a later phase.

The screen clears office-managed state on logout, office/user/role change and session expiration. Pending stale requests cannot restore a prior session's data. Backend pages are read in batches, with a 10,000-record-per-resource safety limit that reports an error rather than silently truncating. Very large offices have not been benchmarked.

## Local drafts and migration

Open **Local drafts** to select an existing draft. Check the explicit migration acknowledgement, then choose **Review migration**. The form displays the connection metadata before **Create disabled connection** sends anything. Custom drafts map to the existing REST/MCP connection contract; catalog drafts use a current backend provider template where one exists. Unsupported catalog drafts remain local.

The original local draft is retained. Local IDs never become backend IDs. No credential, operation discovery, test, approval or activation is migrated implicitly. Matching existing connections are shown for inspection to reduce accidental duplicate registration, but the backend has no atomic migration/deduplication API. The original local editor remains available through **Open local draft workspace**; its static descriptions belong to that historical local catalog, not the current backend's capability authority.

## Credentials and network policy

Credential values are never fetched or collected by this frontend. Authentication method/header name and stored credential revision metadata are the only credential-related fields. Managed connection definitions, diagnostics and sessions are memory-only; existing local storage contains validated draft metadata only. Metadata editors reject explicit credential fields and recognizable secret-bearing text, but they are not a universal secret detector: never paste credentials into descriptions, mappings, arguments or URLs.

An authorized backend operator can provision credentials through the existing write-only `PUT /api/v1/integrations/{id}/credential`. The new terminal helper uses the existing password login and connection service, hidden interactive prompts and no secret command-line arguments, files, logs or browser storage:

```powershell
cd C:\Users\fraol\Documents\Agri-roots\AgriRoots\backend
.\.venv\Scripts\python.exe scripts/configure_connection_credential.py --api http://127.0.0.1:8000
```

Use an HTTPS API origin for remote/production operation. The helper requires an interactive terminal and an active office administrator. It does not provision accounts, approve tools or enable connections. A credential change suspends activation and requires retest/reapproval. No actual credential was provisioned during Phase 2 verification.

The backend still enforces approved exact HTTPS hosts, pinned public addresses, fixed paths, schemas, role and data-class rules. Production excludes test-only local-origin exceptions. Host-policy changes require deployment configuration, not a UI approval button. Real discovery/tests additionally require the backend live-test flag and explicit network consent. No live provider probes or paid Kindwise/Earth Engine operation were run. Diagnosis tests remain unavailable on Plugins; its credit/image workflow is separate.

## Actual routes

All routes use the existing bearer session. None accepts client office identity as authorization.

| Method and route | Connected use |
| --- | --- |
| `GET /api/v1/providers` | Current implemented handler metadata plus unchanged historical verification |
| `GET /api/v1/providers/{id}/template` | Backend-reviewed connection/operation template |
| `GET, POST /api/v1/integrations` | Office connection listing / disabled registration |
| `POST /api/v1/integrations/{id}/versions` | Optimistic configuration revision |
| `GET, POST /api/v1/integrations/{id}/tools` | Registered definitions / REST or template operation registration |
| `POST /api/v1/integrations/{id}/tools/{tool}/versions` | Exact reviewed operation revision |
| `POST /api/v1/integrations/{id}/discover` | Explicit MCP discovery job |
| `POST /api/v1/integrations/{id}/tools/{tool}/preview` | No-network request preview |
| `POST /api/v1/integrations/{id}/tools/{tool}/test` | Authorized bounded diagnostic job |
| `GET /api/v1/connector-jobs/{id}` | Actual job status/result/error |
| `GET /api/v1/integrations/{id}/tests` | Recorded tests/discovery history |
| `POST /api/v1/integrations/{id}/tools/{tool}/approve` | Administrator approval of exact tested version |
| `PATCH /api/v1/integrations/{id}/tools/{tool}/enabled` | Tool activation/revocation |
| `PATCH /api/v1/integrations/{id}/enabled` | Connection activation/revocation |
| `PUT /api/v1/integrations/{id}/credential` | Terminal helper only; browser never handles values |

The only production backend change is current provider metadata resolution: the older inventory incorrectly omitted eight implemented handlers. Routes now merge the operator-owned factory mapping into implementation metadata, leaving historical verification unchanged. Template and provider verification lookup use that same mapping. No new services, tables, permission exemptions, model configuration, execution routes or migrations were added.

## Walkthrough

1. Use the [Home setup guide](PHASE1_HOME_INTEGRATION.md) to start HTTP mode and the existing API/connector worker. Sign in on Home with an authorized account, then navigate to Plugins. Officer roles can inspect; an office administrator is required for management actions.
2. Inspect a provider's configured connections, operations, current/active versions and recorded tests. Opening this page makes no provider health probe. Use **Refresh backend registry** to update the snapshot.
3. For REST choose **Add → Register custom REST API**. Enter an approved origin, metadata, auth method and data classes; create the disabled connection. Under **Tools & operations**, declare its fixed operation. Use **Testing & approval** to preview, select authorized farm context if needed, authorize network and test. Review the actual result before exact-version approval. Enable the tool, then the connection separately.
4. For MCP register an approved Streamable HTTP endpoint. Under **Testing & approval**, explicitly authorize network and discover. Inspect tools; review the definition under **Tools & operations**, replacing `unreviewed.*` capabilities with reviewed ones. Test the exact reviewed version before approval and activation. Failed/partial discovery stays failed/partial; unsupported artifacts remain diagnostics.
5. For local migration, explicitly choose the draft and review metadata as described above. Do not remove the draft unless you independently choose that action in the local editor.
6. Refresh Home context to see any changed available tools through existing skills. Plugins does not create or enable skills. Tests and approvals do not change Gemini/Qwen or send outreach messages.

## Tests and verification

Run frontend typecheck/lint/unit/build with `npm run check`, and the legacy demo browser regression with `npm run test:e2e`. The dedicated cross-repository runner is:

```powershell
cd C:\Users\fraol\Documents\Agri-roots\AgriRoots\backend
.\.venv\Scripts\python.exe -m pytest tests/test_plugins_integration.py tests/test_connectors_rest.py tests/test_connectors_mcp.py tests/test_home_integration.py -q
.\.venv\Scripts\python.exe scripts/check_home_browser.py --plugins
```

It starts only disposable fixtures: real FastAPI/auth/database/worker/executor, real local HTTP REST fixture and official MCP SDK fixture server, plus Home's explicitly labelled model fixture. It never modifies the operational database or calls external models/providers. Backend runtime tests verify actual approved executor invocation; browser tests exercise the diagnostic path, not an invented direct runtime API. Current results, exact changed files and remaining gaps are in the [Phase 2 report](../../docs/PHASE2_PLUGINS_INTEGRATION.md).

## Known limits / stop boundary

There is no separate submit-for-review queue, approval delegation, backend delete/archive endpoint, atomic local-draft migration, connection creation idempotency, live push updates, browser credential entry/readback, interactive MCP OAuth, tenant stdio, automatic REST/OpenAPI discovery, or direct Plugins runtime invocation route. These are explicit gaps rather than simulated success. UI schemas are runtime-validated; existing route response OpenAPI schemas remain incompletely typed. Individual providers have not all been freshly retested through the new UI. Credential helper actual writes were not performed.

Plugins integration is ready for review. Stop here; Skills, Monitoring and Outreach integration require a later instruction.
