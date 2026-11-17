import { createStore } from 'zustand/vanilla'
import { QueryClient } from '@tanstack/react-query'
import type { FieldOpsApi } from '../api/fieldops-api'
import type { AnalysisPhase, AreaAnalysis, AssistantMessage, DraftAdvisory, Farm, Filters, LayerVisibility, MapFocus, Selection } from '../api/types'
import { assistantResponseSchema, mapCommandSchema, selectionSchema } from '../api/schemas'
import { bboxKey } from '../lib/geo'
import { errorMessage } from '../lib/format'
import { emptyFilters, filterFarms } from '../features/farms/filters'
import { makeDraft, readDrafts, saveDrafts } from '../features/advisories/local-drafts'

export type Tab = 'overview' | 'farms' | 'assistant' | 'advisories'
export interface FieldOpsState {
  mode: 'mock' | 'http'; selection: Selection | null; phase: AnalysisPhase; analysis: AreaAnalysis | null; farms: Farm[];
  selectedFarmId: string | null; filters: Filters; layers: LayerVisibility; tab: Tab; focus: MapFocus;
  messages: AssistantMessage[]; assistantBusy: boolean; drafts: DraftAdvisory[]; error: string | null; toast: string | null;
  setSelection: (selection: Selection, delay?: number) => void; clearSelection: () => void; retry: () => void;
  setPhase: (phase: AnalysisPhase) => void; setTab: (tab: Tab) => void; selectFarm: (id: string) => void;
  setFilters: (filters: Partial<Filters>) => void; clearFilters: () => void; toggleLayer: (id: keyof LayerVisibility) => void;
  focusMap: (type: MapFocus['type'], farmIds?: string[]) => void; dispatch: (command: unknown) => boolean;
  ask: (text: string) => Promise<void>; createDraft: (farmId: string) => void;
  reviewDraft: (id: string, status: DraftAdvisory['status'], reviewer: string) => void;
  notify: (text: string | null) => void; dispose: () => void;
}
export function visibleFarms(s: Pick<FieldOpsState, 'farms' | 'filters'>) { return filterFarms(s.farms, s.filters) }
export function createFieldOpsStore(api: FieldOpsApi, query = new QueryClient({ defaultOptions: { queries: { retry: false } } }), persist = true) {
  let generation = 0, timer: ReturnType<typeof setTimeout> | undefined, chatController: AbortController | undefined
  return createStore<FieldOpsState>((set, get) => {
    const invalidate = () => { generation++; clearTimeout(timer); chatController?.abort(); void query.cancelQueries({ queryKey: ['analysis'] }) }
    const message = (role: AssistantMessage['role'], text: string): AssistantMessage => ({ id: crypto.randomUUID(), role, text, at: new Date().toISOString() })
    const run = async (selection: Selection, token: number) => {
      try {
        const result = await query.fetchQuery({ queryKey: ['analysis', api.mode, bboxKey(selection)], staleTime: 60000, queryFn: ({ signal }) => api.analyzeArea(selection, { signal, onProgress: (phase, farms) => { if (token === generation) set({ phase, ...(farms ? { farms } : {}) }) } }) })
        if (token !== generation) return
        if (result.mode !== api.mode) throw new Error('Backend response mode does not match the configured adapter.')
        set({ analysis: { ...result, selection_id: selection.selection_id }, farms: result.farms, phase: result.status, error: null })
      } catch (error) { if (token === generation) set({ phase: 'failed', error: errorMessage(error), farms: [], analysis: null }) }
    }
    return {
      mode: api.mode, selection: null, phase: 'idle', analysis: null, farms: [], selectedFarmId: null,
      filters: { ...emptyFilters }, layers: { farms: true, selection: true, soil: false, rainfall: false, satellite: false, pests: false },
      tab: 'overview', focus: { serial: 0, type: 'reset' }, messages: [], assistantBusy: false, drafts: persist ? readDrafts() : [], error: null, toast: null,
      setSelection: (input, delay = 300) => {
        const checked = selectionSchema.safeParse(input)
        if (!checked.success) { get().notify(checked.error.issues[0].message); return }
        invalidate(); const token = generation, selection = checked.data
        set({ selection, analysis: null, farms: [], selectedFarmId: null, filters: { ...emptyFilters }, phase: 'loading_farms', error: null, messages: [], assistantBusy: false, layers: { ...get().layers, farms: true, selection: true }, tab: 'overview' })
        timer = setTimeout(() => { void run(selection, token) }, delay)
      },
      clearSelection: () => { invalidate(); set({ selection: null, phase: 'idle', analysis: null, farms: [], selectedFarmId: null, filters: { ...emptyFilters }, error: null, messages: [], assistantBusy: false, tab: 'overview' }) },
      retry: () => { const s = get().selection; if (s) { query.removeQueries({ queryKey: ['analysis', api.mode, bboxKey(s)] }); get().setSelection(s, 0) } },
      setPhase: phase => set({ phase }), setTab: tab => set({ tab }), notify: toast => set({ toast }),
      selectFarm: id => { if (!get().farms.some(f => f.id === id)) return; const filters = visibleFarms(get()).some(f => f.id === id) ? get().filters : { ...emptyFilters }; set({ selectedFarmId: id, tab: 'farms', filters, layers: { ...get().layers, farms: true } }); get().focusMap('farm', [id]) },
      setFilters: filters => {
        const merged = { ...get().filters, ...filters }, visible = filterFarms(get().farms, merged)
        set({ filters: merged, selectedFarmId: visible.some(f => f.id === get().selectedFarmId) ? get().selectedFarmId : null })
      },
      clearFilters: () => set({ filters: { ...emptyFilters } }),
      toggleLayer: id => {
        if (id !== 'farms' && id !== 'selection') { get().notify('This geographic layer needs a connected backend.'); return }
        set({ layers: { ...get().layers, [id]: !get().layers[id] } })
      },
      focusMap: (type, farmIds) => set({ focus: { type, farmIds, serial: get().focus.serial + 1 } }),
      dispatch: input => {
        const parsed = mapCommandSchema.safeParse(input)
        if (!parsed.success) { get().notify('Unsupported map command rejected.'); return false }
        const command = parsed.data
        switch (command.type) {
          case 'filter_farms': get().setFilters({ ...emptyFilters, risk: command.risk ?? '', crop: command.crop ?? '', candidateCrop: command.candidateCrop ?? '' }); set({ layers: { ...get().layers, farms: true } }); break
          case 'clear_filters': get().clearFilters(); set({ layers: { ...get().layers, farms: true } }); break
          case 'select_farm': if (!get().farms.some(f => f.id === command.farmId)) return false; get().selectFarm(command.farmId); break
          case 'zoom_to_farms': get().focusMap('farms', command.farmIds.filter(id => visibleFarms(get()).some(f => f.id === id))); break
          case 'fit_to_selection': get().focusMap('selection'); break
          case 'set_layer_visibility':
            if (!['farms', 'selection'].includes(command.layerId)) { get().notify('Layer unavailable; no geographic data is connected.'); return false }
            set({ layers: { ...get().layers, [command.layerId]: command.visible } }); break
        }
        return true
      },
      ask: async input => {
        const text = input.trim(); if (!text || get().assistantBusy) return
        chatController?.abort(); const controller = new AbortController(); chatController = controller
        const token = generation, s = get()
        set({ messages: [...s.messages, message('user', text)], assistantBusy: true })
        try {
          const response = assistantResponseSchema.parse(await api.queryAssistant(text, { selection: s.selection, farms: s.farms, selectedFarmId: s.selectedFarmId, providers: s.analysis?.providers ?? [] }, controller.signal))
          if (token !== generation || controller.signal.aborted) return
          response.commands.forEach(command => get().dispatch(command))
          set({ messages: [...get().messages, message('assistant', response.text)], assistantBusy: false })
        } catch (error) { if (token === generation && !controller.signal.aborted) set({ assistantBusy: false, messages: [...get().messages, message('assistant', errorMessage(error))] }) }
      },
      createDraft: farmId => {
        if (api.mode !== 'mock') { get().notify('Advisory creation is only connected to local demo storage.'); return }
        const farm = get().farms.find(f => f.id === farmId); if (!farm) return
        const drafts = [makeDraft(farm), ...get().drafts].slice(0, 100)
        const saved = !persist || saveDrafts(drafts)
        set({ drafts, tab: 'advisories', toast: saved ? 'Draft saved locally. Ready for officer review.' : 'Draft kept in memory. Browser storage is unavailable.' })
      },
      reviewDraft: (id, status, reviewer) => {
        if (!reviewer.trim()) { get().notify('Enter a reviewer name to record this local review.'); return }
        const current = get().drafts.find(d => d.id === id)
        const allowed = current && ((current.status === 'draft' && status === 'pending_review') || (current.status === 'pending_review' && (status === 'approved' || status === 'rejected')))
        if (!allowed) { get().notify('Submit a draft for review before approving or rejecting it.'); return }
        const drafts = get().drafts.map(d => d.id === id ? { ...d, status, audit: [...d.audit, { status, reviewer: reviewer.trim(), at: new Date().toISOString() }] } : d)
        const saved = !persist || saveDrafts(drafts)
        set({ drafts, toast: saved ? 'Demo review saved locally. No communication was sent.' : 'Review kept in memory. Browser storage is unavailable.' })
      },
      dispose: () => { invalidate(); query.clear() },
    }
  })
}
