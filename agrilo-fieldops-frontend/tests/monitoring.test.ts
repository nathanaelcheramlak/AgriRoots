import { afterEach, describe, expect, it, vi } from 'vitest'
import { monitorInputSchema, monitorScheduleSchema, monitoringDocumentSchema, ruleSchema } from '../src/features/monitoring/types'
import { sampleHistory, sampleMonitor, sampleScenarios, sampleTimelines, previewRun } from '../src/features/monitoring/fixtures'
import { combinedOutcome, evaluateRule } from '../src/features/monitoring/evaluation'
import { LocalMonitoringService, MONITORING_STORAGE_KEY } from '../src/features/monitoring/service'
import { createMonitoringStore } from '../src/features/monitoring/store'
const input = () => structuredClone(sampleMonitor('rainfall').input)
afterEach(() => vi.unstubAllGlobals())
describe('monitoring configuration validation', () => {
  it('validates every sample configuration and rejects invalid thresholds, units, dates and timezones', () => {
    for (const scenario of sampleScenarios) expect(monitorInputSchema.safeParse(sampleMonitor(scenario.id).input).success).toBe(true)
    const r = input().rules[0]
    for (const value of [-1, 101, NaN, Infinity]) expect(ruleSchema.safeParse({ ...r, threshold: { ...r.threshold, value } }).success).toBe(false)
    expect(ruleSchema.safeParse({ ...r, threshold: { ...r.threshold, unit: '°C' } }).success).toBe(false)
    for (const schedule of [{ timezone: 'Made/Up' }, { startDate: '2026-02-30' }, { endDate: '2026-01-01' }, { reviewDate: '2026-01-01' }, { time: '25:00' }, { monthDay: 31 }]) expect(monitorScheduleSchema.safeParse({ ...input().schedule, ...schedule }).success).toBe(false)
  })
  it('requires farms, capabilities, compatible metric dependencies and selected outputs', () => {
    const v = input()
    expect(monitorInputSchema.safeParse({ ...v, scope: { ...v.scope, farms: [] } }).success).toBe(false)
    expect(monitorInputSchema.safeParse({ ...v, capabilityIds: [] }).success).toBe(false)
    expect(monitorInputSchema.safeParse({ ...v, capabilityIds: ['soil'] }).success).toBe(false)
    expect(monitorInputSchema.safeParse({ ...v, outputs: [] }).success).toBe(false)
    expect(monitorInputSchema.safeParse({ ...v, rules: [{ ...v.rules[0], scope: 'farms', farmIds: ['outside-scope'] }] }).success).toBe(false)
  })
  it('rejects credentials and forged runtime fields in restored documents', () => {
    for (const instructions of ['api_key=never-store-this', 'token=never-store-this', 'refresh_token: never-store-this', 'API key: never-store-this']) expect(monitorInputSchema.safeParse({ ...input(), instructions }).success).toBe(false)
    const m = sampleMonitor('rainfall')
    for (const extra of [{ active: true }, { scheduleState: 'enabled' }, { latestRun: { status: 'succeeded' } }, { credential: 'token' }, { photos: ['data:image/png;base64,private'] }]) expect(monitoringDocumentSchema.safeParse({ version: 1, monitors: [{ ...m, ...extra }], feedback: [] }).success).toBe(false)
  })
})
describe('deterministic threshold previews', () => {
  it('shows a warning with evidence, resolved changes and unavailable observations as unknown', () => {
    const m = sampleMonitor('rainfall'), run = previewRun(m.input, m.id, 1)
    expect(run.evaluations.find(e => e.farmId === 'F-001')?.outcome).toBe('triggered')
    expect(run.evaluations.find(e => e.farmId === 'F-007')?.outcome).toBe('unknown')
    expect(run.alerts.find(a => a.farmId === 'F-005')?.state).toBe('resolved')
    expect(run.alerts.every(a => a.evidenceIds.length)).toBe(true)
    expect(new Set(run.alerts.map(a => a.deduplicationKey)).size).toBe(run.alerts.length)
    expect(sampleHistory(m.input, m.id, 1)).toEqual(sampleHistory(m.input, m.id, 1))
  })
  it('requires compatible references, sufficient consecutive checks and never uses synthetic evidence as a real Home observation', () => {
    const m = sampleMonitor('rainfall'), run = previewRun(m.input, m.id, 1), r = m.input.rules[0]
    expect(evaluateRule({ ...r, consecutiveChecks: 2 }, 'F-001', run.evidence).outcome).toBe('unknown')
    expect(evaluateRule({ ...r, threshold: { ...r.threshold, reference: 'custom', referenceNote: 'Actual 10 year baseline' } }, 'F-001', run.evidence).outcome).toBe('unknown')
    m.input.scope.farms = m.input.scope.farms.map(f => ({ ...f, source: 'home' }))
    expect(previewRun(m.input, m.id, 1).evaluations.every(e => e.outcome === 'unknown')).toBe(true)
  })
  it('uses three-state AND/OR instead of treating missing data as safe', () => {
    expect(combinedOutcome(['triggered', 'unknown'], 'all')).toBe('unknown')
    expect(combinedOutcome(['triggered', 'unknown'], 'any')).toBe('triggered')
    expect(combinedOutcome(['not_triggered', 'unknown'], 'any')).toBe('unknown')
    expect(combinedOutcome([], 'all')).toBe('unknown')
    const m = sampleMonitor('partial'), run = previewRun(m.input, m.id, 1)
    expect(run.status).toBe('partial'); expect(run.dataGaps).toContain('Satellite observations unavailable. No vegetation inference.')
    const rain = sampleMonitor('rainfall')
    rain.input.combination = 'any'; rain.input.rules.push({ ...rain.input.rules[0], id: crypto.randomUUID(), severity: 'high' })
    expect(previewRun(rain.input, rain.id, 1).alerts.find(a => a.farmId === 'F-001')?.severity).toBe('high')
  })
  it('keeps missing photo submissions operational and all crop observations explicitly illustrative', () => {
    const m = sampleMonitor('missing'), run = previewRun(m.input, m.id, 1), timelines = sampleTimelines()
    expect(run.alerts.find(a => a.farmId === 'F-007')?.detail).toContain('not evidence of crop-health deterioration')
    expect(timelines.find(t => t.farm.id === 'F-007')?.missingDates).toEqual(['2026-11-16'])
    expect(timelines.flatMap(t => t.submissions).every(p => p.kind === 'illustration' && p.analysis === 'unavailable' && !p.objectUrl)).toBe(true)
  })
})
describe('local monitoring adapter', () => {
  it('creates, edits, reloads, duplicates, pauses and deletes drafts with version guards', async () => {
    const service = new LocalMonitoringService()
    expect((await service.read()).document.monitors).toEqual([])
    const created = await service.save(input())
    const edited = await service.save({ ...created.input, schedule: { ...created.input.schedule, frequency: 'monthly', monthDay: 15, timezone: 'UTC' } }, { id: created.id, version: 1 })
    expect(edited.version).toBe(2); expect((await new LocalMonitoringService().read()).document.monitors[0].input.schedule.timezone).toBe('UTC')
    await expect(service.save(input(), { id: created.id, version: 1 })).rejects.toThrow('changed')
    const copy = await service.duplicate(created.id); expect(copy.id).not.toBe(created.id); expect(copy.version).toBe(1)
    const paused = await service.setPaused(copy.id, 1, true); expect(paused.configurationStatus).toBe('paused')
    expect((await service.setPaused(copy.id, 2, false)).configurationStatus).toBe('draft')
    await service.remove(copy.id); expect((await service.read()).document.monitors).toHaveLength(1)
    const stored = localStorage.getItem(MONITORING_STORAGE_KEY)!
    expect(stored).not.toMatch(/active|enabled|nextRun|data:image|blob:|credential|token/)
  })
  it('serializes concurrent writes without dropping configurations', async () => {
    const service = new LocalMonitoringService()
    await Promise.all([service.save(input()), service.save(input())])
    expect((await service.read()).document.monitors).toHaveLength(2)
  })
  it('validates restored data and handles unavailable storage without claiming a save', async () => {
    const service = new LocalMonitoringService()
    localStorage.setItem(MONITORING_STORAGE_KEY, '{"version":1,"monitors":[{"active":true}],"feedback":[]}')
    expect((await service.read()).warning).toBeTruthy()
    localStorage.setItem(MONITORING_STORAGE_KEY, '{broken')
    expect((await service.read()).document.monitors).toEqual([])
    const blocked = new LocalMonitoringService(() => { throw new Error('Blocked') }), store = createMonitoringStore(blocked)
    await store.getState().load(); expect(store.getState().warning).toBeTruthy()
    await expect(blocked.save(input())).rejects.toThrow('Could not save')
    expect(store.getState().monitors).toEqual([])
  })
  it('records only local version-specific reviews, invalidates review on edit and removes associated feedback', async () => {
    const service = new LocalMonitoringService(), monitor = await service.save(input())
    const draft = await service.saveFeedback({ monitorId: monitor.id, farmId: 'F-001', text: 'Please supply a clearer crop observation.', reason: 'Officer review example', evidenceIds: ['sample-evidence'], origin: 'synthetic' })
    const reviewed = await service.reviewFeedback(draft.id, draft.version, 'approve_demo', 'Demo reviewer')
    expect(reviewed.decisions[0].authority).toBe('local_demo')
    const changed = await service.saveFeedback({ ...draft, text: 'Updated feedback for review.' }, { id: draft.id, version: 1 })
    expect(changed.version).toBe(2); expect(changed.decisions.some(d => d.feedbackVersion === changed.version)).toBe(false)
    await expect(service.reviewFeedback(changed.id, 1, 'approve_demo', 'Demo reviewer')).rejects.toThrow('current draft')
    await service.remove(monitor.id); expect((await service.read()).document.feedback).toEqual([])
  })
  it('never requests scheduling, diagnoses or message delivery from the local demo', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch)
    const service = new LocalMonitoringService(), monitor = await service.save(input())
    service.preview(monitor.input, monitor.id, 1); service.history(monitor.input, monitor.id, 1); service.photoTimelines()
    const results = await Promise.all([service.backend.setScheduleState(monitor.id, 1, 'activate'), service.backend.requestRun(monitor.id, 1), service.backend.analyzePhoto('sample', 'example'), service.backend.handoffCommunication({ reviewId: 'local', approvedConnectorId: 'example', recipientIds: [], explicitAuthorization: true })])
    expect(results.every(r => !r.ok && r.error.code === 'BACKEND_REQUIRED')).toBe(true); expect(fetch).not.toHaveBeenCalled()
  })
})
