# Plugins — standalone phase one

**Historical local/demo behavior.** Explicit HTTP mode now uses the [Phase 2 Plugins integration](PHASE2_PLUGINS_INTEGRATION.md), real office connection/tool states and administrative lifecycle. The local catalog/editor described below remains available as a separate draft workspace; it does not establish backend availability or approval.

Open `http://127.0.0.1:5175/#plugins`. `#home` opens the existing FieldOps workspace. The former Scheduled placeholder is now the separate local [Monitoring workspace](MONITORING_FRONTEND.md); Plugins behavior remains local-only. Skills has been removed from both navigation sidebars.

The Plugins page uses original AgriLo components, an original circular socket icon, and a neutral dark management layout inspired by the supplied reference. The secondary sidebar shows Installed **local drafts**, while the main page offers source filters, search, categorized agricultural providers and an Add menu. On small screens both application navigation and the installed-draft list use accessible drawers.

## Try the flow

1. Open Plugins. Installed starts empty. Search a provider name or category, or filter Built-in, Office or Custom. Office is empty because no authenticated office service is connected.
2. Choose `+` beside Open-Meteo. It saves a local draft and opens its details. Its provider availability remains separate from the draft, connection, approval and enablement states.
3. Choose **Add → Add MCP server** or **Add API plugin**. Enter a name, optional description, credential-free endpoint, and authentication **method only**. API key mode collects the header name, not the key value. Choose **Save draft**.
4. View the configuration, edit it, or remove it. Refresh to confirm that valid drafts are retained on this device. Tools & operations and Testing & approval explain the future workflow; their backend actions remain unavailable.
5. Return to Home. The rectangle, selected farm, filters, analysis/results, assistant session, input values, map size, basemap, position and zoom remain present. Navigation does not restart screening or cancel pending assistant replies.

## Independent state and ownership

The catalog is a sanitized metadata snapshot from the agricultural provider inventory on 16 November 2026. Only names, IDs, categories, documentation URLs, template/authentication flags and source date were copied. No credentials, accounts, farmer records, original filesystem paths, or live connection evidence were imported. The frontend has no runtime dependency on AgriRoots or `f-test`.

| Dimension | Local prototype behavior |
| --- | --- |
| Catalog availability | Setup available, setup required, or setup unavailable; determined by the catalog metadata and limitations |
| Local installation | Not saved, or Saved locally as a Draft |
| Connection health | Not connected |
| Administrative approval | Not submitted |
| Runtime enablement | Not enabled |

Catalog availability is not a successful provider test. A local save never changes connection, approval or runtime state. Backend-derived states are not accepted in local records; injected `health`, `approved`, `enabled`, office or credential fields cause the stored document to be rejected rather than gaining authority.

Catalog items identify built-in system providers. Drafts have a separate device owner. Custom configurations identify user-created entries stored on this device; no authenticated user or office ID is invented. `PluginSource` reserves built-in, office and custom origins, while future server-side views carry authenticated identity. Displayed names such as “Office API” do not assign office ownership.

Local records use `agrilo-fieldops:plugins:v1` with an explicit version and Zod validation. Catalog drafts store their catalog ID; custom drafts store validated configuration metadata, UUID and creation/update dates. Writes are serialized, catalog additions are idempotent, and duplicate/unknown stored references are rejected. Storage failure leaves the form open and produces an error instead of claiming a save. Invalid stored data produces an explanatory notice; it does not silently restore authority.

## URLs and credentials

- Only HTTPS endpoints are accepted, with HTTP loopback allowed for local MCP servers. Remote HTTP and executable URL schemes are rejected.
- User information, query strings, fragments, encoded query/fragment markers and recognized token-bearing URL/text patterns are rejected. Endpoints must be credential-free. This conservative prototype intentionally does not support query-based authentication.
- Actual keys/tokens, arbitrary headers, credentials and approval flags have no fields in the strict stored schema. API key configuration accepts an allowed header **name** only.
- Invalid submissions are never persisted, and input or parser errors are not logged. Endpoint displays are plain text; the application does not fetch endpoints, previews or remote icons.
- Pattern validation cannot determine the meaning of every possible opaque path segment; users must supply credential-free service endpoints. Future backend destination policy, secret management and authentication remain necessary before real execution.

Provider documentation opens externally only when the officer chooses its link. Plugin management itself makes no external or backend requests. Home retains its separate normal basemap tile requests.

## Service boundary and future backend mapping

`PluginService` handles catalog and draft operations separately from the existing FieldOps analysis/assistant adapter. `LocalPluginService` implements the phase-one behavior. `BackendPluginOperations` defines typed future operations, and every local backend operation returns `{ ok: false, error: { code: 'BACKEND_REQUIRED', ... } }` without contacting anything.

Distinct branded ID types prevent provider/catalog references, connections, tools, plugin packs, jobs and skills from being accidentally interchanged. In particular, a catalog provider is **not** automatically a backend plugin pack. Future adapters must translate frontend property names into the backend's actual wire contract and validate responses.

All proposed mappings below have `/api/v1` prefix and are documented from the existing backend source. None is called by this phase:

| Typed operation | Existing backend route family |
| --- | --- |
| Catalog metadata / provider template | `GET /providers`, `GET /providers/{provider_id}/template` |
| List/create/version integration | `GET/POST /integrations`, `POST /integrations/{id}/versions` |
| MCP discovery / tools | `POST /integrations/{id}/discover`, `GET /integrations/{id}/tools` |
| REST operation registration/versioning | `POST /integrations/{id}/tools`, `POST /integrations/{id}/tools/{tool_id}/versions` |
| Request preview / tests | `POST /integrations/{id}/tools/{tool_id}/preview`, `.../test`, `POST /integrations/{id}/test` |
| Diagnostic job retrieval | `GET /connector-jobs/{job_id}` |
| Exact-version tool approval | `POST /integrations/{id}/tools/{tool_id}/approve` |
| Separate connection/tool enablement | `PATCH /integrations/{id}/enabled`, `PATCH /integrations/{id}/tools/{tool_id}/enabled` |
| Plugin pack list/register/install/enable | `GET/POST /plugins`, `POST /plugins/{id}/install`, `PATCH /plugins/{id}/enabled` |
| Skill registry access | `GET /skills` |

Version targets retain connection revision, tool version and digest. Enablement uses expected revision guards; pack installation/enablement uses the exact digest. Future administrator authorization, credential scope, accepted test evidence and membership come from the server rather than local UI claims. Capability flags keep discovery, testing, approval, enablement and skills disabled in the local implementation.

## Home lifecycle

Application routing uses the URL hash without adding a router dependency. Home mounts on its first visit and remains mounted when hidden; background query/chat state is not disposed. Opening Plugins directly does not mount the Leaflet map or make map-tile requests. Completed geometry, tab contents and local component state are preserved within the existing session.

Leaving Home stops unfinished Geoman drawing/editing while retaining the committed rectangle. The hidden map does not process Escape keys or resize/focus actions against a zero-width container. Returning restores its viewport, resizes Leaflet, and applies a newer queued map command if a pending assistant reply produced one. Existing Home content remains inert while hidden.

## Verification

Use `npm run check` and the documented permitted Chromium override for `npm run test:e2e`. Tests cover catalog/local state separation, URL and credential rejection, corrupted storage, write failure, concurrency, unsupported backend operations, add/edit/remove UI, keyboard focus, mobile drawers, no external plugin requests, browser history, Home state preservation and background analysis/chat completion. Existing map/farm/advisory tests remain part of the full suite.
