# Testing and troubleshooting

[Documentation index](README.md)

For the `agri-mcp` connector platform, run from `backend/`:

```powershell
uv sync --frozen
.\.venv\Scripts\python.exe -m pytest -q --junitxml=validation/agri-mcp-final.xml
.\.venv\Scripts\python.exe scripts/demo_connectors.py
```

To exercise real local PostgreSQL/Redis, start the dedicated test project and use the fixed disposable database helper. The helper never substitutes the operational `agrilo` database; its test fixtures drop application tables in `agrilo_test`.

```powershell
docker compose -p agrilo-connectors-test -f compose.yaml -f compose.test.yaml --env-file private-data/compose.env up -d postgres redis
.\.venv\Scripts\python.exe scripts/test_connectors_postgres.py
```

The tests do not invoke external providers or a real model. `scripts/demo_connectors.py --live` is a separate explicit public-provider probe. See [the observed connector report](../backend/reports/CONNECTOR_TEST_REPORT.md), [support/deployment](CONNECTOR_SUPPORT.md), and [security limits](TOOL_SECURITY.md). The original launcher checks below remain applicable to the existing local-Qwen workflow.

After demo setup, run these from the repository root on the supported Linux environment:

```bash
backend/runtime/demo-venv/bin/python scripts/evaluate.py
npm --prefix frontend run lint
npm --prefix frontend run build
```

To check startup and exit automatically, run `python3 scripts/demo.py --check` while no other demo launcher is running. For browser checks, clean-start verification, and recorded results, see [EVALS.md](../EVALS.md).

| Problem | Check |
| --- | --- |
| Startup fails on Windows/macOS | The supplied demo launcher requires Linux x86_64. |
| Port is occupied | Stop the conflicting service on `4173`, `8000`, or `8081`. |
| A run stays queued | Confirm the advisory worker is running. |
| A run needs information | Check current seasons, matching guidance/calendars, planting rules, and evidence dates. |
| Weather or public retrieval fails | Check connectivity and the run's recorded error. |
| Soil data is missing | Confirm which workflow is running; the current advisory graph does not fetch iSDA data. |
| Credentials appear ignored | The isolated demo deliberately ignores `backend/.env`. |

Logs are in `backend/runtime/api.log`, `worker.log`, `model.log`, and `frontend.log`.

## Optional browser recording

With the local system running, use `npm --prefix scripts/browser ci`, then set `CHROME_PATH` to your Chrome executable and run `npm --prefix scripts/browser test`. Tests create and release synthetic advisories; use the isolated local setup.

`npm --prefix scripts/browser run demo` records a new workflow in `backend/runtime/browser-recordings/officer-to-farmer.webm`. Recordings are generated locally and ignored by Git. Recording no longer uses or creates the root `demo/` folder. Historical JSON reports may still name legacy media paths in that folder.
