# Execution path and agent design

[Documentation index](README.md)

```mermaid
flowchart LR
    Officer[Officer starts a run] --> API[FastAPI]
    API --> Queue[(Database queue)]
    Queue --> Worker[Background worker]
    Worker --> Agent[LangGraph advisory agent]
    Agent --> Draft[Draft awaiting review]
    Draft --> Review[Officer reviews and approves]
    Review --> Release[Officer explicitly releases]
    Release --> Farmer[Farmer reads or listens]
```

The current advisory workflow has **one agent with six processing steps**, rather than six separate agents:

| Step | Responsibility |
| --- | --- |
| `history` | Read authorized plots and crop seasons. |
| `plan` | Ask local Qwen to order the three required evidence sources. |
| `gather` | Collect weather, reviewed guidance/calendars, and public references. |
| `draft` | Check permitted actions, ask Qwen for a candidate per plot, validate it, and allow one repair attempt. |
| `save` | Validate again and store the draft without duplicating it on retry. |
| `review` | Submit it to the officer's review queue. This step does not approve it. |

Qwen3-0.6B Q8_0 runs locally through llama.cpp. Code checks evidence, dates, citations, and permitted actions. Farmer-facing advice uses controlled wording; unverified model narrative remains in private run logs. The agent cannot approve or release advice.

Progress is saved in the database so the worker can recover interrupted runs. The current workflow supports clusters of one to five plots.

### Agent tools

MCP (Model Context Protocol) connects the agent to these tools:

- `get_cluster_plot_history`: farm and crop-season records.
- `get_weather_evidence`: dated forecasts for plot coordinates.
- `get_crop_risk_context`: reviewed guidance, crop calendars, and recorded pest signals.
- `save_advisory_draft`: validated draft storage.
- Independent MCP `fetch`: approved public reference documents through a restricted proxy.

See [ARCHITECTURE.md](../ARCHITECTURE.md) for permissions, evidence validation, and recovery details.
