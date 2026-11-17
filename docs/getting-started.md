# Getting started

[Documentation index](README.md)

The active UI is `agrilo-fieldops-frontend/` inside this repository, running on port 5175. The old `AgriRoots/frontend`, Android wrapper and associated demo launcher were retired. The newer UI does not yet replace every old farmer or administration screen. The advisory backend remains intact.

## Backend

Use the existing backend deployment and private configuration described in [connector support](CONNECTOR_SUPPORT.md). Start the API and connector worker; reuse the authorized database and model configuration. Do not run seed/reset commands against an existing installation. An existing authorized officer phone/password is required. The Home companion also needs its explicitly configured model/key and permitted execution setting. Enabling frontend HTTP mode cannot supply these.

API normally runs at `http://127.0.0.1:8000`; API documentation is at `/docs`. Keep database, JWT, provider and model secrets on the backend. The local Qwen advisory workflow is a separate path and was not switched to make the Home demonstration pass.

## Frontend

Requires Node.js 22.12+ (Node 24 supported). In PowerShell from the AgriRoots repository root:

```powershell
cd agrilo-fieldops-frontend
npm ci
$env:VITE_API_MODE = 'http'
$env:VITE_API_BASE_URL = '/backend'
$env:FIELDOPS_BACKEND_URL = 'http://127.0.0.1:8000'
npm run dev
```

Open `http://127.0.0.1:5175/`, log in with an existing authorized officer account, select an authorized plot and available skill, provide required parameters, review explicit model/network consent and submit. Inspect actual job status, results and evidence. Visit another page and return to verify Home continuity. No messages are sent.

The same-origin development proxy forwards `/backend` to the API. Production hosting needs its own reverse proxy or allowed origin. Do not put secrets in `VITE_*` variables. For the full walkthrough, cancellation, fixtures and limitations, see the [Home integration guide](../agrilo-fieldops-frontend/docs/PHASE1_HOME_INTEGRATION.md).

For UI-only demo mode, use `VITE_API_MODE=mock` (the default) and restart Vite. Demo data is synthetic and separate from authenticated Home. Plugins, Monitoring and Outreach remain local drafts/demos in both modes.

Current live demonstration is blocked until authorized login and backend model configuration are available. Historical public demo credentials belong to the retired isolated launcher, not the operational database. Do not reset accounts or seed a database to recreate them.
