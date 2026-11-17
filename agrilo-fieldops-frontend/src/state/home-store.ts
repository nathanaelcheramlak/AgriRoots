import { createStore } from 'zustand/vanilla'
import { HomeApi, HomeApiError } from '../api/home-api'
import { resultSchema, skillInputs } from '../api/home-contracts'
import type { HomeContext, HomeEvidence, HomeJob, HomePlot, HomeResult, HomeRunInput } from '../api/home-contracts'
import type { MapState } from '../components/map/map-binding'
import type { Selection } from '../api/types'
import { selectionSchema } from '../api/schemas'
import { abortableDelay } from '../api/fieldops-api'

export type HomeInvestigation = { id: string; conversationId: string; question: string; skillId: string; skillName: string; plotIds: string[]; geometry: Selection | null; request: HomeRunInput; job: HomeJob | null; result: HomeResult | null; evidence: HomeEvidence[]; error: string | null; ambiguous: boolean }
export interface HomeState extends MapState {
  context: HomeContext | null; session: 'signed_out' | 'loading' | 'ready'; error: string | null; toast: string | null;
  plots: HomePlot[]; search: string; selectedIds: string[]; skillId: string; parameters: Record<string, string>;
  conversationId: string; investigations: HomeInvestigation[]; activeId: string | null; imageAssetId: string | null; imageName: string | null;
  authorizations: { network: boolean; model: boolean; credit: boolean };
  localDraftSelected: boolean; territoryPlotIds: string[] | null;
  setLocalDraftSelected(value: boolean): void; setTerritoryScope(ids: string[] | null, reset?: boolean): void;
  login: (phone: string, password: string) => Promise<void>; logout: () => void; reload: () => Promise<void>;
  setSearch: (text: string) => void; chooseSkill: (id: string) => void; setParameter: (key: string, value: string) => void;
  prepareSkill: (id: string, plotIds: string[], parameters: Record<string, string>) => Promise<boolean>;
  authorize: (key: 'network' | 'model' | 'credit', value: boolean) => void; upload: (file: File) => Promise<void>;
  openSavedJob: (jobId: string, plotId: string) => Promise<void>;
  submit: (question: string) => Promise<void>; resume: (id: string) => Promise<void>; cancel: (id: string) => Promise<void>;
}

export function investigationBlock(s: Pick<HomeState, 'context' | 'selectedIds' | 'skillId' | 'parameters' | 'imageAssetId' | 'authorizations' | 'investigations' | 'localDraftSelected' | 'territoryPlotIds'>): string | null {
  const context = s.context, skill = context?.skills.find(k => k.id === s.skillId)
  if (s.localDraftSelected) return 'Live investigation requires a registered, authorized farm.'
  if (s.investigations.some(r => r.ambiguous && !r.job)) return 'Recover the uncertain submission before starting another investigation.'
  if (!context || !skill) return 'Choose an available backend skill.'
  if (!skill.available) return skill.blocked_reason ?? 'This skill is not enabled.'
  if (!context.model.configured || !context.model.execution_enabled) return context.model.blocked_reason ?? 'The backend model is not configured.'
  if (!s.authorizations.model || !s.authorizations.network) return 'Authorize the configured model and provider requests for this investigation.'
  if (s.selectedIds.length > context.max_plots_per_run) return `Select at most ${context.max_plots_per_run} farms.`
  const isRoute = skill.tools.some(t => t.capabilities.includes('logistics.route'))
  if (isRoute && s.selectedIds.length !== 2) return 'Select two authorized farms for this route.'
  if (!isRoute && skill.tools.some(t => t.plot_scoped) && s.selectedIds.length !== 1) return 'This skill requires exactly one selected farm. Your other selections are preserved.'
  if (s.selectedIds.some(id => !context.plots.some(p => p.id === id))) return 'Live investigation requires a registered, authorized farm.'
  if (s.territoryPlotIds && s.selectedIds.some(id => !s.territoryPlotIds!.includes(id))) return 'Select farms from the current authorized territory.'
  if (context.model.provider === 'gemini' && context.model.plot_data_policy === 'synthetic_only' && s.selectedIds.some(id => !context.plots.find(p => p.id === id)?.synthetic)) return 'Backend cloud policy currently permits synthetic farm contexts only.'
  if (skill.tools.some(t => t.requires_image) && (!s.imageAssetId || !s.authorizations.credit)) return 'Upload a crop image and authorize diagnosis credit use.'
  const fields = skillInputs(skill)
  const allowed = new Set(fields.map(f => f.key))
  if (skill.tools.some(t => Array.isArray(t.input_schema.required) && t.input_schema.required.some(k => typeof k !== 'string' || !allowed.has(k)))) return 'This skill requires inputs that Home does not support yet.'
  for (const field of fields) if (field.required && !s.parameters[field.key]?.trim()) return `Enter ${field.key.replaceAll('_', ' ')}.`
  if (s.parameters.start || s.parameters.end) {
    const start = Date.parse(s.parameters.start ?? ''), end = Date.parse(s.parameters.end ?? '')
    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || (end - start) / 86400000 > 30 || end >= Date.parse(new Date().toISOString().slice(0, 10))) return 'Use a past date range of at most 31 days, with both start and end dates.'
  }
  if (isRoute && (!s.selectedIds.includes(s.parameters.from_plot_id) || !s.selectedIds.includes(s.parameters.to_plot_id) || s.parameters.from_plot_id === s.parameters.to_plot_id)) return 'Choose two different route endpoints from the selected farms.'
  return null
}

const terminal = (job: HomeJob) => !['queued', 'running'].includes(job.status)
export function createHomeStore(api: HomeApi, pollMs = 1200) {
  let generation = 0, uploadGeneration = 0, controller = new AbortController(), polling: string | null = null
  const store = createStore<HomeState>((set, get) => {
    const update = (id: string, patch: Partial<HomeInvestigation>) => set(s => ({ investigations: s.investigations.map(r => r.id === id ? { ...r, ...patch } : r) }))
    const project = () => {
      const s = get(), box = s.selection?.bbox
      const visible = s.plots.filter(p => (s.territoryPlotIds === null || s.territoryPlotIds.includes(p.id)) && (!box || (s.context?.registry_workspace?.available && s.territoryPlotIds !== null) || (p.longitude >= box[0] && p.longitude <= box[2] && p.latitude >= box[1] && p.latitude <= box[3])) && `${p.name} ${p.id} ${p.crop ?? ''}`.toLowerCase().includes(s.search.toLowerCase()))
      set({ farms: visible.map(p => ({ id: p.id, displayName: p.name, point: { lat: p.latitude, lon: p.longitude }, currentCrop: p.crop ?? 'Crop not recorded', riskLevel: 'unknown' as const })) })
    }
    const clear = () => { generation++; uploadGeneration++; controller.abort(); controller = new AbortController(); polling = null; api.clearSession(); set({ localDraftSelected: false, territoryPlotIds: null }); set({ context: null, session: 'signed_out', plots: [], farms: [], selectedIds: [], highlightedIds: [], selectedFarmId: null, investigations: [], activeId: null, imageAssetId: null, imageName: null, parameters: {}, skillId: '', error: null, toast: null, search: '', conversationId: crypto.randomUUID(), selection: null, authorizations: { network: false, model: false, credit: false } }) }
    const finish = async (id: string, job: HomeJob, token: number) => {
      if (generation !== token) return
      const parsed = resultSchema.safeParse(job.result)
      update(id, { job, result: parsed.success ? parsed.data : null, error: job.error?.message ?? (job.status === 'failed' ? 'The backend investigation failed.' : null) })
      if (!parsed.success) return
      const collected = await Promise.allSettled(parsed.data.evidence_ids.map(key => api.evidence(key, controller.signal)))
      if (generation !== token) return
      const evidence = collected.flatMap(r => r.status === 'fulfilled' ? [r.value] : [])
      update(id, { evidence, ...(collected.some(r => r.status === 'rejected') ? { error: 'Some evidence could not be retrieved. The backend answer is preserved.' } : {}) })
    }
    const poll = async (id: string, initial: HomeJob) => {
      const token = generation, signal = controller.signal
      if (polling === id) return
      polling = id
      let job = initial
      try {
        for (let step = 0; step < 600; step++) {
          if (generation !== token || signal.aborted) return
          const current = get().investigations.find(r => r.id === id)?.job
          if (current?.status === 'cancelled') job = current
          update(id, { job, ambiguous: false, error: null })
          if (terminal(job)) { await finish(id, job, token); return }
          await abortableDelay(pollMs, signal)
          job = await api.job(job.id, signal)
        }
        update(id, { error: 'Status checking paused. Resume this job to retrieve its current backend state.' })
      } catch (error) {
        if (token === generation && !signal.aborted) update(id, { error: error instanceof Error ? error.message : 'Status could not be retrieved.' })
      } finally { if (polling === id) polling = null; if (generation === token) set({ activeId: null }) }
    }
    const load = async () => {
      const token = generation
      const context = await api.context(controller.signal)
      if (generation !== token) return
      const old = get().context
      if (old && (old.user_id !== context.user_id || old.office_id !== context.office_id)) { clear(); throw new Error('Office membership changed. Sign in again to clear the previous workspace.') }
      const combined = context.skills.find(k => k.available && k.tools.some(t => t.capabilities.includes('weather.forecast')) && k.tools.some(t => t.capabilities.includes('soil.profile')))
      set({ context, plots: context.plots, session: 'ready', skillId: get().skillId || combined?.id || context.skills.find(k => k.available)?.id || '', error: null,
        selectedIds: get().selectedIds.filter(id => context.plots.some(p => p.id === id)) })
      project(); get().focusMap('farms', get().farms.map(f => f.id))
    }
    return {
      context: null, session: 'signed_out', error: null, toast: null, plots: [], farms: [], search: '', selectedIds: [], highlightedIds: [], selectedFarmId: null, skillId: '', parameters: {},
      localDraftSelected: false, territoryPlotIds: null,
      setLocalDraftSelected: localDraftSelected => set({ localDraftSelected }),
      setTerritoryScope: (ids, reset = false) => {
        const s = get(), selected = reset ? [] : s.selectedIds.filter(id => ids === null || ids.includes(id))
        set({ territoryPlotIds: ids, selectedIds: selected, highlightedIds: selected, selectedFarmId: selected.at(-1) ?? null, localDraftSelected: reset ? false : s.localDraftSelected,
          parameters: Object.fromEntries(Object.entries(s.parameters).filter(([key, value]) => !key.endsWith('_plot_id') || selected.includes(value))) }); project()
      },
      conversationId: crypto.randomUUID(), investigations: [], activeId: null, imageAssetId: null, imageName: null, authorizations: { network: false, model: false, credit: false },
      selection: null, phase: 'idle', analysis: null, layers: { farms: true, selection: true, soil: false, rainfall: false, satellite: false, pests: false }, focus: { serial: 0, type: 'reset' },
      login: async (phone, password) => { clear(); const token = generation; set({ session: 'loading', error: null }); try { await api.login(phone, password, controller.signal); await load() } catch (e) { if (token === generation) { api.clearSession(); set({ session: 'signed_out', error: e instanceof Error ? e.message : 'Sign-in failed.' }) } } },
      logout: clear,
      reload: async () => { const token = generation; try { await load() } catch (e) { if (generation === token) set({ error: e instanceof Error ? e.message : 'Backend refresh failed.' }) } },
      setSelection: value => { const selected = selectionSchema.safeParse(value); if (!selected.success) { set({ toast: selected.error.issues[0].message }); return } set({ selection: selected.data, phase: 'idle' }); project() },
      clearSelection: () => { set({ selection: null, phase: 'idle' }); project() },
      setPhase: phase => set({ phase }), notify: toast => set({ toast }),
      toggleLayer: id => { if (id !== 'farms' && id !== 'selection') { set({ toast: 'No backend overlay is available.' }); return } set(s => ({ layers: { ...s.layers, [id]: !s.layers[id] } })) },
      focusMap: (type, farmIds) => set(s => ({ focus: { type, farmIds, serial: s.focus.serial + 1 } })),
      selectFarm: id => { if (!get().plots.some(p => p.id === id) || get().territoryPlotIds && !get().territoryPlotIds!.includes(id)) return; const ids = get().localDraftSelected ? [id] : get().selectedIds.includes(id) ? get().selectedIds.filter(p => p !== id) : [...get().selectedIds, id]; if (ids.length > (get().context?.max_plots_per_run ?? 5)) { set({ toast: 'Select at most five authorized farms.' }); return } set({ selectedIds: ids, highlightedIds: ids, selectedFarmId: ids.at(-1) ?? null, localDraftSelected: false }) },
      setSearch: search => { set({ search }); project() },
      chooseSkill: skillId => { uploadGeneration++; set({ skillId, parameters: {}, imageAssetId: null, imageName: null }); },
      prepareSkill: async (id, plotIds, parameters) => {
        const token = generation, old = get().context
        if (!old || get().activeId || get().investigations.some(r => r.ambiguous && !r.job)) { set({ error: 'Finish or recover the active investigation before preparing another skill.' }); return false }
        try {
          const fresh = old.registry_workspace?.available ? await api.context(controller.signal, plotIds) : await api.context(controller.signal)
          if (token !== generation) return false
          if (fresh.office_id !== old.office_id || fresh.user_id !== old.user_id) { clear(); return false }
          if (get().activeId || get().investigations.some(r => r.ambiguous && !r.job)) throw new Error('An investigation became active. Return to Home without replacing it.')
          const skill = fresh.skills.find(k => k.id === id)
          if (!skill?.available) throw new Error(skill?.blocked_reason ?? 'This skill is no longer available in your office.')
          if (plotIds.length > fresh.max_plots_per_run || new Set(plotIds).size !== plotIds.length || plotIds.some(key => !fresh.plots.some(p => p.id === key))) throw new Error('Use distinct authorized farm references only.')
          const allowed = new Set(skillInputs(skill).map(f => f.key))
          if (Object.entries(parameters).some(([key, value]) => !allowed.has(key) || typeof value !== 'string' || value.length > 100)) throw new Error('The selected skill inputs changed. Reload Skills before continuing.')
          const same = get().skillId === id
          uploadGeneration++
          set({ localDraftSelected: false, context: fresh, plots: fresh.plots, skillId: id, selectedIds: [...plotIds], highlightedIds: [...plotIds], selectedFarmId: plotIds.at(-1) ?? null,
            parameters: { ...parameters }, authorizations: { network: false, model: false, credit: false }, error: null,
            ...(!same ? { imageAssetId: null, imageName: null } : {}) })
          project()
          return true
        } catch (e) { if (token === generation) set({ error: e instanceof Error ? e.message : 'Skill preparation failed.' }); return false }
      },
      setParameter: (key, value) => set(s => ({ parameters: { ...s.parameters, [key]: value } })),
      authorize: (key, value) => set(s => ({ authorizations: { ...s.authorizations, [key]: value } })),
      upload: async file => { const token = generation, ticket = ++uploadGeneration; if (get().activeId) return; try { const asset = await api.upload(file, controller.signal); if (generation !== token || ticket !== uploadGeneration) return; set({ imageAssetId: asset.id, imageName: file.name, error: null }) } catch (e) { if (generation !== token || ticket !== uploadGeneration) return; set({ imageAssetId: null, imageName: null, error: e instanceof Error ? e.message : 'Image upload failed.' }) } },
      submit: async input => {
        const s = get(), question = input.trim()
        if (s.activeId || !question) return
        const reason = investigationBlock(s)
        if (reason) { set({ error: reason }); return }
        const skill = s.context!.skills.find(k => k.id === s.skillId)!
        const keys = new Set(skillInputs(skill).map(f => f.key))
        const request: HomeRunInput = { task: question, plot_ids: [...s.selectedIds], parameters: Object.fromEntries(Object.entries(s.parameters).filter(([k, v]) => keys.has(k) && v.trim())), request_key: crypto.randomUUID(), authorize_network: s.authorizations.network, authorize_model: s.authorizations.model, authorize_credit_use: s.authorizations.credit, ...(s.imageAssetId ? { image_asset_id: s.imageAssetId } : {}) }
        const id = crypto.randomUUID(), token = generation
        const run: HomeInvestigation = { id, conversationId: s.conversationId, question, skillId: skill.id, skillName: skill.name, plotIds: request.plot_ids, geometry: s.selection, request, job: null, result: null, evidence: [], error: null, ambiguous: false }
        set({ investigations: [...s.investigations, run], activeId: id, error: null })
        try { const job = await api.start(skill.id, request, controller.signal); if (generation === token) await poll(id, job) }
        catch (error) { if (generation === token) { update(id, { error: error instanceof Error ? error.message : 'Submission failed.', ambiguous: error instanceof HomeApiError && error.ambiguous }); set({ activeId: null }) } }
      },
      openSavedJob: async (jobId, plotId) => {
        const state = get(), token = generation
        if (!state.context || state.activeId || !state.plots.some(p => p.id === plotId)) return
        const existing = state.investigations.find(r => r.job?.id === jobId)
        if (existing) { await get().resume(existing.id); return }
        const id = crypto.randomUUID()
        set({ activeId: id, error: null })
        try {
          const job = await api.job(jobId, controller.signal)
          if (generation !== token) return
          const skill = get().context?.skills.find(k => k.id === job.target_id)
          const run: HomeInvestigation = { id, conversationId: get().conversationId, question: 'Saved farm investigation', skillId: job.target_id,
            skillName: skill?.name ?? 'Saved registered skill', plotIds: [plotId], geometry: null, job, result: null, evidence: [], error: null, ambiguous: false,
            request: { task: 'Restored investigation', plot_ids: [plotId], parameters: {}, request_key: id, authorize_network: false, authorize_model: false, authorize_credit_use: false } }
          set(v => ({ investigations: [...v.investigations, run] }))
          await poll(id, job)
        } catch (e) { if (generation === token) set({ activeId: null, error: e instanceof Error ? e.message : 'Saved investigation could not be opened.' }) }
      },
      resume: async id => { const run = get().investigations.find(r => r.id === id); if (!run || get().activeId) return; set({ activeId: id }); const token = generation; try { const job = run.job ? await api.job(run.job.id, controller.signal) : await api.start(run.skillId, run.request, controller.signal); if (generation === token) await poll(id, job) } catch (e) { if (generation === token) { update(id, { error: e instanceof Error ? e.message : 'Recovery failed.' }); set({ activeId: null }) } } },
      cancel: async id => { const run = get().investigations.find(r => r.id === id); if (!run?.job) return; const token = generation; try { const job = await api.cancel(run.job.id, controller.signal); if (generation !== token) return; update(id, { job, error: job.error?.message ?? null }) } catch (e) { if (generation !== token) return; update(id, { error: e instanceof Error ? e.message : 'Cancellation failed.' }) } },
    }
  })
  api.onSessionExpired = () => { store.getState().logout(); store.setState({ error: 'Your session expired. Sign in again.' }) }
  return store
}
