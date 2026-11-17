// Satellite configuration follows AgroSphere's Leaflet MapExplorer.
// This is the upstream public Google tile endpoint, not a configured Maps Platform API.
export const basemaps = {
  satellite: { label: 'Satellite', url: import.meta.env.VITE_SATELLITE_TILE_URL || 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attribution: import.meta.env.VITE_SATELLITE_ATTRIBUTION || '&copy; <a href="https://www.google.com/maps">Google Maps</a>', maxZoom: 20 },
  street: { label: 'Street', url: import.meta.env.VITE_TILE_URL || 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', attribution: import.meta.env.VITE_TILE_ATTRIBUTION || '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors', maxZoom: 19 },
}
export type Basemap = keyof typeof basemaps
