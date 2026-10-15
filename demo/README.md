# Continuous real demonstration

[Watch officer-to-farmer.webm](officer-to-farmer.webm) — **85.56 seconds**, recorded 15 October 2026.

This unedited recording shows actual officer login, synthetic cluster selection, a genuine Qwen/LangGraph/MCP planting/hold task, a real weather timeout with bounded recovery, visible tool calls, five evidence snapshots, the reviewed planting decision, scripted officer approval and separate release, then the farmer's exact released version and real local speech playback. Review steps have readable pauses. No frames were cut, sped up or substituted. Playwright recorded continuous headless Chrome output using the host's system FFmpeg; the video has no captured audio track or narration.

[Listen to released-example.wav](released-example.wav) for the actual local speech output of this released synthetic version. Browser tests verified HTML audio decoding/playback; `final-audio.json` also verifies exact-version audit metadata. Pronunciation still needs native-speaker assessment.

All household data, planting thresholds and local guidance are **synthetic software fixtures**. Weather was live; public background was a valid cache hit populated through the real borrowed Fetch MCP server. This demonstrates review controls, not endorsement by an extension officer or agronomist. No officer feedback has been collected. No public hosting URL is claimed.

Results: [`final-demo.json`](../backend/validation/final-demo.json), [`final-browser.json`](../backend/validation/final-browser.json), [`final-audio.json`](../backend/validation/final-audio.json). The prior [132.36-second inspection demo](phase3-inspection.webm) is preserved with its historical `phase3-demo.json` report.

Reproduction commands are in the root README. `npm run demo` overwrites the main recording with a new continuous real run and records actual timings/failures. Cloud keys are unnecessary; an officer must still approve and explicitly release the synthetic advisory.
