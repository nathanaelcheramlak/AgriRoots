# Getting started

[Documentation index](README.md)

The supplied launcher supports **Linux x86_64**. It does not run directly in Windows PowerShell; Windows and macOS need a compatible Linux environment or a separate manual setup and model-runtime build.

Requirements:

- Python 3.11–3.13, or Python 3.11+ with `uv` to provision Python 3.13.
- Node.js 22.12+ and npm.
- At least 2 GB free RAM and 3 GB free disk space.
- Internet access for installation, weather, and public reference material.
- Available ports `4173`, `8000`, and `8081`. No GPU or Docker is required.

From the repository root:

```bash
python3 scripts/demo.py
```

The launcher installs dependencies, downloads and verifies the local model, prepares a dedicated demo database, builds the frontend, and starts the services. Initial model/runtime downloads total about 660 MB, plus dependencies.

Wait for `READY`, then open [http://127.0.0.1:4173/workspace](http://127.0.0.1:4173/workspace).

| Demo role | Phone | Password |
| --- | --- | --- |
| Officer | `+251900000002` | `SyntheticDemo123!` |
| Farmer | `+251900000003` | `SyntheticDemo123!` |
| Administrator | `+251900000001` | `SyntheticDemo123!` |

These are public demonstration accounts. The launcher needs no cloud API keys: it creates local keys and **does not load `backend/.env` or inherit cloud credentials**.

Keep the terminal open. Press **Ctrl+C** to stop all services; run the command again to restart. Data, keys, model downloads, and logs persist in the ignored `backend/runtime/` directory.

### Try the officer-to-farmer workflow

1. Sign in as the officer and open `/workspace`.
2. Under **Agent advisory runs**, select **SYNTHETIC cluster** and start a run. CPU inference can take several minutes.
3. Inspect the evidence and draft in the review queue. Edit it or reject it if needed.
4. Approve the exact version, then choose **Release approved version to farmers**. Approval alone does not publish it.
5. Sign in as the farmer and open `/advisories` to read the released advice and play available audio.
