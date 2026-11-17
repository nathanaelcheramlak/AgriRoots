# First Gemini walkthrough — 2026-11-17

The user configured Gemini in the ignored backend Compose environment and authorized a sample investigation. Model metadata access confirmed `gemini-3.8-flash` supports `generateContent`. Model execution was enabled explicitly in private configuration; API and connector worker were restarted without seeds, account resets, provider credential writes, or changes to the selected model/data policy. The frontend remains available at `http://127.0.0.1:5175/`.

## Actual results

- Skill: `fieldops_agricultural_context`, an existing approved enabled workflow requiring forecast and mapped soil evidence.
- Context: existing **synthetic Adama API validation plot**, not a verified real farm.
- Authorization: network and Gemini enabled for these bounded runs; credit authorization false, no image, Earth Engine or delivery operation requested.
- First job `87edb08b-1eab-4118-baa4-835f55479f1c`: failed final answer validation. Both controlled tool operations succeeded with VALID live-origin evidence. The answer cited real evidence IDs but also named the authorized plot UUID; the validator incorrectly classified that context reference as fabricated evidence. A numbered Markdown section heading was also incorrectly treated as a measured number. The failed job was preserved as failed.
- Retest job `5f0e8303-25d8-432e-b61a-f9f718462f82`: **succeeded**, real `gemini-3.8-flash` using the existing Google SDK/manual function-calling graph. Two outcomes were SUCCESS/VALID and the generated answer passed evidence-ID and numerical validation.
- Evidence: Open-Meteo `a910a733-b977-4d30-a7ee-02c3b6149f5a`, retrieved `2026-11-17T05:07:44.429474+00:00`; iSDAsoil `2c2b44d0-b1ee-47d5-8c32-7d465bbe88a5`, retrieved `2026-11-16T19:16:36.160685+00:00`. **Both retest outcomes were cache hits.** Their live-origin classification and original provenance were preserved; fresh upstream reachability was not established by this test.
- Exact private receipts and request keys are retained only under ignored `backend/private-data/`; no key, password or bearer token is included in this report or written to frontend configuration. Actual model cost was not supplied by the provider and is not assumed zero.

## Narrow validation correction

`validate_claims` now receives only server-authorized plot IDs from the existing authorized records. Those references are distinct from evidence IDs. At least one real run evidence ID is still required when evidence exists; unknown IDs remain blocked. Authorized reference IDs are excluded from numerical-value matching, and Markdown heading/list ordinal markers are treated as presentation rather than measurements. Numerical claims in body text and heading content remain validated against source data.

Six negative/positive regression cases cover authorized plot plus real citation, plot-only citation rejection, unknown reference rejection, fabricated measurement rejection, Markdown ordinals and fabricated measurements within numbered headings. Combined with existing companion and Home integration tests: **21 passed**, recorded in `backend/validation/live-gemini-citation-regression.xml`.

No model fallback, removed schema constraint, fabricated evidence, automatic approval or weakened farm authorization was introduced. The graph/executor approval gates and cloud synthetic-only policy remain active. These validation changes and this report are new local changes following the previously pushed consolidation commit; they are not automatically committed/pushed.

## Suggested UI checks

Sign in, click Home's availability Refresh, select the synthetic Adama plot and use Skills → agricultural context → Open skill in Home. Ask for forecast rainfall and mapped pH with evidence and uncertainty. Explicitly authorize the selected model/providers and submit one question. Expect an actual durable job, provider outcomes, two evidence cards, original retrieval dates/cache labels and numerical values from evidence. A cached answer source is not a fresh observation.

Next safe functional checks are the existing weather forecast, soil profile, climate history with `start=2025-07-01`/`end=2025-07-07`, and pest taxonomy with `eppo_code=BEMITA`. Provider availability remains office/credential/version dependent and failures or NO_DATA must remain explicit. Photo diagnosis needs its separate private-image and credit authorization workflow. Satellite/raster operations are not part of this first walkthrough.

The previous Phase 1 model/account blocker is now resolved for a real-model **synthetic-context** walkthrough. Real-farm scientific efficacy, real-household model use, fresh health of every provider, scheduling and farmer delivery remain unverified/out of scope.
