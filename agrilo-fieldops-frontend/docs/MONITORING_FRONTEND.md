# Monitoring — local frontend workspace

Start the independent frontend with `npm run dev` and open `http://127.0.0.1:5175/#monitoring`. The global rail contains Home, Plugins, and Monitoring. Monitoring replaces the Scheduled placeholder. No sibling project, environment file, scheduler or backend was connected.

## Demonstration walkthrough

1. Choose **Daily Weather & Rainfall Watch**. The seven-step wizard opens with a template preset. Give it a name and continue.
2. Select synthetic farms, a snapshot of the current Home area/selected farm, a saved geographic selection, or the named demonstration group. Assigned-officer farms are unavailable until authenticated data exists. Inspect the farm names, crops, and source labels.
3. Select example capabilities. Each explicitly says **Not connected**. Natural-language planning notes remain text; they are not parsed into an AI workflow.
4. Configure a daily, weekly or monthly recurrence, time, IANA timezone, start date, optional end and review dates. The known default timezone is Africa/Addis_Ababa. Monthly days 1–28 are supported. No browser timers execute checks.
5. Define metrics, comparisons, thresholds, units, baselines, farm/crop scope, consecutive checks, severity and actions. Combine rules with AND or OR. Values are illustrative, not scientifically validated agronomic standards.
6. Select outputs and inspect the complete review summary. **Save monitor draft** persists configuration metadata locally. Edit, duplicate, pause/return to draft, and delete work locally; pause does not affect any server schedule.
7. The saved monitor opens at `#monitoring/{id}`. Overview initially has **No result**, **Not scheduled** and no connected capabilities. **Preview synthetic data** explicitly evaluates this configuration against fixed sample evidence. It never invokes an external tool.
8. Explore **Rainfall warning**, **Crop photo review**, **Missing submission**, or **Partial data** below the templates. These addressable examples live at `#monitoring/demo/{scenario}` and do not add saved monitors. **Save a local copy** opens their configuration for review.
9. In the photo example, open a dated crop illustration, compare it with another week, inspect provenance/limitations, and prepare feedback. Original schematic maize images are explicitly labeled illustrations, not field photographs. The missing F-007 submission is an operational reminder, not evidence of crop-health deterioration.
10. Save/edit the feedback text. Enter a local reviewer name and acknowledge the demo-only meaning before **Record demo approval**. Save-for-later, rejection and inspection-request decisions are also local. Editing the draft creates a new version requiring review again. **Delivery unavailable** remains disabled.
11. Inspect threshold evidence, sample history, filters and the source-aware sample report. **Download sample .md** exports the actual displayed synthetic content as a Markdown artifact.

## State and evidence

`MonitorDefinition` contains only a versioned local configuration and draft/paused status. `MonitorRun`, `ThresholdEvaluation`, evidence, alerts, photo observations, reports and officer review decisions are separate concepts. Runtime results and images are never serialized into monitor configuration storage.

The local key is `agrilo-fieldops:monitoring:v1`. Its strict Zod document holds at most 100 monitor definitions and 200 feedback drafts. UUIDs, dates, IANA zones, references, units, bounded numeric values and capability dependencies are validated on both save and restore. Unknown runtime/authentication/image fields, duplicate IDs and invalid references invalidate restored data rather than restoring authority. Writes are serialized; edit/pause/review operations use expected version checks. Storage failure leaves the wizard/draft open with an error instead of claiming success.

Farmer personal details and contact destinations are not collected. Local farm references contain IDs, display labels, crops and a source tag; actual Home records use a generic farm label. There are no credential fields. Recognizable credential strings in free text are rejected, but this cannot infer all possible secrets; officers should not enter credentials or personal information into prototype notes.

The sample fixtures use three existing synthetic maize farms, dated October–November 2026. Current and previous sample runs show new/resolved conditions and explicit gaps. Satellite observations and diagnostic analysis remain unavailable. The threshold evaluator requires matching metric, unit and reference, sufficient consecutive checks, and available finite evidence. Unknown data stays unknown. AND/OR uses three-state logic; it does not convert unknown results into a safe condition. Example data is never matched to a real Home farm solely because its ID resembles a synthetic one.

Alerts use stable farm/condition deduplication keys. The interface shows one condition card per farm; review marks are local to the current view. Cooldown, cross-run delivery, server acknowledgement and evidence-based resolution remain future work. Scheduled checks and sample-event alerts are labeled separately.

## Photo and feedback handling

Officers may explicitly select a JPEG, PNG or WebP sample up to 8 MB / 24 megapixels. Raster decoding is checked. Its object URL and session notes remain in memory and are released when the Photos view closes or Monitoring is left. No image bytes, filenames, object URLs, image data URLs or photo notes enter localStorage. Session sample evidence references may remain in a saved feedback draft, but the corresponding image is not retained; supply durable authorized evidence before a real review.

No live farmer submissions, crop diagnosis, matched upload service or image-quality assessment is simulated. Photo states and observation types reserve future workflows, while the local UI shows **Not analyzed** or **Analysis unavailable**. Photographic lighting, angle, distance and plant-selection differences may prevent reliable growth comparison. An illustrated concern is an officer-review example, never a confirmed diagnosis.

Feedback decisions always carry `authority: local_demo` and the exact feedback version. They are not authenticated administrative approvals, schedule permissions or delivery authorizations. A newer text version supersedes older reviews. The UI collects no recipient contact, communication credentials, SMS/email account or delivery channel.

## Architecture and future integration

- `src/features/monitoring/types.ts`: configuration Zod schemas and distinct frontend models.
- `catalog.ts`: five templates and eight example capabilities, plus adapters to the existing Farm type.
- `evaluation.ts` and `fixtures.ts`: deterministic three-state evaluation, four opt-in scenarios, sample timelines/history/report content.
- `service.ts`: `MonitoringService` and the local adapter; persistent configuration and feedback operations, no network transport.
- `store.ts`: the existing Zustand architecture, with an independent monitoring slice.
- `backend-contract.ts`: a typed future HTTP adapter boundary. All backend methods currently return `BACKEND_REQUIRED` without making requests. No working endpoint paths were invented.
- `src/components/monitoring/`: secondary navigation, wizard, details, results, photos, history and officer review. The existing accessible management dialog is reused.

The backend boundary reserves authenticated ownership and validated configuration separately from device drafts. It includes approved capability discovery, schedule activation/suspension, recurring execution requests, rule evaluation, history/alerts, photo intake/analysis, reports, review submission and explicit communication handoff. Future approved custom skills and plugin tools need immutable version/digest references and server evidence; local example selection supplies neither.

Real implementation requires authenticated farm membership, provider/skill approvals, secure secret storage, validated recurrence and timezone handling, comparable measurements and baselines, durable photo/evidence storage, diagnostic uncertainty, server audit trails, authorized officer review and explicit recipient/channel approval before communication.

## Navigation, accessibility and limits

Hash routes support browser history and direct monitor links. Home remains mounted after first visit, preserving map geometry/viewport, selected farm, filters, analysis, chat and map-size preference. Existing pending Home work continues. Hidden Home controls remain inert and its map resizes on return. Plugin configurations remain in their existing store/storage. Opening Monitoring directly does not mount the Home map or request map tiles.

The secondary navigation collapses into a focus-managed drawer on tablet/mobile. Wizard steps, errors, form controls and dialogs have semantic labels and visible focus states. Mobile templates are single-column; photo comparisons stack. Reduced-motion preferences are supported. Monitoring code is loaded on demand.

This is a local prototype: no background execution, active schedules, connected data providers, automatic farmer advice, live notifications, authenticated approval, diagnosis, SMS/email/voice delivery or real production reports. Demonstration charts/reports have fixed fixture dates and never refresh themselves.

## Verification

Run `npm run check`, then `npm run test:e2e` using the permitted browser override documented in the README when necessary. Unit tests cover schema/restore validation, threshold comparability and unknown states, deduplication, scoped evidence, persistence/version guards, storage failure, feedback review invalidation and unsupported backend actions. Browser tests cover the complete wizard, rejection of invalid thresholds, editing, reload, duplicate/pause/delete, sample evidence/history/report exports, photo comparison/intake/review, mobile focus/drawers and Home/Plugins regression.
