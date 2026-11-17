# Map-first Home

The pre-redesign checkpoint is commit `2c8986a`. This change replaces the registry-enabled Home's two-column workspace with a three-step, map-first screen. Sign-in, older-backend compatibility, local demo, Plugins and Skills retain their existing services.

## Officer workflow

1. Home starts with a large satellite overview. **Draw area** creates a blue outer rectangle. A saved assigned area can also be selected without redrawing it.
2. A separate Leaflet map appears below, showing only the selected area. The outside is masked, navigation/zoom are constrained, and **Draw farm plot** operates exclusively on this cropped map. Drawing outside the crop is rejected.
3. After the plot is drawn, the form asks only **Farmer name**, **Farmer ID**, and **Phone number**. The server creates the profile and plot together; no crop, household, account, consent or contact verification is invented. Matching existing farmer details can link another plot.
4. The saved farm is selected. **AI Chat** opens the existing investigation interface on demand, with an analysis dropdown and a farming idea/question. A single explicit checkbox authorizes provider and configured-model requests; credit-consuming diagnosis still requires its separate permission. Closing chat does not cancel a running job or remove results.

The outer rectangle is a temporary work area when covered by an assigned territory. An area outside assignments can be submitted as a proposal; it never grants access automatically. Office administrators may explicitly approve it; officers still require office approval and assignment. The existing authorization resolver remains authoritative.

## Backend contract

`POST /api/v1/registry/territories/{id}/farm-registrations`

```json
{
  "selection_boundary": {"type": "Polygon", "coordinates": []},
  "geometry": {"type": "Polygon", "coordinates": []},
  "farmer_name": "Test Farmer",
  "farmer_reference": "DEMO-001",
  "phone": "+251900000000",
  "request_key": "client-generated-unique-request-key"
}
```

The geometry examples above are placeholders; real requests require valid closed WGS84 rings. The full plot must fit both the selected crop and the assigned territory. Existing server limits, overlap/duplicate checks and role restrictions apply. The endpoint accepts no office override, synthetic flag, credentials or executable configuration.

The existing `save_farmer` and `save_plot` services support deferred commit for this operation. One transaction saves farmer/plot/association/audit data, and rolls back all changes on failure. Matching farmer references are reused only when territory, name and telephone agree; existing details are never silently overwritten. Telephone is encrypted by the existing secret service and omitted from the response. `request_key` replays return the same farm and conflicting reuses return HTTP 409. Ambiguous frontend saves retry the same request instead of generating another record.

AI submission still uses `/api/v1/skills/{id}/runs`, existing durable polling/cancellation and `/api/v1/evidence/{id}`. Real private farm contexts remain blocked from Gemini by `synthetic_only`. Synthetic farm context and live/fixture provider evidence remain distinct. Registration and map interaction dispatch no environmental-provider/model calls.

## Verification

- Frontend: 127 existing unit/component tests passed, type checking and linting passed.
- Backend: 14 tests passed, one native-only test skipped in the SQLite run, including new atomic save, rollback, crop containment, idempotency, matching-farmer reuse, invalid phone and revoked-assignment checks.
- Actual PostGIS browser workflow: desktop and mobile tests both passed. Desktop draws both maps with actual pointer events, verifies overview clicks cannot create farms, saves exactly three fields, checks no personal data enters localStorage, reloads/signs in, and completes existing LangGraph/evidence/chart rendering.
- The isolated browser run uses explicitly artificial records, fixture tiles, fixture agricultural responses and a fixture model. Only an authenticated test administrator marks the artificial farm synthetic. Passing these tests is not a claim of a new live Gemini or agricultural-provider run.
- Mobile screenshot was inspected for cropped imagery, three-field layout and horizontal overflow. Desktop evidence screenshot was inspected for the on-demand chat and preserved map.

Implementation: `MapFirstHome.tsx`, `AreaCanvas.tsx`, `home-map-first.css`, compact controls in `InvestigationControls.tsx`, and the existing registry service/routes. `LegacyHomeWorkspace.tsx` preserves sign-in and compatibility with backends without the registry capability marker.

Remaining boundaries: overview selection is a temporary crop and is not persisted as a new authoritative assignment; saved assigned boundaries and farms do persist. The map loads at most 100 boundaries per query. Arbitrary polygon drawing is not added; the existing rectangle interaction is used. Monitoring/Outreach delivery are unchanged. The current model privacy policy can prevent AI execution for real farms even though registration succeeds.
