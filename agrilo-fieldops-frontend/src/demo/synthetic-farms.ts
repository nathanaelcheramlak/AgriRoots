import { farmSchema } from '../api/schemas'
import type { CropCandidate, EvidenceRecord, Farm, ProviderStatus } from '../api/types'
export const FIXTURE_DATE = '2026-07-21T06:00:00.000Z'
export const providers: ProviderStatus[] = [
  { id: 'weather', name: 'Weather & rainfall', status: 'available', detail: 'Fixed synthetic 14–20 Jul 2026 record; no live provider.' },
  { id: 'soil', name: 'Soil context', status: 'partial', detail: 'Illustrative profiles; F-009 has no soil measurements.' },
  { id: 'satellite', name: 'Satellite / NDVI', status: 'unavailable', detail: 'Integration not connected. No imagery or vegetation inference.' },
  { id: 'pests', name: 'Pest alerts', status: 'unavailable', detail: 'No regional alert feed connected; no field diagnosis.' },
]
function evidence(id: string, variable: string, value?: number | string, unit?: string, scope: EvidenceRecord['spatialScope'] = 'farm'): EvidenceRecord {
  return { id, variable, value, unit, provider: 'AgriLo synthetic fixture', observedAt: FIXTURE_DATE, retrievedAt: FIXTURE_DATE, spatialScope: scope, sourceType: 'synthetic', status: value === undefined ? 'unavailable' : 'available', details: 'Fixed illustrative demo evidence. Not a measurement, forecast, or validated agronomic rule.' }
}
export const areaEvidence = [evidence('AREA-WEATHER', 'Temperature range · 14–20 Jul 2026', '19–28', '°C', 'area')]
const records: [number, number, string, Farm['riskLevel'], Farm['irrigationAccess'], string, number | undefined, number | undefined][] = [
  [8.574, 39.239, 'Maize', 'high', 'none', 'Sandy loam', 6.3, 12],
  [8.566, 39.269, 'Teff', 'low', 'limited', 'Clay loam', 6.8, 31],
  [8.58, 39.302, 'Wheat', 'moderate', 'limited', 'Loam', 6.5, 25],
  [8.551, 39.226, 'Sorghum', 'low', 'none', 'Sandy loam', 6.4, 20],
  [8.546, 39.253, 'Maize', 'high', 'limited', 'Sandy loam', 6.1, 14],
  [8.553, 39.315, 'Teff', 'moderate', 'none', 'Clay', 7.2, 27],
  [8.532, 39.284, 'Maize', 'high', 'none', 'Sandy loam', 6.2, 11],
  [8.526, 39.238, 'Vegetables', 'low', 'reliable', 'Loam', 6.7, 29],
  [8.511, 39.267, 'Wheat', 'unknown', 'unknown', 'Unavailable', undefined, undefined],
  [8.517, 39.304, 'Sorghum', 'moderate', 'limited', 'Loam', 6.9, 22],
  [8.541, 39.305, 'Teff', 'low', 'limited', 'Clay loam', 6.6, 30],
  [8.562, 39.288, 'Maize', 'moderate', 'reliable', 'Loam', 6.4, 26],
]
export const syntheticFarms: Farm[] = records.map(([lat, lon, crop, risk, irrigation, texture, ph, rain], i) => {
  const id = `F-${String(i + 1).padStart(3, '0')}`
  const soilId = `${id}-SOIL`, rainId = `${id}-RAIN`, waterId = `${id}-WATER`
  const makeCandidate = (name: string, reason: string, constraint: string, status: CropCandidate['status'] = 'candidate'): CropCandidate => ({ crop: name, status, reasons: [reason], constraints: [constraint, 'Illustrative candidate only; extension-officer agronomic review required.'], evidenceIds: [soilId, rainId, waterId] })
  const candidates: CropCandidate[] = risk === 'unknown' ? [] : irrigation === 'reliable'
    ? [makeCandidate('Vegetables', 'Fixture records reliable irrigation and a loam profile.', 'Confirm water quality, local market, and seasonal suitability.', 'conditional'), makeCandidate('Maize', 'Fixture shows irrigation access and a loam profile.', 'Verify planting window and seed suitability.', 'conditional')]
    : risk === 'high' ? [makeCandidate('Sorghum', 'The demo water-limited, sandy-loam profile is flagged for sorghum review.', 'Check cultivar, season length, and field water availability.'), makeCandidate('Teff', 'A second option for local assessment of this fixture profile.', 'Confirm establishment moisture; suitability is not validated.', 'conditional')]
      : [makeCandidate(crop === 'Teff' ? 'Teff' : 'Sorghum', `The ${texture.toLowerCase()} fixture and ${irrigation} irrigation are inputs for local review.`, 'Verify drainage, planting window, and local cultivar.'), makeCandidate('Chickpea', 'An illustrative rotation option for officer comparison.', 'Check residual moisture and local rotation constraints.', 'conditional')]
  return farmSchema.parse({ id, displayName: `Demo Farm ${id}`, point: { lat, lon }, areaHectares: [1.8, 2.4, 3.1, 1.5, 2.8, 1.2, 2.1, 0.9, 3.4, 2.6, 1.7, 2.3][i], currentCrop: crop, plantingDate: '2026-06-18', irrigationAccess: irrigation, riskLevel: risk, droughtRisk: risk, dataQuality: risk === 'unknown' ? 'unknown' : 'estimated',
    riskReasons: risk === 'high' ? ['Low rainfall amount in the synthetic weekly record.', `${irrigation === 'none' ? 'No' : 'Limited'} irrigation access in the fixture.`, 'Sandy-loam profile flagged for a field moisture check.'] : risk === 'unknown' ? ['Soil and rainfall evidence are missing. Risk cannot be assessed.'] : risk === 'moderate' ? ['Seasonal water access needs verification in this demo profile.', 'Schedule a field check before selecting a crop.'] : ['No high-priority issue in the synthetic profile.', 'Low priority does not establish that the farm is safe.'],
    soil: { texture, ph, organicCarbon: ph === undefined ? undefined : 1.2, evidenceId: soilId }, rainfall: { amount: rain, unit: 'mm', period: '14–20 Jul 2026', evidenceId: rainId }, candidates,
    evidence: [evidence(soilId, 'Soil pH / texture', ph === undefined ? undefined : `${ph} · ${texture}`), evidence(rainId, 'Rainfall · 14–20 Jul 2026', rain, 'mm'), evidence(waterId, 'Irrigation access', irrigation)],
    observations: [{ id: `${id}-OBS`, recordedAt: FIXTURE_DATE, note: 'Synthetic registration for interface testing. No real household or field visit.', sourceType: 'synthetic' }],
  })
})
