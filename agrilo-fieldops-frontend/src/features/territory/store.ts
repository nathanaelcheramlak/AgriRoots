import { fetchTerritories, registryRequest, write, parseFarmer, parsePlot, farmerPageSchema, mergeHomePlots } from './backend'
import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import type { Polygon, MultiPolygon } from 'geojson'
import type { HomeContext } from '../../api/home-contracts'
import type { AssignmentState, CropSeason, FarmerProfile, FarmPlot, MapInteractionMode, Panel, Territory } from './types'
import { farmerSchema, plotSchema, seasonSchema, territorySchema } from './types'
import { contained, validateBoundary } from './geometry'
import { demoFarmers, demoTerritory } from './fixtures'
import { farmPlotService, restoreLocalWorkspace, saveLocalWorkspace, territoryService } from './services'

export const blankFarmer = (): FarmerProfile => ({ id: `memory-farmer-${crypto.randomUUID()}`, reference: '', displayName: '', village: '', household: '', language: 'Unknown', channel: 'in-person', availability: 'unknown', consent: 'unknown', verification: 'unverified', phone: '', email: '', preferences: '', notes: '', origin: 'memory' })
export const blankSeason = (): CropSeason => ({ id: crypto.randomUUID(), plotId: '', crop: 'Unknown', plantingDate: '', stage: 'Unknown', irrigation: 'unknown', irrigationMethod: 'Unknown', previousCrop: 'Unknown' })
export type TerritoryForm = Pick<Territory, 'name' | 'region' | 'district' | 'description'>
export type PlotForm = Pick<FarmPlot, 'name' | 'farmerIds' | 'location' | 'notes' | 'observation'>
const territoryForm = (): TerritoryForm => ({ name: '', region: '', district: '', description: '' })
const plotForm = (): PlotForm => ({ name: '', farmerIds: [], location: '', notes: '', observation: '' })
export interface TerritoryState {
  backendReady: boolean; busy: boolean; farmerTotal: number; plotTotal: number;
  refreshRegistry(): Promise<void>; loadRegisteredPlots(bbox?: number[]): Promise<void>; loadFarmers(search?: string, offset?: number): Promise<void>;
  submitTerritory(): Promise<boolean>; registerFarmer(): Promise<boolean>; registerPlot(ack: boolean): Promise<boolean>; reviewTerritory(decision: 'approve' | 'reject'): Promise<void>;
  owner: string | null; live: boolean; officeId?: string; officeName?: string; assignments: AssignmentState;
  territories: Territory[]; plots: FarmPlot[]; seasons: CropSeason[]; farmers: FarmerProfile[]; demo: boolean;
  currentId: string | null; selectedPlotId: string | null; selectedFarmerId: string | null;
  mode: MapInteractionMode; panel: Panel; geometry: Polygon | null; previousGeometry: Polygon | null;
  editId: string | null; dirty: boolean; review: boolean; returnToPlot: boolean;
  territoryForm: TerritoryForm; plotForm: PlotForm; seasonForm: CropSeason; farmerForm: FarmerProfile;
  focus: { serial: number; geometry: Polygon | MultiPolygon | null }; notice: string | null; error: string | null; storageError: string | null;
  session(owner: string | null, context: HomeContext | null, live: boolean): void;
  open(panel: Panel): void; close(discard?: boolean): boolean; switchTerritory(id: string, discard?: boolean): boolean;
  beginTerritory(id?: string): void; beginPlot(id?: string): void; beginFarmer(id?: string, fromPlot?: boolean): void;
  updateTerritory(patch: Partial<TerritoryForm>): void; updatePlot(patch: Partial<PlotForm>): void; updateSeason(patch: Partial<CropSeason>): void; updateFarmer(patch: Partial<FarmerProfile>): void;
  setMode(mode: MapInteractionMode): void; preview(geometry: Polygon): void; undoGeometry(): void;
  saveTerritory(): boolean; savePlot(acknowledgeOverlap: boolean): boolean; saveFarmer(): boolean;
  selectPlot(id: string): void; selectFarmer(id: string): void; removePlot(id: string): void;
  fit(geometry: Polygon | MultiPolygon): void; loadDemo(): void; enableDemoFarmers(): void; setReview(value: boolean): void;
}
export function createTerritoryStore() {
  let plotQuery = 0, farmerQuery = 0
  return createStore<TerritoryState>((set, get) => {
    const persist = () => {
      const s = get(); if (!s.owner) return
      try { saveLocalWorkspace(s.owner, s.territories, s.plots, s.seasons, s.currentId, s.demo); set({ storageError: null }) }
      catch { set({ storageError: 'Device storage is unavailable. Your draft remains in this session; it has not been saved on this device.' }) }
    }
    const initial = () => ({ backendReady: false, busy: false, farmerTotal: 0, plotTotal: 0, owner: null, live: false, assignments: { status: 'unsupported', message: 'Territory assignments are not supplied in the local workspace.' } as AssignmentState, territories: [], plots: [], seasons: [], farmers: [], demo: false, currentId: null, selectedPlotId: null, selectedFarmerId: null, mode: 'navigate' as const, panel: null, geometry: null, previousGeometry: null, editId: null, dirty: false, review: false, returnToPlot: false, territoryForm: territoryForm(), plotForm: plotForm(), seasonForm: blankSeason(), farmerForm: blankFarmer(), focus: { serial: 0, geometry: null }, notice: null, error: null, storageError: null, officeId: undefined, officeName: undefined })
    const fail = (e: unknown) => { set({ error: e instanceof Error ? e.message : 'The draft could not be validated.' }); return false }
    return {
      ...initial(),
      session(owner, context, live) {
        if (owner !== get().owner) {
          const serial = get().focus.serial + 1
          set({ ...initial(), owner, live, focus: { serial, geometry: null } })
          if (owner) try { const saved = restoreLocalWorkspace(owner); if (saved) { set({ ...saved, farmers: saved.demo ? demoFarmers : [] }); const t = saved.territories.find(t => t.id === saved.currentId); if (t) get().fit(t.boundary) } } catch { set({ storageError: 'Saved territory data is invalid, outdated or unavailable. It was not restored. You can start a new proposal.' }) }
        }
        const assignments = live ? territoryService.getAssigned(context) : { status: 'unsupported' as const, message: 'Local workspace · no official territory assignments are loaded.' }
        const authorized = assignments.status === 'available' ? assignments.territories : []
        const local = get().territories.filter(t => t.origin !== 'backend')
        const all = [...authorized, ...local], previous = get().currentId
        const firstAssignment = !get().dirty && !get().territories.some(t => t.origin === 'backend' && t.status === 'assigned') && authorized.find(t => t.status === 'assigned')
        const currentId = firstAssignment ? firstAssignment.id : all.some(t => t.id === previous) ? previous : authorized.find(t => t.status === 'assigned')?.id ?? local[0]?.id ?? authorized[0]?.id ?? null
        set({ assignments, territories: all, currentId, officeId: context?.office_id, officeName: context?.office_name, live, backendReady: context?.registry_workspace?.available === true })
        if (!currentId && assignments.status === 'available' && !assignments.territories.length && !get().panel) set({ panel: 'territory' })
        if (currentId !== previous && currentId) get().fit(all.find(t => t.id === currentId)!.boundary)
      },
      async refreshRegistry() {
        const owner = get().owner
        if (!get().backendReady || !owner) return
        set({ busy: true, error: null })
        try {
          const data = await fetchTerritories()
          if (get().owner !== owner) return
          const backend = data.items, local = get().territories.filter(t => t.origin !== 'backend')
          const currentId = backend.some(t => t.id === get().currentId) ? get().currentId : backend.find(t => t.status === 'assigned')?.id ?? backend[0]?.id ?? local[0]?.id ?? null
          set({ territories: [...backend, ...local], assignments: { status: 'available', territories: backend }, currentId,
            notice: data.total > data.items.length ? 'Showing the first 100 territories; additional territory paging is pending.' : null })
          const current = backend.find(t => t.id === currentId)
          if (current) get().fit(current.boundary)
          if (current?.status === 'assigned') await Promise.all([get().loadRegisteredPlots(), get().loadFarmers()])
        } catch (e) { if (get().owner === owner) fail(e) }
        finally { if (get().owner === owner) set({ busy: false }) }
      },
      async loadRegisteredPlots(bbox) {
        const ticket = ++plotQuery
        const owner = get().owner, territory = get().currentId
        if (!get().backendReady || !territory || get().territories.find(t => t.id === territory)?.status !== 'assigned') return
        try {
          const params = new URLSearchParams({ territory_id: territory, limit: '100' })
          if (bbox) params.set('bbox', bbox.join(','))
          const data = farmerPageSchema.parse(await registryRequest('/plots?' + params))
          if (ticket !== plotQuery || owner !== get().owner || territory !== get().currentId) return
          const values = data.items.map(parsePlot), ids = values.map(v => v.plot.id)
          mergeHomePlots(values.map(v => v.home))
          set(s => ({ plots: [...s.plots.filter(p => p.origin !== 'backend'), ...values.map(v => v.plot)],
            seasons: [...s.seasons.filter(c => !s.plots.some(p => p.id === c.plotId && p.origin === 'backend')), ...values.flatMap(v => v.season ? [v.season] : [])],
            plotTotal: data.total, territories: s.territories.map(t => t.id === territory ? { ...t, authorizedPlotIds: ids } : t) }))
        } catch (e) { if (get().owner === owner && get().currentId === territory) fail(e) }
      },
      async loadFarmers(search = '', offset = 0) {
        const ticket = ++farmerQuery
        const owner = get().owner, territory = get().currentId
        if (!get().backendReady || !territory || get().territories.find(t => t.id === territory)?.status !== 'assigned') return
        try {
          const data = farmerPageSchema.parse(await registryRequest('/farmers?' + new URLSearchParams({ territory_id: territory, search, offset: String(offset), limit: '25' })))
          if (ticket !== farmerQuery || get().owner !== owner || get().currentId !== territory) return
          const values = data.items.map(parseFarmer)
          set(s => ({ farmers: [...s.farmers.filter(f => f.origin !== 'backend' || s.plotForm.farmerIds.includes(f.id)), ...values.filter(f => !s.plotForm.farmerIds.includes(f.id))], farmerTotal: data.total }))
        } catch (e) { if (get().owner === owner) fail(e) }
      },
      async submitTerritory() {
        const s = get(), owner = s.owner
        if (!s.backendReady || !s.geometry) return fail(new Error('A completed boundary and authenticated registry are required.'))
        set({ busy: true })
        try {
          const existing = s.territories.find(t => t.id === s.editId && t.origin === 'backend')
          const territory = territorySchema.parse(await registryRequest(existing ? `/territories/${existing.id}` : '/territory-proposals', write({ ...s.territoryForm, boundary: s.geometry, ...(existing ? { expected_revision: existing.revision } : {}) }, existing ? 'PATCH' : 'POST')))
          if (get().owner !== owner) return false
          set(v => ({ territories: [...v.territories.filter(t => t.id !== territory.id), territory], currentId: territory.id, geometry: null, dirty: false, panel: 'territory',
            notice: 'Territory proposal submitted. Approval and an office assignment are required before farm access.' }))
          return true
        } catch (e) { return get().owner === owner ? fail(e) : false }
        finally { if (get().owner === owner) set({ busy: false }) }
      },
      async reviewTerritory(decision) {
        const s = get(), territory = s.territories.find(t => t.id === s.currentId), owner = s.owner
        if (!territory?.revision || !s.backendReady) return
        set({ busy: true })
        try {
          await registryRequest(`/territories/${territory.id}/review`, write({ expected_revision: territory.revision, decision }))
          if (get().owner !== owner) return
          await get().refreshRegistry()
        } catch (e) { if (get().owner === owner) fail(e) }
        finally { if (get().owner === owner) set({ busy: false }) }
      },
      async registerFarmer() {
        const s = get(), f = s.farmerForm, owner = s.owner
        if (!s.backendReady || !s.currentId) return fail(new Error('Choose an assigned territory.'))
        set({ busy: true })
        try {
          const value = parseFarmer(await registryRequest(f.origin === 'backend' ? `/farmers/${f.id}` : '/farmers', write({
            territory_id: s.currentId, reference: f.reference, display_name: f.displayName, village: f.village, language: f.language,
            channel: f.channel, consent: f.consent,
            ...Object.fromEntries(Object.entries({ phone: f.phone, email: f.email, household: f.household, preferences: f.preferences, notes: f.notes }).filter(([, value]) => f.origin !== 'backend' || value !== '')),
            ...(f.origin === 'backend' ? { expected_revision: f.revision, synthetic: f.synthetic ?? false } : {})
          }, f.origin === 'backend' ? 'PATCH' : 'POST')))
          if (get().owner !== owner) return false
          set(v => ({ farmers: [...v.farmers.filter(p => p.id !== value.id), value], selectedFarmerId: value.id,
            panel: s.returnToPlot ? 'plot-form' : 'farmer-details', dirty: s.returnToPlot,
            plotForm: s.returnToPlot ? { ...v.plotForm, farmerIds: [...new Set([...v.plotForm.farmerIds, value.id])] } : v.plotForm,
            notice: 'Farmer saved to the office registry. Contacts remain restricted and encrypted.' }))
          return true
        } catch (e) { return get().owner === owner ? fail(e) : false }
        finally { if (get().owner === owner) set({ busy: false }) }
      },
      async registerPlot(ack) {
        const s = get(), owner = s.owner, existing = s.plots.find(p => p.id === s.editId && p.origin === 'backend')
        if (!s.geometry || !s.currentId) return false
        set({ busy: true })
        try {
          const c = s.seasonForm
          const result = parsePlot(await registryRequest(existing ? `/plots/${existing.id}` : `/territories/${s.currentId}/plots`, write({
            name: s.plotForm.name, geometry: s.geometry, farmer_ids: s.plotForm.farmerIds,
            location: s.plotForm.location, notes: s.plotForm.notes, observation: s.plotForm.observation,
            acknowledge_overlaps: ack, request_key: s.editId ?? crypto.randomUUID(),
            ...(existing ? { expected_revision: existing.revision } : {}),
            season: { crop: c.crop === 'Unknown' ? null : c.crop, planting_date: c.plantingDate || null,
              stage: c.stage === 'Unknown' ? null : c.stage, irrigation: c.irrigation,
              irrigation_method: c.irrigationMethod === 'Unknown' ? null : c.irrigationMethod,
              previous_crop: c.previousCrop === 'Unknown' ? null : c.previousCrop }
          }, existing ? 'PATCH' : 'POST')))
          if (get().owner !== owner) return false
          mergeHomePlots([result.home])
          set(v => ({ plots: [...v.plots.filter(p => p.id !== result.plot.id), result.plot],
            seasons: [...v.seasons.filter(c => c.plotId !== result.plot.id), ...(result.season ? [result.season] : [])],
            farmers: [...v.farmers.filter(f => !result.farmers.some(r => r.id === f.id)), ...result.farmers],
            territories: v.territories.map(t => t.id === s.currentId ? { ...t, authorizedPlotIds: [...new Set([...(t.authorizedPlotIds ?? []), result.plot.id])] } : t),
            selectedPlotId: result.plot.id, dirty: false, geometry: null, editId: null, panel: 'plot-details',
            notice: 'Farm registered with a permanent plot ID. Gemini privacy restrictions still apply to real-farm investigations.' }))
          return true
        } catch (e) { return get().owner === owner ? fail(e) : false }
        finally { if (get().owner === owner) set({ busy: false }) }
      },
      open: panel => set({ panel, mode: 'navigate', error: null }),
      close(discard = false) { if (get().dirty && !discard) return false; set({ panel: null, mode: 'navigate', geometry: null, previousGeometry: null, dirty: false, editId: null, error: null, review: false }); return true },
      switchTerritory(id, discard = false) {
        const t = get().territories.find(t => t.id === id)
        if (!t || get().dirty && !discard) return false
        get().close(true); set({ currentId: id, selectedPlotId: null, selectedFarmerId: null }); get().fit(t.boundary); persist(); if (t.origin === 'backend' && t.status === 'assigned') { void get().loadRegisteredPlots(); void get().loadFarmers() } return true
      },
      beginTerritory(id) {
        const t = get().territories.find(t => t.id === id)
        if (t?.origin === 'backend' && !get().backendReady) { set({ error: 'Official assignments are read-only without registry editing support.' }); return }
        
        set({ panel: 'territory-setup', editId: t?.id ?? `local-territory-${crypto.randomUUID()}`, territoryForm: t ? { name: t.name, region: t.region, district: t.district, description: t.description } : territoryForm(), geometry: t?.boundary.type === 'Polygon' ? t.boundary : null, previousGeometry: null, dirty: false, review: false, mode: 'navigate', error: null })
      },
      beginPlot(id) {
        const t = get().territories.find(t => t.id === get().currentId)
        if (!t || t.status === 'inactive' || t.status === 'pending-approval') { set({ error: 'Choose an available territory boundary first.' }); return }
        const p = get().plots.find(p => p.id === id)
        set({ panel: 'plot-form', editId: p?.id ?? `local-plot-${crypto.randomUUID()}`, plotForm: p ? { name: p.name, farmerIds: p.farmerIds, location: p.location, notes: p.notes, observation: p.observation } : plotForm(), seasonForm: p ? get().seasons.find(s => s.plotId === p.id) ?? blankSeason() : blankSeason(), geometry: p?.geometry.type === 'Polygon' ? p.geometry : null, previousGeometry: null, dirty: false, review: false, mode: p ? 'navigate' : 'draw-farm-plot', error: null })
      },
      beginFarmer(id, fromPlot = false) {
        const f = get().farmers.find(f => f.id === id)
        set({ panel: 'farmer-form', farmerForm: f ? { ...f, verification: 'unverified' } : blankFarmer(), returnToPlot: fromPlot, error: null, dirty: fromPlot && get().dirty })
      },
      updateTerritory: patch => set(s => ({ territoryForm: { ...s.territoryForm, ...patch }, dirty: true, review: false })),
      updatePlot: patch => set(s => ({ plotForm: { ...s.plotForm, ...patch }, dirty: true, review: false })),
      updateSeason: patch => set(s => ({ seasonForm: { ...s.seasonForm, ...patch }, dirty: true, review: false })),
      updateFarmer: patch => set(s => ({ farmerForm: { ...s.farmerForm, ...patch }, dirty: true })),
      setMode(mode) {
        const s = get()
        if ((mode.endsWith('territory') && s.panel !== 'territory-setup') || (mode.endsWith('farm-plot') && s.panel !== 'plot-form')) { set({ error: 'Open the matching territory or plot registration before drawing.' }); return }
        if (mode.startsWith('edit-') && !s.geometry) { set({ error: 'Complete a draft boundary before editing it.' }); return }
        set({ mode, error: null })
      },
      preview(geometry) {
        try {
          const s = get(), kind = s.panel === 'territory-setup' ? 'territory' : 'plot'
          validateBoundary(geometry, kind)
          if (kind === 'plot') { const t = s.territories.find(t => t.id === s.currentId); if (!t) throw new Error('Choose a territory first.'); farmPlotService.validate(geometry, t, s.plots, s.editId ?? undefined) }
          set({ previousGeometry: s.geometry, geometry, mode: 'navigate', dirty: true, error: null, review: false }); get().fit(geometry)
        } catch (e) { fail(e); set({ mode: 'navigate' }) }
      },
      undoGeometry() { const s = get(); set({ geometry: s.previousGeometry, previousGeometry: s.geometry, dirty: true, review: false, mode: 'navigate' }) },
      saveTerritory() {
        try {
          const s = get(); if (!s.geometry) throw new Error('Draw or enter a complete boundary before saving.')
          validateBoundary(s.geometry, 'territory')
          const id = s.editId ?? `local-territory-${crypto.randomUUID()}`
          if (s.plots.some(p => p.territoryId === id && !contained(p.geometry, s.geometry!))) throw new Error('This boundary would exclude a saved local plot. Keep all linked plots inside the territory.')
          const t = territorySchema.parse({ ...s.territoryForm, id, status: 'local-draft', origin: 'local', boundary: s.geometry, createdAt: s.territories.find(t => t.id === id)?.createdAt ?? new Date().toISOString(), officeId: s.officeId })
          set({ territories: [...s.territories.filter(t => t.id !== id), t], currentId: id, panel: 'territory', geometry: null, previousGeometry: null, dirty: false, editId: null, mode: 'navigate', notice: 'Local territory proposal saved. This is not an official assignment.', error: null }); persist(); return true
        } catch (e) { return fail(e) }
      },
      savePlot(acknowledgeOverlap) {
        try {
          const s = get(), t = s.territories.find(t => t.id === s.currentId)
          if (!s.geometry || !t) throw new Error('Draw a complete plot inside a territory first.')
          const conflicts = farmPlotService.validate(s.geometry, t, s.plots, s.editId ?? undefined)
          if (conflicts.length && !acknowledgeOverlap) throw new Error('Review the overlapping plot records before saving this local draft.')
          if (!s.plotForm.farmerIds.length || s.plotForm.farmerIds.some(id => !s.farmers.some(f => f.id === id))) throw new Error('Link at least one available farmer profile. Register a temporary profile or use the synthetic directory.')
          const id = s.editId ?? `local-plot-${crypto.randomUUID()}`
          const p = plotSchema.parse({ ...s.plotForm, id, territoryId: t.id, geometry: s.geometry, status: 'local-draft', origin: s.demo && s.plotForm.farmerIds.every(id => demoFarmers.some(f => f.id === id)) ? 'synthetic' : 'local', createdAt: s.plots.find(p => p.id === id)?.createdAt ?? new Date().toISOString() })
          const season = seasonSchema.parse({ ...s.seasonForm, plotId: id })
          set({ plots: [...s.plots.filter(p => p.id !== id), p], seasons: [...s.seasons.filter(p => p.plotId !== id), season], selectedPlotId: id, panel: 'plot-details', geometry: null, previousGeometry: null, dirty: false, editId: null, mode: 'navigate', notice: 'Plot saved as a local draft. It is not authorized for live investigation.', error: null }); persist(); return true
        } catch (e) { return fail(e) }
      },
      saveFarmer() {
        try {
          const s = get(), f = farmerSchema.parse({ ...s.farmerForm, origin: 'memory', verification: 'unverified' })
          if (f.phone && !/^\+?[\d ()-]{7,24}$/.test(f.phone)) throw new Error('Enter a valid telephone number or leave it unknown.')
          if (f.email && !zEmail(f.email)) throw new Error('Enter a valid email address or leave it unknown.')
          if (s.farmers.some(p => p.id !== f.id && p.reference.toLowerCase() === f.reference.toLowerCase())) throw new Error('A farmer with this reference already exists. Open that profile to link another plot.')
          set({ farmers: [...s.farmers.filter(p => p.id !== f.id), f], selectedFarmerId: f.id, panel: s.returnToPlot ? 'plot-form' : 'farmer-details', plotForm: s.returnToPlot ? { ...s.plotForm, farmerIds: [...new Set([...s.plotForm.farmerIds, f.id])] } : s.plotForm, dirty: s.returnToPlot, notice: 'Farmer profile kept in memory for this session only.', error: null }); return true
        } catch (e) { return fail(e) }
      },
      selectPlot(id) { if (get().dirty) { set({ error: 'Finish or discard the open registration before selecting another plot.' }); return } if (!get().plots.some(p => p.id === id)) return; set({ selectedPlotId: id, panel: 'plot-details', mode: 'navigate', error: null }) },
      selectFarmer(id) { if (!get().farmers.some(f => f.id === id)) return; set({ selectedFarmerId: id, panel: 'farmer-details', error: null }) },
      removePlot(id) { set(s => ({ plots: s.plots.filter(p => p.id !== id), seasons: s.seasons.filter(p => p.plotId !== id), selectedPlotId: s.selectedPlotId === id ? null : s.selectedPlotId, panel: null })); persist() },
      fit: geometry => set(s => ({ focus: { serial: s.focus.serial + 1, geometry } })),
      loadDemo() {
        const s = get(), t = s.territories.find(t => t.id === demoTerritory.id) ?? demoTerritory
        set({ territories: [...s.territories.filter(row => row.id !== t.id), t], currentId: t.id, farmers: [...demoFarmers, ...s.farmers.filter(f => f.origin !== 'synthetic' && !demoFarmers.some(seed => seed.id === f.id))], demo: true, selectedPlotId: null, panel: null, mode: 'navigate', dirty: false, error: null, notice: 'Synthetic workspace · 2,000 demonstration farmer profiles. No official assignment or live tool access.' }); get().fit(t.boundary); persist()
      },
      enableDemoFarmers() { set(s => ({ farmers: [...demoFarmers, ...s.farmers.filter(f => !demoFarmers.some(seed => seed.id === f.id))], demo: true })); persist() },
      setReview: review => set({ review }),
    }
  })
}
function zEmail(value: string) { return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) }
export const territoryStore = createTerritoryStore()
export const useTerritory = () => useStore(territoryStore)
