import { describe, expect, it } from 'vitest'
import { demoSelection, farmsInside, rectangleSelection } from '../src/lib/geo'
import { candidateSchema, evidenceSchema, mapCommandSchema, selectionSchema } from '../src/api/schemas'
import { syntheticFarms } from '../src/demo/synthetic-farms'
import { emptyFilters, filterFarms } from '../src/features/farms/filters'
describe('WGS84 rectangle contract', () => {
  it('normalizes reverse corners and preserves longitude-first precision', () => {
    const s = rectangleSelection({ lat: 8.590000001, lng: 39.33 }, { lat: 8.49, lng: 39.20 })
    expect(s.bbox).toEqual([39.20, 8.49, 39.33, 8.590000001])
    expect(s.geometry.coordinates[0]).toEqual([[39.2, 8.49], [39.33, 8.49], [39.33, 8.590000001], [39.2, 8.590000001], [39.2, 8.49]])
  })
  it.each([[0, 0, 0, 0], [91, 39, 92, 40], [8, 181, 9, 182], [-50, -100, 50, 100]])('rejects zero, invalid or oversized bounds %j', (a, b, c, d) => expect(() => rectangleSelection({ lat: a, lng: b }, { lat: c, lng: d })).toThrow())
  it('rejects an unclosed or mismatched ring', () => { const s = demoSelection(); s.geometry.coordinates[0][4] = [40, 9]; expect(selectionSchema.safeParse(s).success).toBe(false) })
  it('queries fixed farms and includes centroid on boundary', () => {
    expect(farmsInside(syntheticFarms, demoSelection().bbox)).toHaveLength(12)
    expect(farmsInside(syntheticFarms, [0, 0, 1, 1])).toEqual([])
    const f = syntheticFarms[0]; expect(farmsInside(syntheticFarms, [f.point.lon, f.point.lat, f.point.lon + .001, f.point.lat + .001])).toEqual([f])
  })
})
describe('filters and evidence', () => {
  it('supports risk, crop, candidate, drought and search filters', () => {
    expect(filterFarms(syntheticFarms, { ...emptyFilters, risk: 'high' }).map(f => f.id)).toEqual(['F-001', 'F-005', 'F-007'])
    expect(filterFarms(syntheticFarms, { ...emptyFilters, crop: 'maize' })).toHaveLength(4)
    expect(filterFarms(syntheticFarms, { ...emptyFilters, candidateCrop: 'Vegetables' }).map(f => f.id)).toEqual(['F-008', 'F-012'])
    expect(filterFarms(syntheticFarms, { ...emptyFilters, drought: 'unknown', search: 'F-009' })).toHaveLength(1)
  })
  it('validates actual unavailable evidence without calling it no risk', () => {
    const f = syntheticFarms[8]; expect(f.riskLevel).toBe('unknown'); expect(f.candidates).toEqual([])
    expect(evidenceSchema.parse(f.evidence[0]).status).toBe('unavailable')
    expect(evidenceSchema.safeParse({ ...f.evidence[0], sourceType: 'imagined' }).success).toBe(false)
  })
  it('requires explanations and constraints on all differentiated candidates', () => {
    for (const f of syntheticFarms) for (const c of f.candidates) expect(candidateSchema.safeParse(c).success).toBe(true)
    expect(syntheticFarms[0].candidates.map(c => c.crop)).not.toEqual(syntheticFarms[7].candidates.map(c => c.crop))
    expect(candidateSchema.safeParse({ ...syntheticFarms[0].candidates[0], reasons: [] }).success).toBe(false)
  })
  it('rejects unknown commands, extra executable fields and invalid layers', () => {
    expect(mapCommandSchema.safeParse({ type: 'eval', code: '1+1' }).success).toBe(false)
    expect(mapCommandSchema.safeParse({ type: 'clear_filters', script: '1+1' }).success).toBe(false)
    expect(mapCommandSchema.safeParse({ type: 'set_layer_visibility', layerId: 'invented', visible: true }).success).toBe(false)
  })
})
