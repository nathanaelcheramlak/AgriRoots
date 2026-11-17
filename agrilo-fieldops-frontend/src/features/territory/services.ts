import { z } from 'zod'
import type { HomeContext } from '../../api/home-contracts'
import type { AssignmentState, FarmerProfile, FarmPlot, Territory, TerritorySubmission, FarmerRegistration, PlotRegistration, SelectedFarmContext } from './types'
import { territorySchema, seasonSchema } from './types'
import { boundarySchema, polygonSchema, contained, sharedArea, validateBoundary } from './geometry'
import { demoFarmers, demoTerritory } from './fixtures'

export interface TerritoryService {
  getAssigned(context: HomeContext | null): AssignmentState
  prepareSubmission(territory: Territory): TerritorySubmission
}
export interface FarmerService {
  search(profiles: FarmerProfile[], query: string): FarmerProfile[]
  prepareRegistration(profile: FarmerProfile): FarmerRegistration
}
export interface FarmPlotService {
  validate(plot: FarmPlot['geometry'], territory: Territory, existing: FarmPlot[], excludeId?: string): string[]
  prepareRegistration(plot: FarmPlot, season: z.infer<typeof seasonSchema>): PlotRegistration
}
export interface FarmInvestigationService {
  resolve(id: string, context: HomeContext | null): SelectedFarmContext | null
}
const assignmentEnvelope = z.object({ status: z.enum(['available', 'unavailable']), territories: z.array(territorySchema).max(100), message: z.string().max(600).optional() }).strict()
export const territoryService: TerritoryService = {
  getAssigned(context) {
    if (!context) return { status: 'connection-unavailable', message: 'Sign in to check authorized territory information.' }
    if (context.territory_workspace === undefined) return { status: 'unsupported', message: 'The current backend provides farm points, but territory assignments are not available yet. A local proposal does not grant access.' }
    const parsed = assignmentEnvelope.safeParse(context.territory_workspace)
    if (!parsed.success || parsed.data.status === 'unavailable') return { status: 'unavailable', message: 'Territory data is temporarily unavailable. Your assignment status is unknown.' }
    if (parsed.data.territories.some(t => t.origin !== 'backend' || t.officeId !== context.office_id || t.authorizedPlotIds?.some(id => !context.plots.some(p => p.id === id)))) return { status: 'unavailable', message: 'The supplied territory assignments could not be validated for this office.' }
    return { status: 'available', territories: parsed.data.territories }
  },
  prepareSubmission(t) { return { kind: 'proposal', boundary: t.boundary, name: t.name, region: t.region, district: t.district, expectedOfficeId: t.officeId } },
}
export const farmerService: FarmerService = {
  search(profiles, query) { const q = query.toLowerCase(); return profiles.filter(p => `${p.displayName} ${p.reference} ${p.village}`.toLowerCase().includes(q)) },
  prepareRegistration(profile) { return { kind: 'farmer-registration', profile, consentRecorded: profile.consent === 'granted' } },
}
export const farmPlotService: FarmPlotService = {
  validate(geometry, territory, existing, excludeId) {
    validateBoundary(geometry, 'plot')
    if (territory.status === 'inactive' || territory.status === 'pending-approval') throw new Error('Use an available assigned boundary or a clearly labeled local proposal.')
    if (!contained(geometry, territory.boundary)) throw new Error('This plot crosses the territory boundary. Draw the whole plot inside the boundary.')
    return existing.filter(p => p.id !== excludeId && p.territoryId === territory.id && sharedArea(geometry, p.geometry) > 1).map(p => p.id)
  },
  prepareRegistration(plot, season) { return { kind: 'plot-registration', territoryId: plot.territoryId, geometry: plot.geometry, farmerIds: plot.farmerIds, season } },
}
export const farmInvestigationService: FarmInvestigationService = {
  resolve(id, context) { const plot = context?.plots.find(p => p.id === id); return plot && !id.startsWith('local-plot-') ? { origin: 'backend', authorized: true, plot } : null },
}

export const STORAGE_PREFIX = 'agrilo-fieldops:territory:v1:'
// Persist an allowlist, never form objects. No entered names, contact details,
// notes, office records, credentials, or memory-only farmer references enter storage.
const localTerritory = z.object({ id: z.string().regex(/^(local-territory-|synthetic-territory-)[\w-]+$/), boundary: boundarySchema, createdAt: z.iso.datetime(), origin: z.enum(['local', 'synthetic']) }).strict()
const localPlot = z.object({ id: z.string().startsWith('local-plot-'), territoryId: z.string(), geometry: polygonSchema, farmerIds: z.array(z.string().regex(/^DEMO-FARMER-\d{4}$/)).max(10), createdAt: z.iso.datetime(), origin: z.enum(['local', 'synthetic']) }).strict()
const storedSchema = z.object({ version: z.literal(1), territories: z.array(localTerritory).max(30), plots: z.array(localPlot).max(1000), seasons: z.array(seasonSchema).max(1000), currentId: z.string().nullable(), demo: z.boolean() }).strict()
export function storageKey(owner: string) { return STORAGE_PREFIX + encodeURIComponent(owner) }
export function saveLocalWorkspace(owner: string, territories: Territory[], plots: FarmPlot[], seasons: z.infer<typeof seasonSchema>[], currentId: string | null, demo: boolean) {
  const local = territories.filter(t => t.origin !== 'backend')
  const keepPlots = plots.filter(p => local.some(t => t.id === p.territoryId))
  const document = storedSchema.parse({ version: 1,
    territories: local.map(t => ({ id: t.id, boundary: t.boundary, createdAt: t.createdAt, origin: t.origin })),
    plots: keepPlots.map(p => ({ id: p.id, territoryId: p.territoryId, geometry: p.geometry, farmerIds: p.farmerIds.filter(id => demoFarmers.some(f => f.id === id)), createdAt: p.createdAt, origin: p.origin })),
    seasons: seasons.filter(s => keepPlots.some(p => p.id === s.plotId)), currentId: local.some(t => t.id === currentId) ? currentId : null, demo,
  })
  localStorage.setItem(storageKey(owner), JSON.stringify(document))
}
export function restoreLocalWorkspace(owner: string) {
  const raw = localStorage.getItem(storageKey(owner))
  if (!raw) return null
  if (raw.length > 2e6) throw new Error('Saved workspace exceeds this device’s restore limit.')
  const data = storedSchema.parse(JSON.parse(raw))
  const territories: Territory[] = data.territories.map((t, i) => {
    validateBoundary(t.boundary, 'territory')
    return { ...t, status: 'local-draft', name: t.id === demoTerritory.id ? demoTerritory.name : `Local territory ${i + 1}`, region: '', district: '', description: '' }
  })
  const plots: FarmPlot[] = data.plots.map((p, i) => {
    const territory = territories.find(t => t.id === p.territoryId)
    if (!territory || p.farmerIds.some(id => !demoFarmers.some(f => f.id === id))) throw new Error('Saved plot refers to an unavailable territory or synthetic profile.')
    farmPlotService.validate(p.geometry, territory, [])
    return { ...p, name: `${p.origin === 'synthetic' ? 'Demo' : 'Local'} plot ${i + 1}`, status: 'local-draft', location: '', notes: '', observation: '' }
  })
  if (new Set(territories.map(t => t.id)).size !== territories.length || new Set(plots.map(p => p.id)).size !== plots.length || data.seasons.some(s => !plots.some(p => p.id === s.plotId))) throw new Error('Saved workspace contains invalid relationships.')
  return { territories, plots, seasons: data.seasons, currentId: territories.some(t => t.id === data.currentId) ? data.currentId : territories[0]?.id ?? null, demo: data.demo }
}
