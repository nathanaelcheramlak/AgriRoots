import type { CropSeason, FarmerProfile, FarmPlot, MonitoringFarmContext, OutreachFarmContext } from './types'

function scopedPlots(territoryId: string, ids: string[], plots: FarmPlot[]) {
  const selected = [...new Set(ids)].map(id => plots.find(p => p.id === id && p.territoryId === territoryId))
  if (!selected.length || selected.some(p => !p)) throw new Error('Choose existing local plots from one territory.')
  return selected as FarmPlot[]
}
// These references are preparation contracts, not a scheduler or sending API.
export function prepareMonitoringContext(territoryId: string, ids: string[], plots: FarmPlot[], seasons: CropSeason[]): MonitoringFarmContext {
  const selected = scopedPlots(territoryId, ids, plots)
  return { territoryId, plotIds: selected.map(p => p.id), seasons: seasons.filter(c => selected.some(p => p.id === c.plotId)), observations: selected.filter(p => p.observation).map(p => ({ plotId: p.id, text: p.observation })), authority: 'local-preview' }
}
export function prepareOutreachContext(territoryId: string, ids: string[], plots: FarmPlot[], farmers: FarmerProfile[], evidenceIds: string[] = []): OutreachFarmContext {
  const selected = scopedPlots(territoryId, ids, plots), farmerIds = [...new Set(selected.flatMap(p => p.farmerIds))]
  if (farmerIds.some(id => !farmers.some(f => f.id === id))) throw new Error('A temporary farmer association is unavailable in this session.')
  return { territoryId, plotIds: selected.map(p => p.id), farmerIds, preferences: farmers.filter(f => farmerIds.includes(f.id)).map(({ id, language, channel, consent }) => ({ id, language, channel, consent })), evidenceIds: [...new Set(evidenceIds)], authority: 'local-preview' }
}
