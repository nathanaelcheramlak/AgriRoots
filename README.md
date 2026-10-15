# AgriRoots

**Evidence-based agricultural advisories for Ethiopian extension offices.**

AgriRoots helps extension officers turn household and plot records, weather forecasts, and reviewed guidance into planting, hold, and crop inspection advice. A local AI agent gathers evidence and prepares a draft. An officer reviews and approves an exact version, then explicitly releases it to the intended farmers.

The current release is a local prototype with synthetic households and demonstration guidance. Field validation and feedback from a participating extension office are pending.

[Quick start](#quick-start) · [Workflow](#usage-and-human-in-the-loop-workflow) · [Architecture](ARCHITECTURE.md) · [Evaluations](EVALS.md) · [Demo recording](demo/officer-to-farmer.webm)

## Problem statement

Extension officers need to combine household and plot histories, changing weather, crop calendars, and local guidance before issuing advice. AgriRoots addresses the challenge of collecting that evidence, keeping decisions traceable, and ensuring that officers review advice before farmers receive it.

## Solution overview

AgriRoots provides a shared advisory workspace. A local agent gathers five categories of evidence, proposes a structured draft for each plot, and saves validated advice for review. Versioned approval, explicit release, and recipient access connect each farmer-facing advisory to its evidence and responsible officer.

## Target users

| User | Role in the workspace |
| --- | --- |
| Extension officers | Maintain plot context, initiate agent runs, review evidence, correct drafts, approve versions, and release advice. |
| Farmers | Read released advisories addressed to them and listen to available audio. |
| Office administrators | Provision accounts and manage office memberships and access. |

These are intended roles; the demonstration uses synthetic accounts and has not established real-office adoption.

## Features

- **Sourced drafts:** each plot's advisory references history, weather, office guidance, a crop calendar, and public background material.
- **Planting and inspection workflows:** planned crops receive planting or hold decisions based on officer-entered rules; growing crops receive inspection advice.
- **Officer approval and release:** versioned edits, rejection reasons, separate approval and release actions, and an audit trail.
- **Farmer access:** recipients see only released advisories addressed to their accounts.
- **Local AI and audio:** Qwen3 runs on the CPU; released advice supports English and Amharic speech through local eSpeak NG.
- **Recoverable processing:** a durable queue, per-plot checkpoints, retries, and execution limits support interrupted runs.

## Quick start

### 1. Check the requirements

| Requirement | Supported configuration |
| --- | --- |
| Operating system | Linux x86_64 |
| Python | Python 3.11+ with `uv` to provision Python 3.13, or Python 3.11–3.13 with `venv` and `pip` |
| Frontend tools | Node.js 22.12+ and npm |
| Available resources | At least 2 GB free RAM and 3 GB free disk space |
| Network | Internet access for installation, live weather, and public guidance |
| Available ports | `4173`, `8000`, and `8081` |

A GPU and Docker are not required. Recorded CPU runs used an Intel i3-1315U with 12 GB RAM. Other platforms require a separate build of the pinned llama.cpp runtime.

### 2. Start the system

From the repository root:

```bash
python3 scripts/demo.py
```

The launcher installs locked Python and npm dependencies, downloads and verifies the model and runtime, migrates and seeds a dedicated SQLite database, builds the frontend, and starts all services. The first download includes approximately 640 MB of model weights and an 18 MB runtime, plus dependencies.

Wait for:

```text
READY: http://127.0.0.1:4173/workspace
```

Open [http://127.0.0.1:4173/workspace](http://127.0.0.1:4173/workspace). Keep the terminal running while using the app.

No manual `.env` setup or cloud API keys are required for the local demonstration. The launcher creates local authentication and model keys, uses its own synthetic database, and excludes inherited cloud credentials. All services bind to loopback.

### 3. Sign in

| Role | Phone | Password |
| --- | --- | --- |
| Officer | `+251900000002` | `SyntheticDemo123!` |
| Farmer | `+251900000003` | `SyntheticDemo123!` |
| Administrator | `+251900000001` | `SyntheticDemo123!` |

These accounts are public fixtures for the isolated demonstration.

### 4. Stop or restart

Press **Ctrl+C** in the launcher terminal to stop all child services. Run the same command to restart.

The database, keys, downloads, and logs persist in the ignored `backend/runtime/` directory. Existing demo records are preserved; keep this directory out of published artifacts.

## Usage and human-in-the-loop workflow

1. **Select a cluster.** Sign in as the officer, open `/workspace`, and choose **SYNTHETIC cluster** under **Agent advisory runs**.
2. **Gather evidence.** Start a run and inspect its progress, tool calls, warnings, and evidence snapshots. CPU inference can take several minutes.
3. **Review the draft.** Inspect the saved advisory in the review queue. Correct it by creating a new version, or reject it with a reason.
4. **Approve and release.** Approve the exact version, then select **Release approved version to farmers**. Approval and release are separate actions.
5. **View as a farmer.** Sign in as the farmer and open `/advisories` to read the released advice, inspect its evidence, and play its audio.

Edits require fresh approval. Earlier releases and audit history remain available. The agent's permissions end at draft creation; approval and release belong to the officer.

General chat provides an educational catalogue and queues household-specific requests for officer review. Legacy direct recommendation, diagnosis, alert, and arbitrary speech-delivery routes require review. The legacy sorghum and enset classifiers are not required for this workflow.

Watch the [recorded officer-to-farmer workflow](demo/officer-to-farmer.webm), including a planting/hold decision, weather retry, review, release, and local audio playback. The recording uses a real agent run and scripted officer actions; it does not represent agronomist endorsement.

## Architecture and technology stack

| Component | Responsibility |
| --- | --- |
| React + Vite frontend | Officer workspace, advisory review, and farmer views |
| FastAPI backend | Authentication, scoped access, records, approval, release, and audio |
| LangGraph worker | Evidence collection, draft generation, validation, and recovery |
| Qwen3-0.6B Q8_0 + llama.cpp | Local planning and structured draft candidates |
| MCP tools | Office records, weather evidence, crop context, draft storage, and public document retrieval |
| SQLite / PostgreSQL | Records, queue state, advisory versions, evidence, and audit events |
| eSpeak NG | Local speech for released advice |

Planning and drafting use the pinned local model. SQLite is the default for the demonstration; PostgreSQL is covered by the recorded integration suite. Model and runtime versions, revisions, and checksums are defined in [backend/local_model.lock.json](backend/local_model.lock.json).

See [ARCHITECTURE.md](ARCHITECTURE.md) for component relationships, access boundaries, evidence validation, and recovery behavior.

## Agent architecture

The [LangGraph advisory agent](backend/src/agent/advisory/graph.py) runs inside a durable background worker. Its processing stages are:

```mermaid
flowchart LR
    History[Read authorized history] --> Plan[Model plans evidence priority]
    Plan --> Gather[Gather evidence through MCP]
    Gather --> Draft[Draft each plot and attempt one repair]
    Draft --> Validate[Validate evidence and advisory]
    Validate --> Review[Save draft for officer review]
```

Local Qwen3-0.6B Q8_0 supplies planning choices and structured candidates. Code checks evidence identity, scope, dates, freshness, citations, and permitted actions before storage. Database leases and saved per-plot checkpoints support recovery; bounded contexts, tool calls, retries, and execution time limit each run. Generated factual narrative remains private when it cannot be verified. The agent has no approval or release tools.

## MCP implementation

AgriRoots uses the **Model Context Protocol (MCP)** to connect the worker to separate tool servers over stdio. The [MCP clients](backend/src/mcp/clients.py) initialize sessions, discover tools, and invoke them during each run. The [custom server](backend/src/mcp/server.py) exposes typed input schemas and returns structured results.

Custom calls recheck the initiating officer, office scope, run capability, and active lease. The independent Fetch server receives fixed public URLs without household context. A restricted proxy validates domains and resolved public IP addresses and bounds network traffic. Retrieved public background is attributed and stored as evidence.

### MCP tools and servers

| Server | Tool | Purpose |
| --- | --- | --- |
| Custom advisory server (`src.mcp.server`) | `get_cluster_plot_history` | Read authorized cluster, plot, and season history. |
| Custom advisory server | `get_weather_evidence` | Retrieve dated forecasts and persist weather evidence. |
| Custom advisory server | `get_crop_risk_context` | Retrieve reviewed guidance, calendars, and pest signals. |
| Custom advisory server | `save_advisory_draft` | Validate citations and persist an idempotent draft for review. |
| Independent MCP Fetch server (`mcp_server_fetch`) | `fetch` | Retrieve approved public background documents through the restricted proxy. |

The custom and independent servers are spawned for each run. Neither server grants the agent permission to approve or release an advisory. Tool validation is implemented in [advisory_tools.py](backend/src/mcp/advisory_tools.py); public retrieval restrictions are documented in [ARCHITECTURE.md](ARCHITECTURE.md).

## Configuration

The demo uses [backend/requirements-demo.lock](backend/requirements-demo.lock), [frontend/package-lock.json](frontend/package-lock.json), and the local model lock. Its runtime is isolated from the backend `.env` file.

For manual setup, administrator provisioning, optional integrations, and deployment configuration, see:

- [Backend setup and office workflows](backend/PHASE1.md)
- [Local model, agent, and MCP configuration](backend/PHASE2.md)
- [Environment variable examples](backend/.env.example)
- [Third-party components and model provenance](THIRD_PARTY_NOTICES.md)

Local speech is the launcher's default. A manual deployment can select `ADVISORY_AUDIO_PROVIDER=cloud` with the appropriate speech dependencies and credentials. The original classifier dependencies are retained separately in `backend/requirements.txt`.

For planned seasons, officers must supply a matching reviewed calendar and complete planting rules: rainfall window, minimum and maximum accumulated rain, maximum temperature, and maximum wind. Rules must come from the cited guidance. Missing evidence blocks drafting; unsuitable conditions produce a hold decision, and conflicting pest reports require a field visit.

## Verification

After the launcher has created the demo environment, run the integration suite and frontend checks from the repository root:

```bash
backend/runtime/demo-venv/bin/python scripts/evaluate.py
npm --prefix frontend run lint
npm --prefix frontend run build
```

To check startup readiness and shut down automatically, run this command while no other demo launcher is running:

```bash
python3 scripts/demo.py --check
```

For the browser workflow, keep the demo running in another terminal:

```bash
npm --prefix scripts/browser ci
CHROME_PATH=/path/to/chrome npm --prefix scripts/browser test
```

Replace `/path/to/chrome` with your Chrome executable. The browser check creates and releases synthetic advisories, exercises rejection and correction, and verifies farmer viewing and audio playback. Use it against the local demo only.

To verify startup from a separate source tree:

```bash
python3 scripts/verify_clean_start.py --reuse-model-downloads
```

Omit `--reuse-model-downloads` to download the model and runtime again. See [EVALS.md](EVALS.md) for PostgreSQL checks, capacity fixtures, recorded failures, timings, cost measurements, and reproducibility limits. PostgreSQL tests require an explicit disposable database because they drop and recreate application tables.

To record a new demonstration:

```bash
cd scripts/browser
npx playwright install ffmpeg
npm run demo
```

The recording is saved to `demo/officer-to-farmer.webm`; reports and screenshots are saved under `backend/validation/`.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Port already occupied | Stop the service using `4173`, `8000`, or `8081`, then restart the launcher. |
| Dependency or model download fails | Check access to PyPI, npm, GitHub, and Hugging Face. |
| Readiness fails | Inspect the service logs and connectivity to Open-Meteo and the configured public guidance source. |
| Existing synthetic seasons have expired | Update their records in the workspace before restarting. |
| Partial seed or login failure | Inspect the reported error; the launcher preserves existing data rather than overwriting it. |

Read service logs from the repository root:

```bash
tail -n 80 backend/runtime/{api,worker,model,frontend}.log
```

Readiness checks cover seeded logins, authenticated model identity, both MCP stdio connections, live weather, public guidance, and frontend/API availability. An unavailable upstream source can prevent startup even when local services are running.

## Limitations

All demonstration households and local guidance records are synthetic. Weather is live and dated; public NRCS material provides attributed soil-health background. A participating office, officer feedback, field effectiveness, and public hosting remain unconfirmed.

Testing exposed unsupported fieldwork claims in generated narrative. That narrative stays in private logs; validated, controlled wording supplies farmer-facing actions, reasons, and uncertainty. Planting eligibility follows officer-entered rules, with no universal agronomic thresholds. Pesticide and fertilizer prescribing remain outside the current scope. English and Amharic audio playback has been recorded, while pronunciation quality still requires native-speaker review.

Recorded results and reproducibility limits are maintained in [EVALS.md](EVALS.md). To attach an assumed compute rate to a local run:

```bash
python3 scripts/demo.py --compute-cost-per-hour 0.10
```

This sets an assumed USD 0.10/hour compute rate for inference estimates. The default is **unpriced**. Estimates exclude electricity, idle time, downloads, and external provider fees.

## Future improvements

The following are proposed next steps, rather than completed capabilities:

- **Field validation:** partner with an extension office and agronomists to evaluate the workflow, guidance, and farmer usefulness.
- **Model evaluation:** build an agronomist-labelled factuality dataset and compare suitable larger open models before expanding the supported action catalogue.
- **Language quality:** obtain native-speaker review of Amharic translations and pronunciation, and improve reviewed audio content.
- **Capacity and resilience:** measure concurrent officer workloads, larger plot sets, and behavior under intermittent connectivity.
- **Deployment readiness:** validate production hosting, operational monitoring, backups, and office onboarding before a public rollout.

## License

Original code is licensed under [Apache License 2.0](LICENSE). See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and third-party terms. Submission notes and outstanding submission facts are maintained in [SUBMISSION.md](SUBMISSION.md).
