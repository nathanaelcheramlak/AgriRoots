# Submission description draft

Theme: climate-smart agricultural advisory support. Target: an Ethiopian extension-office workflow; the specific participating office is **unconfirmed**. This is a development demonstration with synthetic records, not a deployed or agronomist-validated service.

AgriRoots gives an extension officer a workspace for turning household and plot records into traceable climate advice. The officer selects a household cluster and asks the agent to identify observations needed for review. A local open-weights Qwen model plans evidence retrieval, drafts supported planting, hold or inspection decisions, and links each recommendation to dated sources. A LangGraph workflow gathers plot history, live weather, locally reviewed crop calendars and guidance, plus public soil-health background.

The application includes a custom MCP server with separate history, weather, crop-context and draft-saving tools. It also uses the independently maintained MCP Fetch server for public documents. The borrowed server receives approved public URLs without household data. Retrieval is constrained to reviewed domains and public network destinations. Every recommendation is checked against its office, plot, crop, season, dates, location and evidence freshness before a draft becomes reviewable.

The agent stops at pending review. An officer inspects evidence and uncertainty, edits or rejects the draft, approves an exact version, and separately releases it. Farmers see only released versions addressed to their household. Edits require fresh approval; historical versions and events remain inspectable. The agent has no tools for publication, purchases, credit or farmer messaging.

The demonstration uses CPU inference and requires no cloud language-model key. Small-model tests exposed invented claims of completed fieldwork, so farmer-facing wording is controlled and generated narrative remains private. Recorded evaluations distinguish deterministic integration tests from real inference runs. Original code is Apache-2.0 with owner-confirmed redistribution rights. Remaining work includes real-office feedback, agronomist assessment, native-speaker assessment of local speech, and deployment validation. Submission eligibility and a public demo URL must be confirmed before presenting this prototype as a competition entry.

## Submission checklist

- Real office name, contact and permission: pending owner input.
- Interviews / officer feedback / resulting changes: the owner confirms no feedback has been collected; none is claimed.
- Licence: original code is Apache-2.0; owner confirmed redistribution rights for included code/assets. Third-party terms remain applicable; see `THIRD_PARTY_NOTICES.md`.
- Demo media: the legacy root `demo/` folder has been removed. Historical run details remain in `EVALS.md` and `backend/validation/`; create a new local recording if needed. No public URL has been configured.
- In-country hosting and competition eligibility: unconfirmed.
