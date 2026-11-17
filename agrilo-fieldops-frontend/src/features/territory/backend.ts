import { z } from 'zod'
import { homeApi, homeStore } from '../../state/useHome'
import { plotSchema as homePlotSchema } from '../../api/home-contracts'
import { farmerSchema, plotSchema, seasonSchema, territorySchema, crops, type FarmerProfile } from './types'

export const registryRequest = (path: string, options: RequestInit = {}, signal = new AbortController().signal) => homeApi.registryRequest(`/api/v1/registry${path}`, signal, options)
export const write = (body: unknown, method = 'POST'): RequestInit => ({ method, body: JSON.stringify(body) })
const farmerResponse = z.object({ id: z.string(), reference: z.string(), display_name: z.string(), village: z.string(),
  language: z.string(), channel: farmerSchema.shape.channel, consent: farmerSchema.shape.consent, synthetic: z.boolean(), revision: z.number() })
export function parseFarmer(value: unknown): FarmerProfile {
  const f = farmerResponse.parse(value)
  return farmerSchema.parse({ id: f.id, reference: f.reference, displayName: f.display_name, village: f.village, language: f.language,
    channel: f.channel, consent: f.consent, synthetic: f.synthetic, revision: f.revision, origin: 'backend', verification: 'unverified',
    household: '', phone: '', email: '', preferences: '', notes: '', availability: 'unknown' })
}
export const farmerPageSchema = z.object({ items: z.array(z.unknown()), total: z.number(), limit: z.number(), offset: z.number() })
const plotResponse = z.object({ id: z.string(), territoryId: z.string(), name: z.string(), geometry: plotSchema.shape.geometry,
  farmerIds: z.array(z.string()), status: plotSchema.shape.status, origin: z.literal('backend'), createdAt: z.string(), revision: z.number(),
  location: z.string().optional(), notes: z.string().optional(), observation: z.string().optional(),
  home_plot: homePlotSchema, season: z.record(z.string(), z.unknown()).nullable(), farmers: z.array(z.unknown()).optional() })
export function parsePlot(value: unknown) {
  const r = plotResponse.parse(value)
  const plot = plotSchema.parse({ id: r.id, territoryId: r.territoryId, name: r.name, geometry: r.geometry, farmerIds: r.farmerIds,
    status: r.status, origin: r.origin, createdAt: r.createdAt, revision: r.revision, location: r.location ?? '', notes: r.notes ?? '', observation: r.observation ?? '' })
  const c = r.season
  const season = c ? seasonSchema.parse({ id: c.id, plotId: r.id,
    crop: crops.includes(c.crop as typeof crops[number]) ? c.crop : 'Unknown', plantingDate: c.planting_date ?? '',
    stage: ['Land preparation', 'Planted', 'Vegetative', 'Flowering', 'Maturing', 'Harvested'].includes(String(c.stage)) ? c.stage : 'Unknown', irrigation: c.irrigation ?? 'unknown', irrigationMethod: ['Rainfed', 'Drip', 'Sprinkler', 'Surface', 'Other'].includes(String(c.irrigation_method)) ? c.irrigation_method : 'Unknown',
    previousCrop: crops.includes(c.previous_crop as typeof crops[number]) ? c.previous_crop : 'Unknown' }) : null
  return { plot, season, home: r.home_plot, farmers: (r.farmers ?? []).map(parseFarmer) }
}
export async function fetchTerritories(signal?: AbortSignal) {
  const data = z.object({ items: z.array(territorySchema), total: z.number() }).parse(await registryRequest('/territories?limit=100', {}, signal))
  return data
}
export function mergeHomePlots(plots: z.infer<typeof homePlotSchema>[]) {
  const h = homeStore.getState(), known = new Map(h.plots.filter(p => h.selectedIds.includes(p.id)).map(p => [p.id, p]))
  for (const plot of plots) known.set(plot.id, plot)
  const all = [...known.values()]
  if (h.context) homeStore.setState({ context: { ...h.context, plots: all }, plots: all })
  homeStore.getState().setSearch(h.search)
}
