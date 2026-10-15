# Recorded evaluations

Results are from 15 October 2026. Final checks are recorded below; Phase 2/3 results are retained as historical measurements. Households, plots, crop history and office guidance are explicitly synthetic. Tests verify software behavior and evidence controls; they do not establish agronomic accuracy, farmer benefit or real-office adoption.

## Deterministic integration suite

Command: `backend/runtime/demo-venv/bin/python scripts/evaluate.py` after demo setup. Current results: [`final-integration.json`](backend/validation/final-integration.json) and [`final-postgres.json`](backend/validation/final-postgres.json). **60 tests pass with zero failures and zero skips on each of SQLite and PostgreSQL 18.6.** The earlier 48-test result remains in `phase3-integration.json`. It uses an explicit test model, synthetic forecasts and cached source fixtures while invoking the real custom MCP server over stdio. A passing task below means the expected control worked, including refusal when appropriate. Latencies are recorded per task in the JSON; they are not inference timings.

| Task | Expected and observed behavior | Result |
| --- | --- | --- |
| Complete consistent records | Real custom MCP creates one persisted sourced version and stops at pending review | Pass |
| Missing plot history | `needs_information`; no advisory persisted | Pass |
| Stale weather | Validator rejects weather retrieved more than six hours ago | Pass |
| Weather unavailable | Two bounded weather attempts, then explicit failure without a draft | Pass |
| Conflicting pest reports | Conflict is visible; field visit accepted, ordinary inspection rejected | Pass |
| Unsupported advice / invented evidence | Unsupported action, numerical prescription, wrong plot/crop/date or invented IDs rejected | Pass |
| Cross-office access | HTTP 403 for office records, versions, events and private run access | Pass |
| Unapproved release | Release denied before approval; farmer sees no draft or merely approved version | Pass |
| Edit after approval | New draft version requires approval; released history preserved | Pass |
| Repeated run / concurrent release | Same request returns same run; eight concurrent releases yield one release event | Pass |
| Malicious source and model output | Source instructions do not grant permissions; added release/recipient fields rejected | Pass |
| Restart after draft save | Expired attempt resumes the existing draft without a duplicate; old capability fails | Pass |
| Fresh and legacy migrations | Revisions 1–3 applied idempotently; legacy row and chat fields preserved | Pass |
| Reject / cancel / correct | Reasons and versioned corrections preserved in audit history | Pass |
| Unverified generated claims | Private narrative retained; invented completed-inspection claims excluded from advisory | Pass |
| Synthetic bootstrap login | All three seeded accounts log in through the API with completed onboarding | Pass |

The authorization test substitutes a provider to assert exact reviewed text and version/language audit metadata. Separate real tests synthesize English and Amharic with local eSpeak NG and check non-silent PCM. Actual browser playback is recorded in the final section below. Restart evaluation simulates interruption at a persisted checkpoint and expires its lease; it is not a machine power-loss test. Fresh/legacy frozen migrations and concurrent release are now verified on both SQLite and PostgreSQL, including separate native PostgreSQL schemas.

## Real model and browser execution

No model test double or intercepted API is used for saved real runs. Configuration: Qwen3-0.6B Q8_0 at immutable revision `23749fefcc72300e3a2ad315e1317431b06b590a`, llama.cpp b11429, Linux x86_64, Intel i3-1315U, 12 GB host RAM, CPU only, four inference threads, one slot, 8,192-token context, temperature 0, seed 42, at most 1,400 output tokens. The historical runs below each contain **one synthetic household, one plot and one current maize season**. The later capacity check explicitly measures five plots.

| Run | Actual result | Measurement / artifact |
| --- | --- | --- |
| Phase 2 final controlled-text run | Pending review; five citations | 81.52 s; [`phase2-live-run.json`](backend/validation/phase2-live-run.json) |
| Phase 3 browser correction workflow | Real draft; evidence inspection, rejection, version-two correction, approval, release and recipient view pass | 101.734 s end to end, including scripted officer actions; [`phase3-browser.json`](backend/validation/phase3-browser.json) |
| Phase 3 initial continuous take | Real draft; evidence inspection, approval, release and recipient view pass | 91.895 s; [`phase3-demo-initial.json`](backend/validation/phase3-demo-initial.json); video superseded by the readable final take |
| Phase 3 final continuous take | Real weather timeout and recovery; draft, evidence inspection, approval, release and exact recipient-version check pass | 132.489 s browser workflow; 132.36 s video; [`phase3-demo.json`](backend/validation/phase3-demo.json), [`demo/phase3-inspection.webm`](demo/phase3-inspection.webm) |

The browser run spent 11.129 s planning and 77.477 s drafting, with 492 and 1,946 total tokens respectively. It retrieved weather live; public guidance was a valid cache hit. The public cache was populated by a genuine Fetch MCP call during startup. A separate fresh live retrieval with the restricted pure-Python parser is recorded in [`phase3-borrowed-fetch.json`](backend/validation/phase3-borrowed-fetch.json): 4,000 characters, attributed source and SHA-256 digest, no household input.

The browser checks actual officer login and cluster selection, readable activity/evidence, rejection and correction, exact-version approval, separate release, farmer viewing and HTTP 403 for private run logs. Without speech credentials the actual audio request fails cleanly and the UI keeps the released text readable. **That historical run did not verify playback; the final browser run below does.** Screenshots are saved alongside the reports. These are scripted review actions, not review by a participating extension officer or agronomist.

The run reports record zero estimated USD because the configured hourly compute rate is zero. This is an explicit accounting assumption, not a claim of free infrastructure. To estimate inference cost, multiply measured model-call seconds by the operator's hourly host rate and divide by 3,600; electricity, idle time, downloads and external provider fees are not included.

The four current controlled-text runs all selected crop inspection and reached pending review. The three Phase 3 repetitions used the same synthetic plot and task, fresh live weather and cached public guidance; model planning/drafting together took 88.606 s, 82.605 s and 88.171 s respectively. The final recording includes 19 seconds of readable pauses in the scripted review. Its first real weather call failed after 15.277 s, then the bounded retry succeeded in 2.039 s. Generated private narratives varied and still contained unsupported completed-fieldwork claims in both recorded repetitions. The final video uses the host's installed FFmpeg because the optional Playwright encoder download remained busy; it is unedited and has no synthetic narration or substituted model output.

The current one-plot measurements are below fifteen minutes on this host. They do **not** establish the target for a five-plot cluster, concurrent officers, another machine, a cold model or unreliable connectivity. The repeated sample is small and no confidence interval or general success rate is claimed. Initial implementation failures are retained separately rather than pooled into a misleading success percentage.

## Observed failures and changes

- [`phase2-initial-plan-failure.json`](backend/validation/phase2-initial-plan-failure.json): the model repeated a tool. Planning now chooses the first tool while code requires all evidence categories.
- [`phase2-context-timeout.json`](backend/validation/phase2-context-timeout.json): verbose context timed out. Concise evidence summaries reduced the prompt.
- [`phase2-schema-compatibility-failure.json`](backend/validation/phase2-schema-compatibility-failure.json): llama.cpp rejected a boolean schema item. The grammar now uses a typed string item and independently validates IDs.
- [`phase2-narrative-validation-failure.json`](backend/validation/phase2-narrative-validation-failure.json): draft and repair both invented completed fieldwork. **Unrestricted factual prose generation is still unreliable.** Controlled advisory wording prevents those claims from reaching recipients; the next step is an agronomist-labelled factuality set and testing larger, suitable open models against it before expanding the action catalogue.
- [`phase3-seed-login-failure.json`](backend/validation/phase3-seed-login-failure.json): real browser login exposed a plus-prefix mismatch in seeded phone storage. The seed now uses the same normalizer as registration, and all seeded logins are checked in regression tests and readiness.
- First-start public parsing launched an unpinned npm installation and polluted MCP stdout. The borrowed subprocess now has an empty executable search path, uses its supported Python parser and was verified by a fresh live retrieval. This preserves the independent MCP server without runtime npm installs.

## Startup, artifacts and remaining release gates

Earlier Phase 3 validation exercised the native launcher with a freshly created Python environment and synthetic database, and cached dependencies/model downloads. The fresh seeded startup reached readiness in 42.19 s (`phase3-fresh-startup.json`); the final restart with persisted data also passed and was stopped cleanly after recording. The latest readiness record is `final-startup.json`. A separate `--check` invocation also passed and shut down automatically. The full 48-test suite passed inside the launcher's new locked environment. Saved startup reports identify cache scope rather than claiming an uncached clean-VM test. At that stage frontend lint/build passed with a 563 kB main-chunk warning; the final changes below remove that warning. The artifact check scans Git-visible text for common credential patterns and rejects visible environment/databases/runtime directories; it is a heuristic check, not proof against every secret or personal datum.

The owner confirmed code/asset redistribution rights and authorized Apache-2.0 for original code; `LICENSE`, `NOTICE` and `THIRD_PARTY_NOTICES.md` record that decision and retain third-party terms.

Outstanding external checks: real target-office identification and feedback; agronomist assessment of rules and speech pronunciation; public repository/video hosting; verified host country and competition eligibility. A fully uncached separate-host run is provided as an opt-in CI job but has not been run remotely. The owner confirms no officer feedback has been collected.


## Final code-gap verification

| Additional task | Actual result | Evidence |
| --- | --- | --- |
| Planting versus hold | Five integration cases cover suitable weather, insufficient/excess rainfall, excessive heat and wind. Opposite actions are rejected; calendar/forecast coverage is checked. | `test_reviewed_planting_rules_drive_sourced_decisions`, `test_planting_rules_are_required_and_weather_window_is_complete` |
| Five-plot context and citations | Each plot gets its own bounded draft/checkpoint, one recommendation and five applicable citations; rerun creates no duplicate advisory. | `test_five_plots_have_independent_citations_and_resumable_drafts` |
| Local speech | Real English/Amharic non-silent WAV synthesis passes; language/length limits reject invalid requests. | `test_local_speech.py` |
| Startup weather failure | Recovers on one retry, or fails explicitly after two attempts. A real startup timeout exposed this missing readiness retry. | `test_readiness.py` |
| PostgreSQL portability | Initial run: 45 passed, 10 failed due to an oversized per-plot stage label. Label bounded; final complete suite: 60 passed. Native fresh and legacy schema migrations also pass. | `final-postgres-initial-failure.json`, `final-postgres.json` |
| Isolated-source startup | Fresh source, Python environment, npm cache/dependencies, database, secrets and model extraction passed in **56.94 s**. Host prerequisites, wheel cache and checksum-verified model archives were reused. Services shut down after readiness. | `final-clean-start.json`; this is not a separate VM or fully uncached-download claim |
| Real five-plot run | **219.75 s**, pending review, five recommendations, **25 evidence snapshots**, no tool failures. Cluster is **one synthetic household with five plots**, with live weather and a public-source cache hit. | `final-five-plot-run.json` |
| Real planting browser task | **54.716 s**, sourced `hold_planting`, evidence inspection, rejection/correction, approval, explicit release and exact recipient-version check passed. Real local audio decoded and advanced during browser playback; private run logs were denied to the farmer. | `final-browser.json` |

The five-plot run used **217.511 model seconds**. At the explicitly assumed **$0.10/hour** host rate, estimated inference is **$0.006042**, or **$0.006104** across the measured run wall time. These are scenario estimates, not observed billing; provider fees, idle time, electricity and first-start downloads are excluded. A zero configured rate is now shown as **unpriced**, with no claim of free hosting. The CLI records counts, latency, rate and exclusions for each new run.

Planting thresholds in the demonstration are **synthetic software fixtures, not validated agronomic defaults**. Production use requires locally reviewed thresholds and field confirmation. The model's unrestricted factual prose weakness remains unresolved; controlled actions/reasons keep those claims out of released advisories. The new planting support does not add pesticide, fertilizer, market, purchasing or credit automation.

The React chat route is now loaded on demand: the main frontend bundle fell from approximately **563 kB to 375 kB**, with a separate approximately 187 kB chat chunk. Frontend lint/build pass without the prior large-chunk warning. CI is pinned to immutable action commits, runs both database suites and frontend checks, and offers an explicit full-download/model/browser job. Remote CI execution is not claimed.


The final **85.56-second continuous demo** (`demo/officer-to-farmer.webm`, `final-demo.json`) shows a real planting/hold task, a **15.242-second weather failure followed by a 1.162-second successful retry**, evidence inspection, explicit approval/release and real local audio playback. Browser workflow time was **85.304 seconds**, including readable pauses. No frames were edited or accelerated. The earlier 132.36-second inspection demo remains in `demo/phase3-inspection.webm`.

`final-audio.json` separately verifies actual released-only endpoint synthesis, exact-version/language/actor audit metadata, and a decodable 54.857-second English WAV (`demo/released-example.wav`). It is a synthetic demonstration artifact, not a claim of validated pronunciation or real officer endorsement.
