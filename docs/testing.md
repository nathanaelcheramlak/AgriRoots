# Testing and troubleshooting

[Documentation index](README.md)

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
