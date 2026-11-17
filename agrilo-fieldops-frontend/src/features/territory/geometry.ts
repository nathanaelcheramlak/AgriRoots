import { area } from '@turf/area'
import { bbox } from '@turf/bbox'
import { intersect } from '@turf/intersect'
import { feature, featureCollection } from '@turf/helpers'
import { kinks } from '@turf/kinks'
import type { Polygon, MultiPolygon } from 'geojson'
import { z } from 'zod'

export const LIMITS = { territoryKm2: 10000, plotHectares: 1000, minimumM2: 1 }
const position = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)])
const ring = z.array(position).min(4).max(2000).refine(r => r[0][0] === r.at(-1)![0] && r[0][1] === r.at(-1)![1], 'Close each boundary ring.')
export const polygonSchema: z.ZodType<Polygon> = z.object({ type: z.literal('Polygon'), coordinates: z.array(ring).min(1).max(50) }).strict()
export const boundarySchema: z.ZodType<Polygon | MultiPolygon> = z.union([polygonSchema, z.object({ type: z.literal('MultiPolygon'), coordinates: z.array(z.array(ring).min(1).max(50)).min(1).max(50) }).strict()]).superRefine((g, ctx) => {
  try {
    const box = bbox(g)
    if (box[2] - box[0] > 180 || area(g) < LIMITS.minimumM2 || kinks(g).features.length) ctx.addIssue({ code: 'custom', message: 'Use a nondegenerate WGS84 boundary without self-intersections or an antimeridian crossing.' })
  } catch { ctx.addIssue({ code: 'custom', message: 'Invalid geographic boundary.' }) }
})
export function rectangle(w: number, s: number, e: number, n: number): Polygon {
  if (![w, s, e, n].every(Number.isFinite) || w >= e || s >= n) throw new Error('Minimum coordinates must be smaller than maximum coordinates.')
  return boundarySchema.parse({ type: 'Polygon', coordinates: [[[w, s], [e, s], [e, n], [w, n], [w, s]]] }) as Polygon
}
export function measuredArea(g: Polygon | MultiPolygon) { return area(g) }
export function bounds(g: Polygon | MultiPolygon) { return bbox(g) as [number, number, number, number] }
export function center(g: Polygon | MultiPolygon) { const [w, s, e, n] = bounds(g); return { lat: (s + n) / 2, lng: (w + e) / 2 } }
export function validateBoundary(g: Polygon | MultiPolygon, kind: 'territory' | 'plot') {
  boundarySchema.parse(g)
  const maximum = kind === 'territory' ? LIMITS.territoryKm2 * 1e6 : LIMITS.plotHectares * 1e4
  if (area(g) > maximum) throw new Error(kind === 'territory' ? 'Territories must be at most 10,000 km².' : 'Farm plots must be at most 1,000 hectares.')
}
export function sharedArea(a: Polygon | MultiPolygon, b: Polygon | MultiPolygon) {
  const overlap = intersect(featureCollection([feature(a), feature(b)]))
  return overlap ? area(overlap) : 0
}
export function contained(plot: Polygon | MultiPolygon, territory: Polygon | MultiPolygon) {
  // An area comparison also handles MultiPolygons and holes, including shared edges.
  return area(plot) - sharedArea(plot, territory) <= .01
}
