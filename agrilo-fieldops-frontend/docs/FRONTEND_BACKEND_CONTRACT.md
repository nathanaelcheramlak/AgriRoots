# Frontend/backend boundary (proposed, not deployed)

**Historical demo proposal.** Live Home uses the implemented [Phase 1 contract](PHASE1_HOME_INTEGRATION.md) and [exported backend OpenAPI subset](contracts/home.openapi.json). The proposed area/assistant endpoints below are not called by live Home. Other pages remain local demos/drafts.

This frontend is isolated from AgriRoots and the `f-test` provider evaluation. The default `MockFieldOpsApi` uses deterministic local fixtures. `HttpFieldOpsApi` requires an explicit `VITE_API_MODE=http` and `VITE_API_BASE_URL` for a future separate service. It never silently falls back to mock data on a server error.

`src/api/schemas.ts` is the authoritative runtime contract; `types.ts` derives strict types from it. The map and sidebar consume `FieldOpsApi`, not raw `fetch`. All HTTP/assistant responses are validated. No provider keys belong in the browser.

## Area selection

`POST {base}/api/v1/areas/analyze` uses WGS84 / EPSG:4326. Bbox is **[west, south, east, north]**. Polygon vertices are **[longitude, latitude]**. Leaflet center/corners are **[latitude, longitude]**. The request retains full floating-point precision; displayed coordinates are rounded separately.

```json
{
  "selection_id": "sel-client-uuid",
  "selection_type": "rectangle",
  "bbox": [39.218, 8.502, 39.328, 8.59],
  "geometry": { "type": "Polygon", "coordinates": [[[39.218,8.502],[39.328,8.502],[39.328,8.59],[39.218,8.59],[39.218,8.502]]] },
  "client_context": { "trigger": "map_rectangle_selected" }
}
```

The app constructs these values from the actual Leaflet rectangle. The preselected **Try demo area** rectangle is intentionally fixed. Edits use `map_rectangle_edited`; demo selection uses `demo_area`; the manual coordinate + width workflow uses `manual_area`. That workflow converts the requested square width in kilometres to a displayed WGS84 rectangle and sends its full bbox and polygon. Rings must exactly describe the bbox and close. Bounds must be within valid geographic limits, have positive area, and meet the 2,500 km² / 2° guard. Demo point centroids on the boundary are included. Do not replace the rectangle with a point query.

## Analysis response

A direct response has this shape (illustrative empty selection; full farm shape is in `farmSchema`):

```json
{
  "id": "analysis-001",
  "selection_id": "sel-client-uuid",
  "mode": "http",
  "status": "partial",
  "checkedAt": "2026-11-16T06:00:00Z",
  "farms": [],
  "providers": [{ "id": "satellite", "name": "Satellite / NDVI", "status": "unavailable", "detail": "No licensed imagery integration configured." }],
  "evidence": []
}
```

Modes are `mock` and `http`; the response must match the selected adapter. Status is `completed` or `partial`. Farm count is bounded to 100 in this frontend; a future pagination contract must be coordinated before raising it. Farm and candidate data must come from validated services or explicit synthetic fixtures. No farms means no candidates.

Each farm has ID/displayName/point/areaHectares/currentCrop/plantingDate/irrigationAccess, riskLevel/droughtRisk/riskReasons/dataQuality, soil/rainfall, candidates, evidence and observations. `CropCandidate` requires crop, status (`candidate | conditional | not_recommended`), nonempty reasons/constraints/evidenceIds. Missing evidence is represented by absent value and an explicit status, not zero or a low risk conclusion.

Evidence record example:

```json
{
  "id": "F-007-RAIN",
  "provider": "AgriLo synthetic fixture",
  "variable": "Rainfall · 14–20 Jul 2026",
  "value": 11,
  "unit": "mm",
  "observedAt": "2026-07-21T06:00:00Z",
  "retrievedAt": "2026-07-21T06:00:00Z",
  "spatialScope": "farm",
  "sourceType": "synthetic",
  "status": "available",
  "details": "Fixed illustrative demo record; not measured current rainfall."
}
```

Source types: forecast/historical/estimated/reported/synthetic. Availability: available/unavailable/stale/partial. Evidence retains its observation/retrieval dates when analysis is rerun or cached. In default fixtures, soil coverage is partial and satellite/pests unavailable, so the result accurately reports `partial`.

## Optional background job

The initial POST may instead return:

```json
{ "job_id": "job-001", "status": "queued", "stage": "loading_farms", "updatedAt": "2026-11-16T06:00:00Z" }
```

`GET /api/v1/analysis/{job_id}` returns the same job envelope, with `running`, `completed`, `partial`, or `failed`. Completed/partial jobs must contain `result` with the analysis response. Failed jobs may include `error`. The HTTP adapter polls at 1 second with a 60-poll bound, honoring cancellation. Progress stages are loading_farms/screening/preparing_candidates.

Each finished draw runs immediately; completed corner drags debounce 350 ms. React Query caches by exact canonical bbox for 60 seconds. New/edit/clear selections cancel the old query and assistant request; a generation guard discards late results even if an adapter ignores abort. Results/details/chat are cleared before new screening. Retry preserves geometry and removes the failed/cached query. Pan/zoom never triggers analysis.

## Assistant

`POST /api/v1/assistant/query` body: `{ "text": "Show high-risk farms", "context": { "selection": ..., "farms": [...], "selectedFarmId": null, "providers": [...] } }`.

Response:

```json
{
  "text": "Showing the three high-priority farms in this selected area.",
  "commands": [
    { "type": "filter_farms", "risk": "high" },
    { "type": "zoom_to_farms", "farmIds": ["F-001", "F-005", "F-007"] }
  ]
}
```

Allowed commands are defined by strict `mapCommandSchema`: filter_farms, select_farm, zoom_to_farms, set_layer_visibility, clear_filters, fit_to_selection. Unknown types, extra fields, invalid risk values and unrecognized layer IDs are rejected. Selecting/zooming can use only farms in the current area. Geographic layer commands for soil/rainfall/satellite/pests are rejected until data exists. Text is rendered as plain React text; there is no eval, script or HTML execution.

In mock mode `parseAssistant` recognizes only documented deterministic intents. Unrecognized prompts receive an honest command list. All context/history is cleared on new/edited/deleted selection. Context badges indicate area and selected farm.

## Advisory and other future routes

| Proposed route | Frontend status |
| --- | --- |
| GET `/api/v1/areas/{areaId}/farms` | Future pagination; current analysis embeds ≤100 farms |
| GET `/api/v1/farms/{farmId}` | Future lazy loading; current detail consumes embedded farm/evidence |
| GET `/api/v1/layers` | Future geographic layer discovery; absent overlays labeled unavailable |
| POST `/api/v1/advisories/drafts` | Not called; local mock-mode storage only |
| POST `/api/v1/advisories/{id}/review` | Not called; named demo review and audit only |

Local draft states: draft → pending_review → approved/rejected. Reviewer name is required; identity is not authenticated. Every transition records reviewer/time; no messages or orders are sent. Persisted draft objects include full evidence snapshots and limitations so reviews still make sense after the map selection changes. HTTP mode disables draft creation until a real review adapter/authentication is designed.

## Failure behavior

Non-2xx HTTP responses show `FieldOps backend returned HTTP <status>`; invalid data produces a validation error; failed or timed-out jobs show an actionable message. The active rectangle remains available for retry. No automatic consequential POST retry is performed. Provider gaps are partial results, never fabricated weather/imagery or unsupported diagnoses. Tiles fail independently of agricultural screening and display a map notice.

The mock scenarios use the same contract: `success` returns fixed data with honest partial coverage, `partial` simulates missing rainfall and withholds all candidate/risk conclusions, and `error` fails with the rectangle preserved. These are development fixtures, not live controls.
