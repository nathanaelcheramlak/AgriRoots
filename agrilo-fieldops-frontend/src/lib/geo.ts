import { selectionSchema } from '../api/schemas'
import type { Farm, Selection } from '../api/types'
export function rectangleSelection(a: { lat: number; lng: number }, b: { lat: number; lng: number }, trigger: Selection['client_context']['trigger'] = 'map_rectangle_selected'): Selection {
  const [w, s, e, n] = [Math.min(a.lng, b.lng), Math.min(a.lat, b.lat), Math.max(a.lng, b.lng), Math.max(a.lat, b.lat)]
  return selectionSchema.parse({ selection_id: `sel-${crypto.randomUUID()}`, selection_type: 'rectangle', bbox: [w, s, e, n], geometry: { type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] }, client_context: { trigger } })
}
export function farmsInside(farms: Farm[], bbox: Selection['bbox']): Farm[] {
  const [w, s, e, n] = bbox
  return farms.filter(({ point }) => point.lon >= w && point.lon <= e && point.lat >= s && point.lat <= n)
}
export function areaKm2([w, s, e, n]: Selection['bbox']): number { return (e - w) * (n - s) * 111.32 ** 2 * Math.cos((s + n) / 2 * Math.PI / 180) }
export function bboxKey(selection: Selection): string { return selection.bbox.join(',') }
export function demoSelection(): Selection { return rectangleSelection({ lat: 8.502, lng: 39.218 }, { lat: 8.59, lng: 39.328 }, 'demo_area') }
export function leafletBounds(s: Selection): [[number, number], [number, number]] { return [[s.bbox[1], s.bbox[0]], [s.bbox[3], s.bbox[2]]] }
