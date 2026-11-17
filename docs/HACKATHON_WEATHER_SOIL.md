# Hackathon: real-farm weather and soil

The user explicitly requested real environmental evidence for selected registered farm locations, narrowing the hackathon scope to weather forecasts and soil profiles. This supersedes the earlier synthetic-only restriction **for this environmental-evidence workflow**, without authorizing private farmer/household/profile context to the cloud model.

## Current behavior

The ignored local Compose environment selects `CLOUD_MODEL_DATA_POLICY=environment_only`. Code and Compose retain `synthetic_only` as the default for other installations. Restart API/worker/MCP after changing this setting.

- Home presents three existing approved workflows: **Weather & soil**, **Soil profile**, **Weather forecast**. Duplicate provider-pack workflows and other agricultural capabilities are omitted from this Home projection, not deleted or silently approved.
- The saved plot's authorized interior sampling point is bound to the existing controlled tools server-side. Client coordinates cannot replace it. Location is visible to the signed-in officer and sent to the reviewed environmental providers.
- Gemini receives the question, approved weather/soil function declarations and minimized environmental function responses. No registry farmer name, contact, household reference, free-text note, plot boundary, private crop/observation context or exact plot coordinates are added to its prompt. The existing function-response minimizer removes coordinates and URL query parameters from model-visible provider results.
- Other required capabilities/internal actions are rejected in this mode. Optional non-environmental tools are excluded from the model's pinned tools. Existing approval, office/territory authorization, consent, network, credit, queue, cancellation and evidence gates remain.
- Checkpoints from a previous data-policy prompt cannot be resumed into the environmental-only model context. Start a new investigation instead.
- Soil is a **mapped estimate**, not a soil forecast or laboratory measurement. Weather is a gridded forecast, not an on-farm sensor observation. No crop suitability or planting recommendation is invented from those two datasets alone.

## Actual live verification — 17 November 2026

Registered record: **Farm 122**, permanent plot ID `00eb15aa-23f0-441d-9db7-42a8000c0399`. It remained non-synthetic; no farmer record was relabelled or replaced with a fixture.

The first authorized run, `dc5b6ffa-07d8-4279-ae94-85ff0fa1ee0f`, fetched valid live Open-Meteo and iSDAsoil responses. Its model answer failed numerical validation because the validator omitted the actual provider retrieval timestamp from its numeric source set. That failed job remains failed.

The correction adds only authoritative retrieval/observation/range metadata to numerical validation. It does not permit fabricated measurements or arbitrary rounded values. Regression tests accept the genuine retrieval timestamp and reject an invented timestamp value.

Retest `94951114-f793-4c41-b664-924a35f9b4fc` **succeeded**, using the configured real `gemini-3.8-flash` model through the existing manual function-calling workflow. Both outcomes were SUCCESS/VALID, classified `live`. Both retest outcomes were **cache hits**, reusing the live provider responses fetched moments earlier, not making a second fresh provider fetch.

| Evidence | Actual result |
| --- | --- |
| Open-Meteo `f51ca91b-460b-41c1-a5b1-10d5aa597b3e` | Forecast 17–19 November 2026: rainfall 0, 0.1, 0 mm; maximum temperature 22.8, 23.1, 24.1 °C. No forecast uncertainty interval or issue time supplied. |
| iSDAsoil `8fe4761f-63d6-4ae6-98cf-42aabd742a28` | Mapped 0–20 cm soil pH 6.1, organic carbon 19.1 g/kg, with provider confidence intervals retained. Field observation dates were not supplied. |

The answer passed existing evidence-ID/numerical checks and preserved units, limitations and source references. Provider/model cost was not supplied and is not assumed to be zero. No farmer messaging/advisory release occurred.

## Verification

- Existing companion/Home/citation regressions: 21 passed before the metadata correction.
- Environmental-policy and citation checks including the metadata correction: 10 passed.
- Frontend: 127 tests passed; typecheck and lint passed.
- Policy checks cover real registered farm execution through fixture providers/model, exclusion of private/coordinate context, rejection of unrelated capabilities, and optional tool filtering. Fixture tests are distinct from the live Farm 122 run above.

To try it: refresh Home, select a saved farm, open **AI Chat**, choose **Weather & soil**, authorize the agricultural-provider/configured-AI request, and ask: “Show this farm's weather forecast and mapped soil profile, with dates, units and limitations.”
