# Connector support and operation

The `agri-mcp` branch adds a backend connection platform alongside the existing reviewed advisory workflow. The running API advertises its actual subset at `GET /api/v1/integrations/support`. All `/api/v1` routes require an existing active office membership; configuration, credentials, discovery and approvals require an office administrator.

| Area | Implemented | Boundaries |
| --- | --- | --- |
| REST | Fixed-origin JSON GET and explicitly reviewed read-only POST; nested JSON Pointer/literal mappings; authoritative input/output validation | No modifying HTTP methods, dynamic destinations, arbitrary headers, generic pagination or automatic OpenAPI import |
| MCP | Official `mcp==1.29.0` SDK, Streamable HTTP, initialization, paginated discovery, review staging, tool calls, structured/text outputs, deterministic close | No tenant stdio, legacy SSE, OAuth consent, sampling, filesystem roots, elicitation or resource downloads; servers requiring newer incompatible protocols are blocked |
| Authentication | Anonymous, API-key header, bearer; reviewed iSDA login handler | Provider credentials are connection-owned. No app JWT/model key forwarding; no claimed universal OAuth support |
| Schemas | Bounded inline JSON Schema 2020-12 subset; enums, bounds, required properties and additional-property constraints retained | 64 KiB, depth 12, 1,000 nodes; references, regex patterns, quadratic uniqueness checks and unsupported constructs fail explicitly. Formats are limited to date/date-time, UUID, URI, IP, hostname and email. A live Gemini declaration can still be rejected by the selected model; constraints are never silently dropped |
| Plugins | Immutable JSON packs of connection/tool templates and skill manifests, transactional disabled installation | No packages, imports, shell commands, callbacks, code or embedded secrets |
| Storage | PostgreSQL definitions, jobs, approval/audit history, invocations, evidence and LangGraph checkpoints; Redis optional encrypted cache | SQLite is for isolated development/tests; production dispatch/revocation locking requires PostgreSQL |

Default execution limits are 24 logical dispatches, 80 actual provider HTTP attempts, four concurrent calls, 12 relevant model declarations, two follow-up rounds, and 240 seconds per run. Tool responses default to 1 MiB, including decompression; reviewed raster and Earth Engine operations allow up to the 4 MiB deployment ceiling. Raster range reads additionally have an 8 MiB cache bound and share the HTTP request budget. MCP discovery stops at five pages or 200 tools. Safe GET retries are bounded; POST/authentication/job submissions are not automatically replayed. Every request within SDK initialization/list/call/cleanup and provider authentication/polling consumes the shared request budget. The fixed legacy third-party Fetch subprocess counts its logical call; its private HTTP traffic is separately bounded by its reviewed proxy, rather than counted per request.

From `backend/`, install the recorded environment and run the isolated demo:

```powershell
uv sync --frozen
.\.venv\Scripts\python.exe scripts/demo_connectors.py
```

The default demo uses a real local HTTP fixture, application management endpoints, a persistent isolated database, the actual graph and an explicit model fixture. It records approval, execution, evidence and revocation. Its report is `backend/reports/connector_fixture_demo.json`; it makes zero external provider or real model calls.

For the PostgreSQL/Redis/API/worker/internal-MCP stack:

```powershell
.\.venv\Scripts\python.exe scripts/setup_connector_env.py --development
docker compose --env-file private-data/compose.env up -d --build
```

The setup command refuses to overwrite an existing environment. The current workspace already has an ignored environment used for verification. Development mode permits local HTTP credential writes on the localhost-bound API. Production is the Compose default and requires HTTPS for credential writes, a trusted TLS reverse proxy, protected operator configuration, and backups of the encryption keys. Configure forwarded headers only for that proxy. The migration container uses the owner account; the running services receive the restricted application account. No model weights are downloaded.

Reuse normal account verification, the existing `src.cli.provision_admin --user-id ...` operator procedure, and workspace office membership. There is no public administrator bootstrap. The isolated demo's synthetic bootstrap must not be used against production. Database and Redis ports are not published by the main Compose file; `compose.test.yaml` publishes localhost-only ports for a dedicated disposable test project.

For additional approved public hosts, create `backend/private-data/outbound-hosts.json` with `{"hosts":["api.open-meteo.com","power.larc.nasa.gov"]}` and add `-f compose.yaml -f compose.policy.yaml` to Compose. The read-only operator policy file replaces the default host list and is read at dispatch time. Edit its contents in place to add/revoke hosts without restarting; a replacement bind-mount inode may require remounting on some hosts. Missing/invalid policy fails closed. Tenant configuration cannot change this file.

Liveness `/health/live` and readiness `/health/ready` inspect only internal dependencies. Provider tests are separate explicit jobs. To authorize the bounded public verification sequence:

```powershell
.\.venv\Scripts\python.exe scripts/demo_connectors.py --live
```

This permits small Open-Meteo and NASA POWER MCP calls only. It does not spend Gemini or diagnosis quota. A successful response is evidence of availability at its recorded timestamp, not a continuing health guarantee.

The implementation uses the installed SDK APIs and tests, rather than copying examples for a different major version. References: [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling). Current documentation can describe newer interfaces; this release's exact versions are in `backend/uv.lock` and the hash-locked deployment export.
