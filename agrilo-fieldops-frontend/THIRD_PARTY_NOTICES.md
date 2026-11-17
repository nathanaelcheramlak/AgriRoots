# AgroSphere frontend attribution

This independent AgriLo FieldOps test frontend reuses and adapts the frontend of [Leoul39/AgroSphere](https://github.com/Leoul39/AgroSphere), commit `77070f0615f8b529633f8c2c96ade1378ded057a`.

Copyright (c) 2025 Leoul39. Licensed under the MIT license; the full required notice is preserved in [licenses/AgroSphere-MIT.txt](licenses/AgroSphere-MIT.txt).

Reused source materials:

- `frontend/src/App.module.css` → `src/app/App.module.css`: original fixed sidebar, brand, map card, coordinate widget and scrollable main-area styles.
- `frontend/src/index.css` → `src/styles/agrosphere-base.css`: dark palette, base styles and zoom-dependent map labels.
- `frontend/src/components/Dashboard/IntelligencePanel.module.css` → `src/components/intelligence/IntelligencePanel.module.css`: original report, environment cards, candidate cards, skeletons, status badges and empty-state styles.
- `frontend/src/components/Map/MapExplorer.module.css` → `src/reference/agrosphere/MapExplorer.module.css`: original Leaflet container style.
- `frontend/public/agrosphere-logo-transparent.svg` → `public/fieldops-mark.svg`: original visual mark; visible text branding is AgriLo FieldOps.
- `frontend/src/components/Map/MapExplorer.tsx`: satellite tile configuration, Leaflet marker asset configuration, click-coordinate capture, fly-to interaction, six-tier zoom labels, regional/country boundaries, city points and label suppression adapted in `src/components/map/`.
- Upstream `africa.json`, `ethiopia-regions.json`, and `ethiopia-cities.json` copied to `src/components/map/boundaries/` as reference context. The source identifies regional data as geoBoundaries; these layers are illustrative reference boundaries, not authoritative surveyed farm boundaries. Review original dataset provenance/licensing before production redistribution.

Application logic has been adapted to area screening, fixed synthetic registered farms, differentiated illustrative crop candidates, deterministic assistant commands and local officer review. The upstream point-analysis backend, unvalidated suitability percentages, and soil-prescribing outputs are not used.

The satellite layer follows the public Google tile URL used by the reference frontend, upgraded from HTTP to HTTPS and with Google attribution retained. It is **not** a configured Google Maps Platform API integration and has no asserted support, quota, production permission or availability guarantee. Before deployment, configure an appropriately licensed imagery provider through `VITE_SATELLITE_TILE_URL` / `VITE_SATELLITE_ATTRIBUTION`. The Street basemap uses attributed OpenStreetMap tiles under its provider policy. Code permission under MIT does not grant rights to imagery from those services.

Leaflet, React Leaflet, Leaflet-Geoman, React, Zustand, TanStack Query, Lucide, Zod and development tooling retain their respective upstream licenses in the installed packages.
