# Testing and troubleshooting

[Documentation index](README.md)

## Current frontend

From `agrilo-fieldops-frontend/` inside this repository repository:

```powershell
npm ci
npm run check
npm exec playwright install chromium
npm run test:e2e
```

`check` runs typecheck, lint, unit tests and build. The default browser suite tests demo mode; dedicated Home-backend tests skip unless started by the isolated runner below. Frontend CI runs these checks in the frontend's own repository.

## Backend and full-stack Home

From `AgriRoots/backend`, using the installed test environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_home_integration.py -q
.\.venv\Scripts\python.exe scripts/check_home_browser.py
```

The browser runner needs both sibling repositories, frontend dependencies and Playwright Chromium. It starts a temporary fixture database, real auth and LangGraph worker, explicit fixture model and HTTP provider servers. It does not seed the operational database, invoke live models or consume provider credits. Four scenarios cover successful evidence/navigation, mobile, partial provider failure and backend cancellation.

For Phase 2, run `scripts/check_home_browser.py --plugins` with the same interpreter. This adds the real local MCP SDK fixture and isolated administrator login, and runs the four Home scenarios plus six Plugins scenarios. The default demo browser suite intentionally skips these ten backend-connected scenarios. See the [Plugins verification report](PHASE2_PLUGINS_INTEGRATION.md).

For Phase 3, use `scripts/check_home_browser.py --skills`. It retains the Home/Plugins coverage and adds five Skills scenarios for handoff, dependencies, dates, administrator lifecycle and mobile/session isolation. The default demo suite now intentionally skips all fifteen dedicated backend scenarios. See the [Skills report](PHASE3_SKILLS_INTEGRATION.md).

For broader connector and explicit PostgreSQL tests, see [connector support](CONNECTOR_SUPPORT.md). Backend CI retains `scripts/evaluate.py` on SQLite and disposable PostgreSQL plus `scripts/check_artifacts.py`; it no longer installs the removed frontend or runs its cold-start workflow. The cross-repository Home runner is a local integration check, not claimed as backend CI coverage.

`scripts/check_artifacts.py` writes a validation report; inspect its diff before committing. Provider/network probes and real model evaluations are separate explicit checks. Do not automatically spend Kindwise credits or run expensive Earth Engine operations.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Login fails | Existing officer phone/password and office membership; no public demo password is assumed |
| Backend unavailable | API target and proxy configuration; no mock fallback |
| Model blocked | Backend key, explicit model, execution permission and data policy |
| Job stays queued | Connector worker and database/queue health |
| No available skill | Current registry, exact-version approval, enabled state and credentials |
| No farms | Authorized office records; do not seed operational data to hide missing records |
| Basemap tiles missing | Choose Street layer; tiles are separate from agricultural evidence |
| Old `/workspace` or Android UI missing | Retired; not yet fully recreated in the new UI |

Old launcher, clean-start and recording tools are disabled in `scripts/legacy/`. Historical [evaluations](../EVALS.md) remain evidence from the older revision, not proof of the new UI. Use a separate checkout of the matching revision to reproduce them.
