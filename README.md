# AgriRoots

AgriRoots helps Ethiopian extension officers prepare farming advice from plot records, weather forecasts, and reviewed local guidance. A local AI agent creates a draft; an officer reviews, approves, and releases it to the intended farmers.

**Status:** local prototype with synthetic demonstration records. Field validation with an extension office is pending.

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

The supplied launcher supports Linux x86_64 and runs with `python3 scripts/demo.py`. It uses an isolated environment and ignores `backend/.env`. The current advisory agent uses weather; soil API and photo-diagnosis integrations remain outside that workflow. See the configuration guide for details.

## Current limits

The system needs internet access for weather and uncached public references. Local guidance in the demonstration is synthetic. Field effectiveness and speech pronunciation still need review. Fertilizer and pesticide prescribing are outside the current advisory workflow.

## License

Original code is [Apache-2.0](LICENSE). See [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md) for attribution and upstream terms.
