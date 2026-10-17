# Data, integrations, and configuration

[Documentation index](README.md)

The repository contains both the current officer workflow and older direct-advice integrations. Their status differs:

| Source or feature | Current behavior | Credentials |
| --- | --- | --- |
| Open-Meteo weather | Used by the advisory agent. Explicitly marked synthetic forecast fixtures can be used for synthetic households. | No key in the current integration |
| Farm records and local guidance | Stored in the database and maintained through the office workspace. Demo records are synthetic. | Authorized office account |
| Public soil-health reference | Retrieved as background material; it is not a measurement of a farmer's soil. | No key |
| iSDA soil properties | Implemented in older recommendation services; not called by the current advisory graph. | `ISDA_USERNAME`, `ISDA_PASSWORD` |
| Kindwise crop diagnosis | Implemented, but the direct diagnosis route is blocked pending the review workflow. Not an advisory-agent tool. | `KINDWISE_CROP_HEALTH_API_KEY` |
| Local sorghum and enset classifiers | Retained for the older diagnosis workflow; not required by the advisory demo. | Local model files and servers |
| Gemini | Retained for older chat/recommendation functions; the current advisory agent uses local Qwen. | `GEMINI_API_KEY` |
| Released-advice audio | Local eSpeak NG by default; cloud speech is optional. | None for local audio |
| General chat | Answers a small educational catalogue and queues farmer-specific requests for officer review. | Speech credentials if using transcription |

Adding API credentials does not enable blocked routes or add tools to the advisory graph.

### Manual configuration

For manual backend startup, copy [backend/.env.example](../backend/.env.example) to `backend/.env`, replace the JWT placeholder, and start commands from `backend/`. Settings read `.env` from the working directory. API credentials belong on the backend.

Optional settings include soil and diagnosis credentials, Gemini, SMS Ethiopia for normal phone OTP registration, and Google/Hasab speech. Local advisory audio is selected with `ADVISORY_AUDIO_PROVIDER=local`.

See [manual model and worker setup](../backend/PHASE2.md) and [account and office provisioning](../backend/PHASE1.md). These files retain earlier implementation details; the status table above describes the current workflow. The frontend example is [frontend/.env.example](../frontend/.env.example).
