import { afterEach, describe, expect, it, vi } from 'vitest'
import { createFieldOpsStore, visibleFarms } from '../src/state/store'
import { MockFieldOpsApi } from '../src/api/mock-fieldops-api'
import { HttpFieldOpsApi } from '../src/api/http-fieldops-api'
import { demoSelection, rectangleSelection } from '../src/lib/geo'
import type { AreaAnalysis } from '../src/api/types'
import { syntheticFarms, providers } from '../src/demo/synthetic-farms'
import { parseAssistant } from '../src/features/assistant/parser'
import { DRAFT_KEY, readDrafts } from '../src/features/advisories/local-drafts'
const stores: ReturnType<typeof createFieldOpsStore>[] = []
const make = (api = new MockFieldOpsApi('success', 1), persist = false) => { const store = createFieldOpsStore(api, undefined, persist); stores.push(store); return store }
const waitForAnalysis = async (store: ReturnType<typeof make>) => vi.waitFor(() => expect(['partial', 'completed']).toContain(store.getState().phase))
afterEach(() => { stores.forEach(s => s.getState().dispose()); stores.length = 0; vi.unstubAllGlobals() })
describe('area screening and synchronized state', () => {
  it('loads the actual bbox, exposes phases, and produces partial-source results', async () => {
    const store = make(), phases: string[] = []; store.subscribe(s => phases.push(s.phase))
    store.getState().setSelection(demoSelection(), 0); expect(store.getState().analysis).toBeNull()
    await waitForAnalysis(store); expect(store.getState().farms).toHaveLength(12)
    expect(phases).toEqual(expect.arrayContaining(['loading_farms', 'screening', 'preparing_candidates', 'partial']))
    expect(store.getState().analysis?.providers.find(p => p.id === 'satellite')?.status).toBe('unavailable')
  })
  it('selects a farm and emits imperative map focus, then edits/clears stale details', async () => {
    const store = make(); store.getState().setSelection(demoSelection(), 0); await waitForAnalysis(store)
    store.getState().selectFarm('F-007'); expect(store.getState().focus).toMatchObject({ type: 'farm', farmIds: ['F-007'] }); expect(store.getState().selectedFarmId).toBe('F-007')
    store.getState().setSelection(rectangleSelection({ lat: 0, lng: 0 }, { lat: .1, lng: .1 }), 0)
    expect(store.getState().selectedFarmId).toBeNull(); expect(store.getState().farms).toEqual([])
    await waitForAnalysis(store); expect(store.getState().farms).toEqual([])
    store.getState().clearSelection(); expect(store.getState()).toMatchObject({ selection: null, phase: 'idle', analysis: null, farms: [] })
  })
  it('debounces repeated edits into one analysis', async () => {
    const api = new MockFieldOpsApi('success', 1), spy = vi.spyOn(api, 'analyzeArea'), store = make(api)
    for (let i = 0; i < 5; i++) store.getState().setSelection(rectangleSelection({ lat: 8.5, lng: 39.21 }, { lat: 8.59 + i * .001, lng: 39.33 }), 10)
    await waitForAnalysis(store); expect(spy).toHaveBeenCalledTimes(1)
  })
  it('aborts previous requests and rejects late results even if an adapter ignores abort', async () => {
    const api = new MockFieldOpsApi('success', 1)
    let oldSignal: AbortSignal | undefined, finish!: (r: AreaAnalysis) => void
    const spy = vi.spyOn(api, 'analyzeArea').mockImplementationOnce((_selection, options) => { oldSignal = options.signal; return new Promise(resolve => { finish = resolve }); })
    const store = make(api), old = demoSelection(); store.getState().setSelection(old, 0)
    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(1))
    store.getState().setSelection(rectangleSelection({ lat: 0, lng: 0 }, { lat: .1, lng: .1 }), 0)
    expect(oldSignal?.aborted).toBe(true); await waitForAnalysis(store)
    finish({ id: 'old', selection_id: old.selection_id, checkedAt: new Date().toISOString(), mode: 'mock', status: 'partial', farms: syntheticFarms, providers, evidence: [] })
    await new Promise(r => setTimeout(r, 10)); expect(store.getState().farms).toEqual([])
  })
  it('keeps failed rectangle, retries, and withholds risk when provider data is missing', async () => {
    const api = new MockFieldOpsApi('success', 1), original = api.analyzeArea.bind(api)
    vi.spyOn(api, 'analyzeArea').mockRejectedValueOnce(new Error('Provider unavailable')).mockImplementation(original)
    const store = make(api), selection = demoSelection(); store.getState().setSelection(selection, 0)
    await vi.waitFor(() => expect(store.getState().phase).toBe('failed'))
    expect(store.getState().selection?.bbox).toEqual(selection.bbox); store.getState().retry(); await waitForAnalysis(store)
    const partialStore = make(new MockFieldOpsApi('partial', 1)); partialStore.getState().setSelection(selection, 0); await waitForAnalysis(partialStore)
    expect(partialStore.getState().farms.every(f => f.riskLevel === 'unknown' && f.candidates.length === 0)).toBe(true)
  })
  it('applies chat commands to shared visible farms and safely rejects unknown actions', async () => {
    const store = make(); store.getState().setSelection(demoSelection(), 0); await waitForAnalysis(store)
    await store.getState().ask('Show high-risk farms'); expect(visibleFarms(store.getState())).toHaveLength(3)
    expect(store.getState().focus.farmIds).toEqual(['F-001', 'F-005', 'F-007'])
    await store.getState().ask('Clear filters'); expect(visibleFarms(store.getState())).toHaveLength(12)
    expect(store.getState().dispatch({ type: 'run_script' })).toBe(false)
    expect(store.getState().dispatch({ type: 'set_layer_visibility', layerId: 'soil', visible: true })).toBe(false)
  })
  it('clears chat context and ignores an answer from the previous selection', async () => {
    const store = make(); store.getState().setSelection(demoSelection(), 0); await waitForAnalysis(store)
    const pending = store.getState().ask('Show high-risk farms'); store.getState().clearSelection(); await pending
    expect(store.getState().messages).toEqual([]); expect(store.getState().filters.risk).toBe('')
  })
})
describe('bounded assistant and draft review', () => {
  const ctx = { selection: demoSelection(), farms: syntheticFarms, selectedFarmId: null, providers }
  it('recognizes crop, candidate, focus and explanation intents from actual context', () => {
    expect(parseAssistant('Show only maize farms', ctx).commands).toContainEqual({ type: 'filter_farms', crop: 'maize' })
    expect(parseAssistant('Which farms are candidates for sorghum?', ctx).commands).toContainEqual({ type: 'filter_farms', candidateCrop: 'sorghum' })
    expect(parseAssistant('Zoom to farm F-007', ctx).commands).toContainEqual({ type: 'select_farm', farmId: 'F-007' })
    expect(parseAssistant('Zoom to farm F-099', ctx).text).toContain('not in the selected area')
    expect(parseAssistant('Explain why Farm F-007 is high risk', ctx).text).toContain(syntheticFarms[6].riskReasons[0])
    expect(parseAssistant('Show soil layer', ctx).text).toContain('unavailable')
    expect(parseAssistant('diagnose disease', ctx).commands).toEqual([])
  })
  it('persists local draft, requires review/name, records approval, and never fetches', async () => {
    const fetchSpy = vi.fn(); vi.stubGlobal('fetch', fetchSpy)
    const store = make(undefined, true); store.getState().setSelection(demoSelection(), 0); await waitForAnalysis(store)
    store.getState().createDraft('F-007'); const draft = store.getState().drafts[0]
    expect(localStorage.getItem(DRAFT_KEY)).toContain(draft.id)
    store.getState().reviewDraft(draft.id, 'approved', 'Officer'); expect(store.getState().drafts[0].status).toBe('draft')
    store.getState().reviewDraft(draft.id, 'pending_review', ''); expect(store.getState().drafts[0].status).toBe('draft')
    store.getState().reviewDraft(draft.id, 'pending_review', 'Officer Hana'); store.getState().reviewDraft(draft.id, 'approved', 'Officer Hana')
    expect(readDrafts()[0]).toMatchObject({ status: 'approved', audit: expect.arrayContaining([expect.objectContaining({ reviewer: 'Officer Hana', status: 'approved' })]) })
    expect(fetchSpy).not.toHaveBeenCalled()
  })
  it('rejects malformed local storage', () => { localStorage.setItem(DRAFT_KEY, '[{"id":"bad"}]'); expect(readDrafts()).toEqual([]) })
  it('requires an explicit independent HTTP base and validates response shape', async () => {
    const api = new HttpFieldOpsApi(''); await expect(api.analyzeArea(demoSelection(), { signal: new AbortController().signal, onProgress: () => {} })).rejects.toThrow('No independent FieldOps backend')
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, json: async () => ({ unsafe: true }) }))
    await expect(new HttpFieldOpsApi('https://example.test').analyzeArea(demoSelection(), { signal: new AbortController().signal, onProgress: () => {} })).rejects.toThrow()
  })
})
