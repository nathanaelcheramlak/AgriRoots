# Code and folder guide

[Documentation index](README.md)

| Location | Purpose |
| --- | --- |
| `frontend/src/` | React + Vite screens, navigation, and API calls. |
| `backend/src/api/` | HTTP routes and request/response schemas. |
| `backend/src/services/` | Application rules: accounts, records, advisory runs, review, and release. |
| `backend/src/agent/advisory/graph.py` | Current six-step LangGraph workflow. |
| `backend/src/agent/prompts.py` | Shared AI prompts and legacy diagnosis replies. |
| `backend/src/agent/orchestrator.py` | Older classify/execute chat graph; current chat does not call it. |
| `backend/src/mcp/` | Agent tool server, clients, evidence tools, and public-source restrictions. |
| `backend/src/integrations/` | Weather, soil, crop-health, language-model, speech, and SMS connections. |
| `backend/src/cli/` | Background worker, account provisioning, demo data, and verification commands. |
| `backend/src/common/` | Shared helpers, currently phone-number utilities. |
| `backend/src/db/` | SQLAlchemy models, database connections, and migrations. |
| `backend/tests/` | Backend tests. |
| `scripts/` | Demo launcher, evaluation, and browser workflows. |

SQLite is used for the demo; PostgreSQL verification is documented in [EVALS.md](../EVALS.md). Model/runtime versions and checksums are recorded in [backend/local_model.lock.json](../backend/local_model.lock.json).
