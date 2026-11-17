# FieldOps repository consolidation

At the user's request on 2026-11-17, the current FieldOps frontend is included directly in the AgriRoots GitHub repository under `agrilo-fieldops-frontend/`. It is a normal tracked directory, not a submodule or nested Git repository. The retired `frontend/` remains removed; its old Android wrapper is not restored.

```text
AgriRoots/
  backend/                    API, LangGraph, approved providers/tools/skills
  agrilo-fieldops-frontend/    Current Home, Plugins and Skills application
  docs/                       Contracts and phase verification reports
  scripts/                    Evaluation and archived legacy tooling
  .github/workflows/          Backend and frontend checks
```

The original standalone frontend checkout in the workspace parent is retained as a local backup with its own history, including local snapshot commit `4d54677`. It is no longer the canonical application path. No `.git`, `node_modules`, browser reports, screenshots, databases, private environment, login password or provider credential was copied into the tracked frontend. The parent editor workspace now points to the frontend inside AgriRoots.

The integration runner resolves `AgriRoots/agrilo-fieldops-frontend` from `backend/`; frontend checks run from that directory in the root GitHub workflow. Existing Home, Plugins and Skills contracts and model policy remain unchanged. Phase reports describe verification done before consolidation; their current links/commands now point within this repository. Historical references to separate repositories describe that earlier layout.

From the repository root:

```powershell
cd agrilo-fieldops-frontend
npm ci
$env:VITE_API_MODE = 'http'
$env:VITE_API_BASE_URL = '/backend'
$env:FIELDOPS_BACKEND_URL = 'http://127.0.0.1:8000'
npm run dev
```

From `backend/`, run the bounded fixture integration using:

```powershell
.\.venv\Scripts\python.exe scripts/check_home_browser.py --skills
```

Provider keys and local test administrator records stay in the existing ignored backend configuration/database. The local test account is now provisioned by explicit user authorization; its password is not part of Git. Live-model verification is still pending Gemini configuration. Monitoring/Outreach remain local drafts; no delivery or scheduling was added during consolidation.
