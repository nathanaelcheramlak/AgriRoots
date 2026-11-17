# AgriRoots

AgriRoots helps Ethiopian extension officers prepare farming advice from plot records, weather forecasts, and reviewed local guidance. A local AI agent creates a draft; an officer reviews, approves, and releases it to the intended farmers.

**Status:** local prototype with synthetic demonstration records. Field validation with an extension office is pending.

This repository houses the backend, current FieldOps frontend and their documentation. The current frontend is [agrilo-fieldops-frontend](agrilo-fieldops-frontend); the older `frontend/` and Android wrapper were retired. See the [workspace structure](docs/WORKSPACE_STRUCTURE.md) and [current Home integration guide](agrilo-fieldops-frontend/docs/PHASE1_HOME_INTEGRATION.md).

The backend includes a registry-driven companion with reviewed REST/MCP connectors, reusable skills, configuration-only plugin packs, and PostgreSQL/Redis deployment. Start with [connector support](docs/CONNECTOR_SUPPORT.md) and the [integration audit](docs/FRONTEND_BACKEND_INTEGRATION_AUDIT.md). Existing farmer review and release rules still apply.

See [repository consolidation](docs/REPOSITORY_CONSOLIDATION.md) for the canonical layout and setup commands.

## Main features

- Farm, household, plot, and crop-season records.
- Weather-based planting, hold, and crop-inspection drafts with evidence references.
- Officer review, versioned corrections, approval, and explicit release.
- Farmer access to released advice and available English/Amharic audio.
- Local Qwen inference, a LangGraph background worker, and MCP evidence tools.

## Documentation

| Read this | To learn |
| --- | --- |
| [Getting started](docs/getting-started.md) | How to run the local system and try the workflow |
| [Configuration](docs/configuration.md) | Which APIs are used and where credentials belong |
| [Agent workflow](docs/agent-workflow.md) | How requests move through LangGraph and MCP |
| [Code guide](docs/code-guide.md) | What each folder does |
| [Testing](docs/testing.md) | How to verify changes and troubleshoot |

See the [documentation index](docs/README.md) for architecture and recorded evaluations.

Use [Getting started](docs/getting-started.md) for the current backend/frontend setup. The retired demo launcher and browser tools are archived under `scripts/legacy/` and disabled; their historical results do not verify the new UI. Local Qwen advisory execution remains unchanged in the backend. Current Home live use still requires authorized login and backend model configuration.

## Current limits

The system needs internet access for weather and uncached public references. Local guidance in the demonstration is synthetic. Field effectiveness and speech pronunciation still need review. Fertilizer and pesticide prescribing are outside the current advisory workflow.

## License

Original code is [Apache-2.0](LICENSE). See [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md) for attribution and upstream terms.
