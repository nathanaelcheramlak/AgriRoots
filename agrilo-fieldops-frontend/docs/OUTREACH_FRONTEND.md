# AgriLo Outreach — frontend demonstration

Open `http://127.0.0.1:5175/#outreach` after `npm run dev`. Outreach joins Home, Plugins and Monitoring in the existing rail. Skills stays removed, following the user's later navigation preference. This frontend remains independent of AgriRoots; no backend, communication account, scheduler or agent was connected.

## Short demonstration

1. Choose **Weather & Rainfall Advisory**. Name the campaign and review the explicitly synthetic rainfall source. No current forecast or live AI output is claimed.
2. In Recipients, choose **DEMO-P0001**. This person has two registered demonstration farms; this source is restricted to **F-001**, and personalized guidance includes only that farm.
3. Keep SMS or choose Voice, Email or Smartphone messaging. Every channel says **Not configured**. Language preference is distinct from translation: non-English groups need officer-supplied wording and an explicit language review.
4. Inspect the source panel, edit the shared message, insert approved variables, and compare it with the preserved original template. Weekly templates also include editable conditional actions, reasons, source references and cautions.
5. Inspect advisory groups, representative rendered messages and exceptions. Missing evidence, conflicting farm conditions, unresolved placeholders and missing translations hold a group for further review.
6. **Save local campaign**, then **Submit for demo review**. Enter a local reviewer name/reason and acknowledge the exact recipients, exclusions, evidence, message and personalization before **Record demo approval**. The resulting label explicitly says it is not valid for delivery.
7. Edit the wording or recipients and **Save revision** with a reason. Previous versions and their decisions remain visible; the new version requires a new review. Duplicate, archive/restore and delete work locally.
8. Try **2,000 synthetic farmers**. Search/filter by crop, location, risk, stage, irrigation, monitoring flag, language or channel. Only 20 table rows render per page. Selection survives pagination. **Select all matching** captures concrete IDs; later search/filter changes cannot silently add people. Inspect consent/contact exclusions separately.
9. From Home, select an area or farm and choose **Prepare Farmer Guidance**. From a Monitoring result choose **Prepare Outreach**, or use **Prepare weekly guidance** on a sample report. The wizard receives a typed source/farm snapshot. Home retains its rectangle, viewport, selected farm, filters, chat, analysis and map size; background work continues.
10. In a Monitoring crop-photo viewer, enter officer notes, then choose **Prepare Feedback in Outreach**. The original uncertain observation and officer assessment remain separate. No photo bytes or object URLs are transferred.
11. Explore **Delivery History → Explore synthetic history** and **Farmer Responses → Explore synthetic inbox**. Provider acceptance is distinguished from delivery confirmation. Save a local response draft, inspection need or crop-case draft; **Prepare campaign reply** opens a new reviewable campaign. Nothing is transmitted.

## Recipient and evidence boundaries

The dataset has exactly 2,000 synthetic farmer identities. Farm associations are separate, including two people with multiple farms. There are no real names, phone numbers, email addresses, households or confidential contact records. Contact availability and channel consent are demonstration flags, never live eligibility evidence.

Eligibility checks officer exclusions, opt-outs, conflicting/unfinished records, contact availability, consent and language policy. The future review batch includes only eligible candidates. Agricultural evidence and language review are additional group-level requirements; contact eligibility does not establish that an advisory is supported.

Home and Monitoring mapping uses synthetic farm associations only when the originating context is explicitly synthetic. A real/HTTP Home farm is never matched to a demo person merely because its ID resembles F-001. Without an authenticated farmer/contact mapping, the wizard shows unmapped farm references and cannot invent recipients.

Imported source farm IDs constrain the campaign scope. A farmer's other registered farms are not silently included in personalization. Evidence records can identify the farm(s) they support; unavailable farm-specific observations hold the affected group. Generic synthetic context is used only for illustrative observation requests, not unsupported claims about individual fields.

The six template purposes are weekly guidance, weather, crop-health follow-up, irrigation review, inspection requests and custom composition. Six opt-in scenarios cover grouping, rainfall follow-up, crop correction, large populations, missing evidence and communication constraints. Counts come from the actual selected records. Synthetic histories are standalone examples, not the execution history of a saved local campaign.

## Guidance, corrections and review

The local generator is deterministic. It proposes safe observation/review requests and no fertilizer rates, pesticide dosages, irrigation quantities, exact application dates or confirmed diagnoses. Officer instructions remain text; no Gemini or LangGraph request executes.

Approved variables are farmer display label, crop, scoped farm IDs, location and officer-chosen follow-up date. Rendering is plain React text, without HTML execution or expression evaluation. Unknown/malformed variables and missing values remain visibly unresolved. Representative previews cover the exact group; all exceptions can be inspected in Recipients.

The original template, original source observation, officer corrections, edited actions and message revisions are separate records. Corrections require an assessment, reason, local reviewer and timestamp. Editing cannot silently rewrite an earlier source snapshot or revision.

Each saved version binds content, source, variables, channel, recipient selection and eligibility snapshot with local SHA-256 fingerprints. Decisions reference that exact version and recipient scope; restore validates the chain, snapshot and review target. These fingerprints provide local consistency checks, **not authentication or a backend approval**. Editing a saved configuration creates a new version; no previous review grants blanket approval.

Review choices include requesting evidence, rejecting with a reason and returning to draft. Group-specific decisions can be recorded independently. Held groups cannot receive a demo approval. All decisions carry `authority: local_demo`, and every delivery action remains unavailable.

## Channels and privacy

SMS previews estimate standard GSM-7 / Unicode segmentation, including two-unit GSM extension characters and UTF-16 surrogate pairs without splitting them across segments. Standard encoding capacities follow [Twilio's SMS encoding documentation](https://www.twilio.com/docs/glossary/what-sms-character-limit). Provider-specific headers, routing and smart encoding can change final counts; no provider pricing or cost estimate is invented.

Voice shows a script and **No audio artifact available**. It does not synthesize audio or initiate calls. Email shows subject/body and a demo recipient label without an address. Smartphone messaging reserves future provider-specific media capability; no attachment or incoming upload is invented.

Only metadata and text drafts are stored under `agrilo-fieldops:outreach:v1`. There are no credential/contact fields, image uploads or delivery records in the stored document. Known token/credential patterns, email addresses, recognizable phone formats, image/blob data and credential-bearing/query/fragment URLs in text are rejected. Pattern validation cannot identify every possible opaque secret or private fact; officers must keep confidential information out of prototype notes.

Strict Zod restore rejects extra runtime/approval/delivery/image fields, malformed data, unknown recipient identities, duplicate scope, invalid version chains and changed review targets. Writes are serialized, stale edits are rejected, and storage failure leaves the form open with an error. Local limits are 25 campaigns, 20 retained versions per campaign, 200 decisions per campaign and 100 response follow-ups; browser quota may be reached earlier.

Home/Monitoring context transfer is memory-only until an officer saves a campaign. Refreshing an unsaved handoff can lose that context. Campaign drafts and response notes survive reload when storage is available. Monitoring photo data remains governed by its existing session-only lifecycle.

## Service and future backend integration

`src/features/outreach/` contains schemas/models, deterministic recipients/templates, grouping, eligibility, variable rendering, SMS estimates, immutable local versions, review decisions, fixtures, Zustand state and typed context transfer. `src/components/outreach/` contains the navigation, six-step wizard, campaign details, paginated recipient picker, editor, previews, review queue, history and sample inbox. Existing management dialogs and controls are reused.

`OutreachService` isolates local storage and demo operations. `OutreachBackend` is the proposed HTTP adapter boundary. Its discovery, snapshot, campaign, AI generation, approval, connector, delivery and response operations all return `BACKEND_REQUIRED` without making requests. Device-draft schemas and authoritative server response types are distinct. A demo decision ID is never a backend approval ID.

### Existing contracts inspected — not invoked

- The isolated frontend's `docs/FRONTEND_BACKEND_CONTRACT.md` describes its independent analysis/assistant adapters and proposed advisory routes.
- AgriRoots `backend/src/api/routes/workspace.py` provides office-scoped advisory version/create/update/transition operations.
- `backend/src/api/routes/advisory_run.py` provides office-scoped advisory runs under `/api/workspace/offices/{office_id}/runs`.
- `backend/src/api/routes/voice.py` exposes voice services, and `backend/src/services/delivery_policy.py` requires the review workflow for legacy advice/delivery paths.

None of those routes was connected or changed. Existing advisory/run concepts are not assumed to be Outreach campaigns or authorized delivery batches.

### Proposed additions — no implemented route URLs

The new boundary describes authenticated recipient discovery with pagination, server-controlled membership/consent snapshots, source-linked campaign generation, exact immutable group/message approval, approved connector discovery, explicit idempotent dispatch and authoritative delivery/response retrieval. Endpoint paths must be agreed with the backend rather than invented by this frontend.

Before production communication, backend services must validate office/farmer access, contact and consent freshness, source provenance and agronomic validity, translations, exact message/personalization/recipient versions, reviewer authority, connector health/approval, provider costs/limitations, explicit release and audit/idempotency rules. Confirmed delivery needs provider evidence; acceptance alone is insufficient. Private contacts, media and credentials require secure server storage and authorized intake.

## Verification

Run `npm run check` and `npm run test:e2e`. The README documents the permitted Windows Chromium executable override. Tests cover 2,000-person pagination/filtering, stable scope, deduplication, exclusions, group holds, safe variables/HTML, SMS encoding, source/correction preservation, exact-version review invalidation, persistence/corruption/quota failures, local response notes, unsupported backend operations, Home/Monitoring handoffs, mobile focus/layout and existing workspace regression. Actual observed results are recorded in `docs/VERIFICATION.md`.
