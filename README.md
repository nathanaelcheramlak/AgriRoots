# AgriRoots extension-office advisory workspace

An Ethiopian extension-office prototype for sourced planting/hold decisions and crop inspection: select a household cluster, gather evidence with a local open-weights agent, inspect a sourced draft, approve an exact version, then explicitly release it to its farmer recipients. The agent stops at officer review. The demonstration uses labelled synthetic households and reviewed demonstration guidance; no real participating office or field validation is claimed.

## Start the local demonstration

From the repository root:

```bash
python3 scripts/demo.py
```

Requirements: Linux x86_64, Python 3.11+ plus **uv** (recommended; selects Python 3.13), or Python 3.11–3.13 with venv/pip; Node.js 22.12+ and npm; an internet connection. Tested host: Intel i3-1315U, 12 GB RAM, CPU only. Allow at least 2 GB free RAM and 3 GB free disk for dependencies, caches and inference. GPU support is not required. Other platforms require a separately built pinned llama.cpp runtime.

First start installs exact Python/npm dependencies, downloads approximately 640 MB of weights and an 18 MB runtime, verifies checksums, runs migrations, creates a dedicated synthetic database and builds the frontend. Download time depends on the connection. The launcher waits for usable login accounts, authenticated model identity, both real MCP stdio handshakes, live weather, public guidance and frontend/API readiness. An unavailable upstream source prevents readiness. Later starts reuse database/model storage; the frontend build is reproducible through `npm ci`.

Open **http://127.0.0.1:4173/workspace** after `READY` appears. All services bind to loopback. The native launcher is intended for a local demo, and does not require Docker.

| Account | Phone | Password |
| --- | --- | --- |
| Officer | +251900000002 | SyntheticDemo123! |
| Farmer | +251900000003 | SyntheticDemo123! |
| Administrator | +251900000001 | SyntheticDemo123! |

These public credentials are only for the isolated demo. The launcher creates random local authentication/model keys and strips cloud credentials from the synthetic runtime. It does not use an existing production database or backend `.env`. Press Ctrl-C to stop all child services. The SQLite database, keys, downloads and service logs persist in ignored `backend/runtime/`; do not publish that directory. Existing demo data is preserved. If synthetic seasons have expired, update their records in the workspace before restarting. A partial seed or broken login fails readiness instead of silently overwriting data.

For a readiness-and-shutdown check:

```bash
python3 scripts/demo.py --check
```

A failure points to logs in `backend/runtime/{api,worker,model,frontend}.log`. Ports 4173, 8000 and 8081 must be available. Initial downloads need public PyPI/npm/GitHub/Hugging Face access; advisory runs need Open-Meteo and approved NRCS guidance (or its valid cache). Startup from a separate source tree with a fresh Python environment, npm cache, database and keys passed in 56.94 seconds, reusing verified model downloads and Python package caches. A fully uncached Ubuntu CI job is provided in `.github/workflows/verify.yml`; its remote execution is not claimed.

## Demonstrate the workflow

1. Sign in as the officer; open `/workspace`. Under **Agent advisory runs**, choose **SYNTHETIC cluster** and start a run.
2. Inspect progress, model/tool calls, warning messages and the five evidence snapshots. Planned crops use explicit officer-reviewed planting rules to draft a plant/hold decision with numerical reasons. Growing crops receive inspection advice. The agent cannot approve or release advice.
3. Open the saved draft in the review queue. Edit into a new version or reject with a reason as needed. Approve the exact version, then separately select **Release approved version to farmers**.
4. Sign in as the farmer and open `/advisories`. Only released versions addressed to that account appear, with the reviewed wording and evidence.

Edits create a new draft requiring approval. Previous releases and audit history remain available. General chat provides a small educational catalogue and queues household-specific requests for the officer. Existing direct AI recommendation, diagnosis, alerts and arbitrary speech-delivery routes require review. The repository's legacy crop models are not needed by this demo.

Released audio works locally without cloud keys using pinned eSpeak NG in a bounded subprocess. English and Amharic synthesis and real browser audio playback are verified; pronunciation quality still needs native-speaker review. The endpoint synthesizes only the released action, reason and uncertainty or an already-reviewed translation, and records the exact version/language in the audit. Optional cloud speech requires `ADVISORY_AUDIO_PROVIDER=cloud`, legacy speech dependencies and provider credentials; the synthetic launcher always uses local speech.

## Reproduce verification

After startup has created the demo environment:

```bash
backend/runtime/demo-venv/bin/python scripts/evaluate.py
npm --prefix frontend run lint
npm --prefix frontend run build
npm --prefix scripts/browser ci
CHROME_PATH=/path/to/chrome npm --prefix scripts/browser test
```

The browser check uses actual login forms, a real model run, evidence inspection, rejection, correction, approval, explicit release and farmer viewing. It also decodes and plays real local speech. Default Chrome path: `/opt/google/chrome/chrome`. It creates and releases **synthetic** advisories, so run it only against the launcher's local demo. Browser dependencies are separate from production frontend dependencies.

To record an unedited demonstration with the same real agent and scripted officer controls:

```bash
cd scripts/browser
npx playwright install ffmpeg
npm run demo
```

The existing [unedited recording](demo/officer-to-farmer.webm) is **85.56 seconds**. It shows a real planting/hold decision, weather timeout and successful retry, readable review pauses and actual local audio playback. The earlier inspection recording is preserved as `demo/phase3-inspection.webm`. New recordings use that same path; reports and screenshots go to `backend/validation/`. The report measures runtime and flags whether the recording is under three minutes. Scripted review demonstrates the controls; it is not agronomist endorsement. Public hosting is not configured.

See [EVALS.md](EVALS.md) for real outcomes, failures, model repetition, latency and cost assumptions; [ARCHITECTURE.md](ARCHITECTURE.md) for trust boundaries and recovery; [SUBMISSION.md](SUBMISSION.md) for the description draft and outstanding submission facts; and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for provenance. Original code is licensed under [Apache-2.0](LICENSE), with owner-confirmed redistribution rights and third-party terms retained.

## Configuration and provenance

The one-command demo uses `backend/requirements-demo.lock`, the frontend npm lock, and `backend/local_model.lock.json`. Qwen3-0.6B Q8_0 runs through pinned llama.cpp on loopback, with four CPU threads, one slot and an 8,192-token context. Both planning and drafting use this model without a Gemini fallback. Custom and borrowed MCP servers are spawned over stdio within each run. SQLite stores durable queue state, immutable advisory versions, audit events and evidence.

Manual setup, administrator provisioning, optional integrations and production configuration are documented in [backend/PHASE1.md](backend/PHASE1.md), [backend/PHASE2.md](backend/PHASE2.md), and the secret-free [backend/.env.example](backend/.env.example). Original heavyweight classifier dependencies remain in `backend/requirements.txt`; the advisory demo deliberately has its own coherent lock.

Every demo household and local guidance record is synthetic. Weather is live and dated; public NRCS material is attributed general soil-health background. The model repeatedly invented claims of completed fieldwork during testing. Generated narrative is therefore kept in private logs; farmer-facing actions, titles, uncertainty and missing-information wording are controlled. Planting/hold eligibility comes from officer-entered rainfall, temperature, wind and calendar rules. No universal agronomic thresholds are supplied. Fresh demo thresholds are explicitly synthetic. Pesticide/fertilizer prescribing remains outside scope.

The specific target office remains unconfirmed, and no officer feedback has been collected. PostgreSQL 18.6 passed the same 60-test suite as SQLite, including fresh/legacy migrations and concurrent release. A real five-plot task completed in 219.75 seconds on the stated CPU host; this is one household with five plots, not a production SLA. Physical host country, production deployment and competition eligibility remain unverified. No public deployment URL or real-office use is claimed.


## Planting rules, capacity and cost

Set a season's stage to **planned** and enter a matching reviewed guidance/calendar with explicit planting/hold actions and a complete planting rule. Choose rainfall days (1–3), minimum/maximum accumulated rain, maximum temperature and wind. These values must come from the cited office guidance. The validator requires the full forecast window; unsuitable rain, heat, wind or dates produce a hold decision, and conflicting pest reports require a field visit. Rules and numerical reasons are preserved with the advisory's evidence. Growing seasons cannot receive planting instructions. Each plot is drafted and checkpointed independently, with exactly five matching citations.

Run `python3 scripts/demo.py --compute-cost-per-hour 0.10` to use an explicitly assumed $0.10/hour compute rate. Default cost status is **unpriced**, not free. Model logs and CLI reports record the rate, token usage, latency, inference estimate and exclusions. The five-plot check cost $0.006042 of inference in that scenario; this is not a measured hosting bill.

Additional reproducible checks:

```bash
python3 scripts/verify_clean_start.py --reuse-model-downloads
# Omit the flag to download model/runtime archives again.
AGRIROOTS_TEST_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@127.0.0.1:5432/DISPOSABLE_TEST_DB backend/runtime/demo-venv/bin/python scripts/evaluate.py --output backend/validation/my-postgres.json
```

The PostgreSQL test database is **disposable**: tests drop/recreate its application tables. They never use the normal `DATABASE_URL` as a test fallback. CI runs SQLite/PostgreSQL tests and frontend checks; its manually enabled cold-start job additionally downloads the real model and executes the browser workflow. GitHub Actions are pinned to immutable commits.

For a separate synthetic capacity fixture, run `python -m src.cli.seed_benchmark --plots 5` from `backend/` with your synthetic database configured, then pass its printed cluster ID to `python -m src.cli.check_advisory_run --cluster-id UUID --output validation/my-capacity.json`. Add `--planned` to seed planting/hold examples. The fixture refuses databases containing non-synthetic households and creates a separate labelled household/account. Reports state the actual household/plot counts, latency and cost assumptions. Never point these commands at production records.
