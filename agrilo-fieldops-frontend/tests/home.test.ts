import { describe, it, expect, vi } from 'vitest'
import { HomeApi, HomeApiError } from '../src/api/home-api'
import { createHomeStore, investigationBlock } from '../src/state/home-store'
import { evidenceSeries, sourceLink } from '../src/features/home/evidence'
import { homeContextSchema, jobLabel, skillInputs } from '../src/api/home-contracts'
import { context, job, result, evidence, plotId } from './home-fixtures'
import { rectangleSelection } from '../src/lib/geo'

function fixtureApi() {
  return { clearSession: vi.fn(), onSessionExpired: undefined, login: vi.fn().mockResolvedValue('fixture-user'), context: vi.fn().mockResolvedValue(structuredClone(context)), start: vi.fn().mockResolvedValue(job), job: vi.fn().mockResolvedValue({ ...job, status: 'succeeded', result }), cancel: vi.fn().mockResolvedValue({ ...job, status: 'cancelled', error: { code: 'CANCELLED', message: 'Cancelled by backend' } }), evidence: vi.fn().mockResolvedValue(evidence), upload: vi.fn().mockResolvedValue({ id: 'fixture-image' }) }
}
async function ready() {
  const api = fixtureApi(), store = createHomeStore(api as unknown as HomeApi, 1)
  await store.getState().login('fixture-phone', 'fixture-password')
  store.getState().selectFarm(plotId); store.getState().authorize('network', true); store.getState().authorize('model', true)
  return { api, store }
}
describe('Home officer integration', () => {
  it('submits only authorized IDs and preserves job, evidence, conversation and geometry', async () => {
    const { api, store } = await ready()
    const geometry = rectangleSelection({ lat: 9, lng: 38 }, { lat: 9.1, lng: 38.8 })
    store.getState().setSelection(geometry)
    const conversation = store.getState().conversationId
    await store.getState().submit('Inspect weather and soil')
    const request = api.start.mock.calls[0][1]
    expect(request.plot_ids).toEqual([plotId]); expect(request).not.toHaveProperty('coordinates'); expect(request).not.toHaveProperty('geometry')
    expect(request).not.toHaveProperty('office_id'); expect(request).not.toHaveProperty('history')
    const run = store.getState().investigations[0]
    expect(run.job?.status).toBe('succeeded'); expect(run.evidence[0].id).toBe(evidence.id); expect(run.geometry).toEqual(geometry)
    expect(run.conversationId).toBe(conversation); expect(api.start).toHaveBeenCalledTimes(1)
    store.getState().setSelection(rectangleSelection({ lat: 8.9, lng: 38.1 }, { lat: 9.1, lng: 38.9 }))
    expect(store.getState().investigations).toHaveLength(1); expect(api.start).toHaveBeenCalledTimes(1)
  })
  it('does not call providers merely because the map moves or selection changes', async () => {
    const { api, store } = await ready()
    store.getState().setSearch('farm'); store.getState().focusMap('farm', [plotId]); store.getState().clearSelection()
    expect(api.start).not.toHaveBeenCalled()
    expect(store.getState().farms[0].riskLevel).toBe('unknown')
  })
  it('blocks disabled skills, missing model configuration and unsupported farm scope', async () => {
    const { api, store } = await ready()
    store.setState({ context: { ...context, model: { ...context.model, configured: false, blocked_reason: 'Missing configured model' } } })
    await store.getState().submit('Inspect weather and soil'); expect(api.start).not.toHaveBeenCalled(); expect(store.getState().error).toBe('Missing configured model')
    store.setState({ context, selectedIds: [plotId, 'untrusted'] }); expect(investigationBlock(store.getState())).toContain('exactly one')
    store.setState({ context: { ...context, skills: [{ ...context.skills[0], available: false, blocked_reason: 'Disabled by administrator' }] }, selectedIds: [plotId] })
    expect(investigationBlock(store.getState())).toBe('Disabled by administrator')
  })
  it('shows partial outcomes without converting them to success', async () => {
    const { api, store } = await ready()
    api.job.mockResolvedValue({ ...job, status: 'partial', result: { ...result, status: 'partial', outcomes: [...result.outcomes, { execution_outcome: 'TIMEOUT', data_outcome: 'INVALID', error: { code: 'TIMEOUT', message: 'Fixture provider timed out' } }] } })
    await store.getState().submit('Inspect weather and soil')
    expect(store.getState().investigations[0].result?.status).toBe('partial')
    expect(jobLabel(store.getState().investigations[0].job!)).toBe('Partially completed')
  })
  it('recovers an uncertain submission with the same idempotency key', async () => {
    const { api, store } = await ready()
    api.start.mockRejectedValueOnce(new HomeApiError('Lost response', 0, 'BACKEND_UNAVAILABLE', true))
    await store.getState().submit('Inspect weather and soil')
    const run = store.getState().investigations[0], key = api.start.mock.calls[0][1].request_key
    expect(investigationBlock(store.getState())).toContain('uncertain')
    await store.getState().resume(run.id)
    expect(api.start.mock.calls[1][1].request_key).toBe(key); expect(store.getState().investigations).toHaveLength(1)
  })
  it('clears office data on logout and discards delayed context responses', async () => {
    const { api, store } = await ready()
    let resolve!: (value: unknown) => void
    api.context.mockReturnValueOnce(new Promise(r => { resolve = r }))
    const pending = store.getState().reload(); store.getState().logout(); resolve(context); await pending
    expect(store.getState().context).toBeNull(); expect(store.getState().plots).toEqual([]); expect(store.getState().investigations).toEqual([])
  })
  it('never forwards an arbitrary coordinate or unrecognized task input', async () => {
    const { api, store } = await ready()
    store.getState().selectFarm('untrusted-plot'); store.getState().setParameter('latitude', '0')
    await store.getState().submit('Inspect weather and soil')
    expect(api.start.mock.calls[0][1].parameters).toEqual({})
  })
  it('uses runtime input schemas and makes optional tool dates optional', () => {
    const skill = structuredClone(context.skills[0]); skill.tools.push({ ...skill.tools[0], optional: true, input_schema: { type: 'object', properties: { start: { type: 'string', format: 'date' }, end: { type: 'string', format: 'date' } }, required: ['start', 'end'] } })
    expect(skillInputs(skill)).toEqual([{ key: 'start', type: 'date', required: false }, { key: 'end', type: 'date', required: false }])
    expect(() => homeContextSchema.parse({ ...context, max_plots_per_run: 99 })).toThrow()
  })
})

describe('HTTP boundary', () => {
  it('keeps tokens in memory and handles expired officer sessions separately from provider auth errors', async () => {
    const transport = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ access_token: 'explicit-invalid-fixture-token', token_type: 'bearer', user: { user_id: 'fixture-user' } })))
      .mockResolvedValueOnce(new Response(JSON.stringify(context)))
      .mockResolvedValueOnce(new Response(JSON.stringify({ error: { code: 'AUTH_INVALID', message: 'Provider rejected credentials' } }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: 'Session expired' }), { status: 401 }))
    const api = new HomeApi('/backend', transport), expired = vi.fn(); api.onSessionExpired = expired
    const signal = new AbortController().signal
    await api.login('fixture-phone', 'fixture-password', signal); await api.context(signal)
    expect(transport.mock.calls[1][1].headers.Authorization).toBe('Bearer explicit-invalid-fixture-token')
    expect(localStorage.length).toBe(0); expect(sessionStorage.length).toBe(0)
    await expect(api.job('id', signal)).rejects.toThrow('Provider rejected'); expect(expired).not.toHaveBeenCalled()
    await expect(api.job('id', signal)).rejects.toThrow('Sign in again'); expect(expired).toHaveBeenCalledOnce()
  })
  it('does not claim success or fall back to demo after malformed/unreachable responses', async () => {
    const api = new HomeApi('/backend', vi.fn().mockRejectedValue(new TypeError('offline')))
    await expect(api.context(new AbortController().signal)).rejects.toThrow('No demo result')
  })
})

describe('source-aware evidence', () => {
  it('builds charts from actual dated numerical values, not narrative text', () => {
    expect(evidenceSeries(evidence)[0]).toEqual({ label: 'precipitation_sum', unit: 'mm', points: [{ date: '2026-07-01', value: 2 }, { date: '2026-07-02', value: 4 }] })
    expect(evidenceSeries({ ...evidence, data: { ...evidence.data, values: { kind: 'text', payload: 'Expect 50 mm' } } })).toEqual([])
  })
  it('never merges price series across currencies, markets or units', () => {
    const record = { price: 100, commodity_name: 'maize', market_name: 'fixture-market', currency_code: 'ETB', unit: 'KG', price_type: 'retail', reference_period_start: '2026-07-01' }
    expect(evidenceSeries({ ...evidence, data: { ...evidence.data, values: { kind: 'prices', payload: { records: [record, { ...record, unit: '100KG' }] } } } })).toHaveLength(2)
    expect(sourceLink('javascript:alert(1)')).toBeNull(); expect(sourceLink('https://example.invalid/data?token=secret')).toBe('https://example.invalid/data')
  })
})
