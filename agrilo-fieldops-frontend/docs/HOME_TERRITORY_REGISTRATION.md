# Home territory and farmer registration

Home retains its existing Leaflet map, satellite/street basemaps, temporary analysis selection, officer companion, skills, authorization controls and evidence workflows. The territory feature extends that map rather than creating another application. Existing Monitoring and Outreach behavior is unchanged.

## Local workflow

1. Open **My Territory**. Unsupported territory data is shown as unavailable, not as proof that no territory is assigned. A confirmed empty assignment response has a distinct empty state.
2. Choose **Set Up My Territory**. Enter a name, region and district; draw a rectangle or enter west/south/east/north WGS84 bounds. Preview the area, edit corners, undo, fit the boundary, or cancel. Save a **Local draft**, which grants no record access.
3. Choose **Register Farm Plot**. Draw a smaller rectangle. Escape cancels an unfinished draw; coordinate entry is also available. The whole plot must be inside its territory. Overlaps greater than one square meter are flagged and require an explicit review acknowledgment; legitimate shared records are not categorically rejected.
4. Link an existing local profile, load the 2,000 deterministic synthetic profiles, or register a temporary profile. A farmer can link to several plots. Enter known crop information, review and save the local plot draft. Optional dates and stages remain unknown.
5. Inspect farm details, farmers, crop records and observations. Local plots show their context in the companion with **Live investigation requires a registered, authorized farm.** They never become skill-run targets. Backend-authorized point records continue to use the existing companion API.

The map has distinct territory (green), local plot (blue), selected/unsaved plot (gold), and temporary analysis (purple) geometries. Clearing an analysis area leaves territory and plot records intact. One mode is active at a time; navigation cancels unfinished drawing and removes edit handles while retaining forms, saved boundaries and active investigations. The existing map resize observer preserves Compact/Expanded Map behavior. The live companion can be hidden while inspecting the map, and shown again without remounting it.

## Storage and privacy

`agrilo-fieldops:territory:v1:<office-and-officer-scope>` is a dedicated versioned namespace. Only an explicit allowlist is stored: non-authoritative local boundary geometry, generated client IDs, timestamps, predefined crop selections and dates, and IDs of deterministic synthetic profiles. Entered territory/plot labels use generic labels after reload.

Entered names, farmer references, phone numbers, email addresses, household information, free-form notes, observations, temporary profile IDs, credentials, backend-authorized records and official boundaries are **not** written to localStorage or sessionStorage. Real profiles and free-form labels are memory-only. Links to memory-only profiles cannot be restored after the session ends. An edited synthetic profile is also memory-only; the immutable synthetic fixture is used after reload. Signing out, changing officer, or changing office clears in-memory registration data. Storage errors preserve the current draft in memory and explicitly say that device persistence failed. Invalid restores are rejected without inventing a successful restore.

The safe local storage model intentionally does not provide real farmer persistence. Secure backend contact storage is required before production use with real registries.

## Architecture

- `src/features/territory/geometry.ts`: bounded WGS84 geometries, geodesic area, bounding boxes, containment and overlap using Turf. [Area documentation](https://turfjs.org/docs/api/area), [intersection documentation](https://turfjs.org/docs/api/intersect).
- `types.ts`: separate territory, local plot, farmer, crop-season, interaction-mode and future submission types. A local plot has no backend plot identity; authorized investigation context resolves against the current authenticated `HomeContext.plots` only.
- `services.ts`: `TerritoryService`, `FarmerService`, `FarmPlotService`, `FarmInvestigationService`, independent assignment validation, and the validated local adapter.
- `store.ts`: local registration lifecycle, session scoping, generated draft IDs, safe persistence, unsaved-change guards and geometry previews.
- `runtime.tsx`: authenticated session synchronization and authorized territory scoping; current investigation snapshots are preserved.
- `src/components/map/TerritoryMapLayer.tsx`: persistent shapes and Geoman territory/plot drawing on the existing map. Temporary analysis remains in its original store.
- `src/components/territory/`: nonmodal registration drawer, paginated directory, profiles and farm records. The map remains interactive while drawing; mobile temporarily hides the drawer during map editing.
- `handoffs.ts`: typed, deduplicated local preview references for future Monitoring and Outreach. They are not scheduler, delivery or approval endpoints.

## Existing backend and proposed integration contract

The current `/api/v1/companion/context` supplies authorized plot points and skills. It does not currently supply territory boundaries, a farmer directory, crop-season history, or authorized registration operations. This implementation adds no backend route, migration, spatial service or permission.

An optional **proposed** context extension can later supply assignment metadata. It is validated separately, so absent/invalid territory data cannot break the existing authenticated companion:

```json
{
  "territory_workspace": {
    "status": "available",
    "territories": [{
      "id": "backend-issued-territory-id",
      "name": "Assigned agricultural zone",
      "region": "Office-supplied region",
      "district": "Office-supplied district",
      "description": "",
      "officeId": "authenticated-office-id",
      "origin": "backend",
      "status": "assigned",
      "boundary": { "type": "Polygon", "coordinates": [[[39.2,8.5],[39.3,8.5],[39.3,8.6],[39.2,8.6],[39.2,8.5]]] },
      "createdAt": "2026-01-01T00:00:00Z",
      "authorizedPlotIds": ["existing-backend-plot-id"]
    }]
  }
}
```

`status: available` with an empty array confirms no assignment. `unavailable`, an absent extension, malformed geometry, wrong-office records or references outside `HomeContext.plots` cannot establish assignment. `pending-approval` is read-only pending verification; local storage cannot restore `assigned` or backend-origin records. Multiple assignments have a switcher; switching clears incompatible farm targets and route endpoints, preserves active investigation snapshots, and warns before discarding registration edits.

Future authenticated service operations must provide:

- **Office-owned territories and assignments:** paginated authorized assignment reads, proposal creation, revision/version checks, administrator review and revocation; distinguish permission denial, missing data and temporary outages. The office comes from authentication, never from a client claim. A self-drawn boundary confers no private-record access.
- **Farm plots:** backend-issued immutable identities, office/territory linkage, WGS84 Polygon/MultiPolygon boundaries, server-side PostGIS validity, containment, area and overlap checks, documented conflict resolution and idempotent registration. Client areas are estimates. This frontend phase draws rectangles only; future authorized geometries may be Polygon/MultiPolygon.
- **Farmer registry:** authorized search/pagination, duplicate detection, farmer-to-plot associations with documented roles, secure encrypted contact storage, consent purpose/version, verification provenance and audit records. One farmer can have many plots, and future association tables can support multiple documented roles. No sensitive data should enter a browser persistence cache by default.
- **Crop seasons and observations:** immutable plot references, unknown-value semantics, dated season revisions, observation provenance, controlled photo upload and authorized history reads. Never infer dates, crop stages or historic findings from registration.
- **Skill execution:** preserve the existing authenticated plot-ID run contract, model/provider permissions, synthetic-data restrictions, request recovery, evidence provenance and job lifecycle. Validate ownership and territory scope server-side; never trust local IDs or arbitrary client coordinates as authorization.
- **Monitoring/Outreach:** references to authorized territories, plots, seasons, observations and actual evidence. Dedupe recipients by farmer identity rather than plot identity. Resolve contact eligibility, language, channel, consent and delivery permission on the server. The current preview contracts do not authorize monitoring execution or message sending.
- **Authorization and persistence:** deny cross-office reads/writes, enforce roles and assignment changes on every request, protect private contacts, use server-generated IDs and versions, support pagination and race-safe updates, and return explicit capability/permission states.

No proposed URL is invoked. Prepared submission objects are typed metadata only; submission, approval, secure persistence, official farmer counts and live execution for locally created plots require backend development.

## Verification

Run `npm run check`, `npm run test:layout`, and the existing demo browser suite (`VITE_API_MODE=mock npm run test:e2e`). The layout suite uses intercepted HTTP fixtures on port 5177; it does not use real officer credentials or call agricultural providers. Territory tests cover drawing/editing, coordinates, assigned metadata, persistence, linked plots, privacy, session reset, navigation and mobile pagination. Unit tests cover geometry, containment/holes, overlaps, invalid storage, duplicate references and local-ID investigation rejection.

Implementation verification: TypeScript, lint, production build and 122 unit/component tests passed. All 29 existing demo browser workflows and 11 HTTP-fixture territory/layout scenarios passed, including actual Geoman corner editing and tablet companion collapse. The demo regression run used a separate port to preserve the running integrated frontend. Real FastAPI/LangGraph/provider fixture suites were not run; authenticated territory persistence, farmer registry writes and approval endpoints do not exist in this phase.
