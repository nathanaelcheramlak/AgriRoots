# Repository scripts

The active frontend is `../agrilo-fieldops-frontend/` inside this repository. See [current setup](../docs/getting-started.md).

- `evaluate.py`: deterministic backend advisory evaluations, including optional disposable PostgreSQL verification.
- `check_artifacts.py`: heuristic Git-visible secret/runtime artifact check.
- `legacy/`: retired launcher, clean-start and browser tools for the removed frontend. These are preserved as historical source, disabled before any setup or provider action. They are not part of current CI.

Current backend entry points remain in `backend/scripts/`. The current full-stack Home runner is `backend/scripts/check_home_browser.py`; current browser tests live in the frontend repository.
