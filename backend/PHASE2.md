# Phase 2: evidence-gathering advisory agent

This is the Phase 2 implementation record. The final application also supports office-reviewed planting/hold rules, per-plot drafting/checkpoints, local released-only speech, explicit cost assumptions and PostgreSQL verification. Use the root README and `../EVALS.md` for the current setup, measured results and remaining external checks.

Phase 2 adds a local-model LangGraph workflow and real MCP stdio tools. It creates sourced inspection advisories and stops at **Pending review**. Phase 1's authenticated officer approval and separate release remain required. It has no tools for approval, publication, farmer messaging, ordering inputs or credit.

## Local setup

From `backend/`, activate the backend Python environment, copy `.env.example` to `.env` if needed, replace the JWT placeholder, and install:

```bash
pip install -r requirements.txt -r requirements-phase2.txt
python -m src.db.schema_migrations
```

Revision 3 preserves existing data and adds durable runs, tool-call logs, run/evidence links and a public guidance cache. Run migrations once before starting multiple workers.

The tested local CPU configuration is pinned in `local_model.lock.json`:

- Model: [Qwen/Qwen3-0.6B-GGUF](https://huggingface.co/Qwen/Qwen3-0.6B-GGUF/tree/23749fefcc72300e3a2ad315e1317431b06b590a), Q8_0, revision `23749fefcc72300e3a2ad315e1317431b06b590a`, Apache-2.0.
- Server: [llama.cpp b11429](https://github.com/ggml-org/llama.cpp/releases/tag/b11429), CPU Linux x86_64 build, MIT. Download hashes are recorded in the lock file.
- Settings: four CPU threads, one inference slot, 8,192 context tokens, temperature zero, seed 42, thinking disabled, at most 1,400 output tokens. Application context is capped at 24,000 characters; the model sees concise evidence extracts while the officer can inspect the stored supporting snapshots.
- Downloads: approximately 640 MB of model weights and 18 MB of compressed runtime. Runtime files, API keys and databases are ignored by Git. Allow approximately 2 GB of available memory for this small configuration; actual capacity depends on host load and context size. The validation host had 12 GB RAM and an Intel i3-1315U CPU, without a discrete GPU.

Start the verified model in one terminal:

```bash
python scripts/local_model.py
```

The script downloads immutable revisions, checks SHA-256 digests, creates an API key in ignored `runtime/model-api-key`, and binds inference to `127.0.0.1:8081`. The backend uses that key file; it never sends it to the browser or a public MCP server. For other platforms, build the pinned llama.cpp revision and configure a loopback server with equivalent settings.

Start the API and queue worker in separate terminals, using the same environment and database:

```bash
python -m uvicorn src.main:app --host 127.0.0.1 --port 8000
```

```bash
python -m src.cli.advisory_worker
```

`--once` processes one queued or expired run and exits. The worker automatically recovers expired leases after a process restart. No in-memory background task is required to retain a queued run.

Configuration overrides:

```env
ADVISORY_MODEL_URL=http://127.0.0.1:8081
ADVISORY_MODEL_ID=qwen3-0.6b-q8
ADVISORY_MODEL_REVISION=23749fefcc72300e3a2ad315e1317431b06b590a
# Optional absolute path; the default is backend/runtime/model-api-key
# ADVISORY_MODEL_KEY_FILE=/absolute/path/to/model-api-key
ADVISORY_MODEL_TIMEOUT=180
ADVISORY_RUN_TIMEOUT=600
ADVISORY_TOOL_TIMEOUT=45
ADVISORY_MAX_TOOL_CALLS=32
ADVISORY_COMPUTE_COST_PER_HOUR=0
```

Only literal loopback HTTP origins are accepted for model inference. Proxies and redirects are disabled on model requests, served model identity is checked, and LangSmith tracing is disabled for the graph. There is no Gemini/cloud fallback. The application runs inference on this local host; an operator must verify the physical location of a deployed host before claiming in-country hosting.

## Use the workflow

1. At `/workspace`, enroll officer/farmer accounts and create a cluster, linked households, plots and one current crop season per plot. Current seasons require planting and harvest dates; zero previous yields are distinct from missing yields.
2. Add a locally reviewed guidance record and calendar matching each crop and agroclimatic zone. Select the inspection actions that the local guidance supports. Calendars must cover the recorded planting and harvest dates. Local review dates must be within the previous year.
3. Under **Agent advisory runs**, select a cluster and submit a task. The current bounded implementation supports one to five plots; larger contexts can return a request to select a smaller cluster.
4. Inspect model planning, tool calls, retrieved evidence, warnings, failures, token usage and cost assumptions. Retry after correcting missing records or resolving an unavailable provider. A run has at most three attempts.
5. Open the saved advisory in the review queue. Inspect the full sources and every recommendation citation, edit if needed, approve the exact version and separately release it. The farmer sees nothing before release.

This first autonomous path deliberately drafts **inspection and officer follow-up actions**: crop inspection, drainage inspection, heat-stress observation and field visits. Local guidance must explicitly support the chosen action. It does not autonomously prescribe pesticide or fertilizer quantities. The model selects the action, supplies a private drafting rationale, and links current evidence. Deterministic code renders the supported action, title, uncertainty and required follow-up. Generated prose is retained in private run logs for officer inspection and is excluded from advisory content. Model output is validated again inside the write tool and before submission.

English drafting is supported. Any Amharic translation is added to the reviewed advisory version through Phase 1; the agent does not translate a released version.

## MCP integrations and network boundaries

The custom `farmly-advisory` MCP server is run by `python -m src.mcp.server` with a per-attempt run capability supplied by the worker. It exports exactly:

| Tool | Behavior |
| --- | --- |
| `get_cluster_plot_history` | Reads only the initiating officer's office/cluster records and stores history evidence. |
| `get_weather_evidence` | Fetches Open-Meteo forecasts for authorized coordinates, checks returned location/units/values, and stores dated snapshots. A fresh, explicitly synthetic forecast record may be used for synthetic households only. |
| `get_crop_risk_context` | Finds matching reviewed guidance/calendars and surfaces recorded pest signals and conflicts. |
| `save_advisory_draft` | Independently validates every citation and persists one draft linked transactionally to the run. Repeating it returns the same advisory. |

Every call rechecks the capability hash, lease, active initiating officer, office membership and call budget. Office/run identity cannot be overridden through tool arguments. Inputs and outputs use Pydantic schemas, including typed plot/season results. A tool client timeout and whole-run timeout bound execution. Weather has one bounded retry; it does not fabricate fallback forecasts.

The independently maintained server is **[Model Context Protocol Fetch](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch)**, published by Anthropic / the MCP reference-server maintainers under MIT. Tested pins: `mcp-server-fetch==2026.10.10`, `mcp==1.29.0` (the Fetch release requires SDK 1.x). Its [published package](https://pypi.org/project/mcp-server-fetch/2026.10.10/) implements robots checks, HTTP retrieval and HTML-to-Markdown simplification. Reusing this maintained parsing/robots implementation avoids rebuilding a document-fetching server. The actual `fetch` MCP tool was exercised against the configured public source, rather than replaced with an HTTP helper.

The operator-reviewed source catalogue is `src/mcp/public_sources.py`, initially [USDA NRCS soil-health background](https://www.nrcs.usda.gov/conservation-basics/natural-resource-concerns/soil/soil-health). This is general supporting context, not Ethiopian crop-specific agronomic authority. Applicable actions must separately cite the office's local guidance and calendar. The stored extract retains the source attribution and retrieval date.

The borrowed subprocess receives fixed public catalogue URLs, never the officer's task, household records, coordinates, capabilities or app credentials. It has a fresh empty working directory and a minimal environment. It uses an authenticated CONNECT proxy that permits only exact reviewed domains on HTTPS port 443. Each redirected connection is checked; all DNS answers must be public and a validated literal IP is used for the actual socket connection. Private, loopback, metadata, multicast and special-use destinations are denied. Response bytes and connection time are bounded. Do not add domains without reviewing their suitability and extraction rights.

Public extracts are cached for at most 30 days with hash, original retrieval time, server version and attribution. Logs distinguish cache hits from a live borrowed-server fetch. Retrieved text is untrusted evidence and cannot add tools or permissions. No retrieved-document prompt is executed as an instruction.

## Validation and recovery

For each recommendation the deterministic validator requires matching history, weather, local guidance, calendar and public-document evidence. IDs must belong to this run and office, and match plot, crop, coordinates, zone, season and proposed date. Weather must be no older than six hours and use the expected units. Expired evidence, invented IDs, unsupported action codes, past/out-of-season dates and unsupported numerical prescriptions block the draft. Free-form generated titles, rationale, uncertainty and missing-information claims are not copied into the advisory. Conflicting pest signals require an officer field visit.

Checkpoints follow successful graph steps; run leases prevent concurrent workers from owning the same attempt. The draft/run link commits in one transaction. Recovery after a lost save response returns that same draft, then revalidates evidence before moving it to review. An expired-evidence failure requires corrected records or a new run; recovery never silently publishes an old recommendation. Existing officer edits are preserved and the agent cannot submit their newer version automatically.

Logs are office-private and include run/officer identity, validated tool inputs, stored results, start/end times, failures, attempts, duration, model token usage and an estimated local-compute cost. A zero hourly rate is an explicit default assumption, not a measured claim of free infrastructure. No API keys or run capabilities are included in the run API or validation reports.

## Synthetic demonstration and checks

For a new local database:

```bash
export DATABASE_URL=sqlite:///./runtime/demo.db
python -m src.cli.seed_phase2
```

Use the synthetic credentials from [Phase 1](PHASE1.md), start the API/worker against that same database, and use `/workspace`. The seed creates current crop records and local guidance; weather is retrieved live by default. It refuses to seed over existing users.

With the real model server running, a reproducible CLI check is:

```bash
DATABASE_URL=sqlite:///./runtime/demo.db python -m src.cli.check_advisory_run --output runtime/my-run-result.json
```

The command refuses household data that is not labelled synthetic. It records actual statuses, calls, duration, usage and errors. It does not approve or release an advisory. Saved real-run results are in `validation/`; initial failures are retained rather than described as successes. This is a functional verification, not the repeated model evaluation or submission packaging planned for Phase 3.

Automated checks:

```bash
python -m pytest -q
cd ../frontend
npm run lint
npm run build
```

The suite uses a test model and cached public fixtures for deterministic workflow tests, but exercises the real MCP stdio server for scoped tools and draft writes. Live model/public-server verification is recorded separately. Migration and concurrency tests currently run on SQLite. Phase 3 now records real browser end-to-end testing in `../EVALS.md`. PostgreSQL execution, agronomist feedback and broader model-quality evaluation remain unverified.

Phase 3 also isolates the borrowed server from Node/npm to select its supported pure-Python document extractor. This avoids readabilipy's automatic, unpinned npm installation and stdout diagnostics during first extraction. A fresh actual Fetch MCP retrieval under this configuration is recorded in `validation/phase3-borrowed-fetch.json`.

The real small-model checks exposed an additional limitation: the model repeatedly described inspections as already completed despite missing field observations. The rejected attempt is preserved in `validation/phase2-narrative-validation-failure.json`. The final implementation retains model prose privately, warns the officer, and renders advisory language from controlled templates instead. This bounds the model to supported inspection-action selection and citations; it does not establish reliable unrestricted agronomic prose generation.

Validation on 15 October 2026: 47 automated tests passed, frontend lint/build passed, and a real Qwen run completed in 81.52 seconds for one synthetic household/plot and saved a pending-review version with five evidence references. Its public guidance was a cache hit from the independently verified Fetch MCP server; the earlier fresh-fetch run is retained alongside the model's narrative-validation failure. This is a single-host functional measurement, not a five-plot latency claim. See `validation/phase2-live-run.json` for actual calls, usage and the saved controlled-text recommendation. The temporary inference process used for verification was stopped afterwards; `scripts/local_model.py` starts it again.
