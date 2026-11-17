import { monitorInputSchema, monitoringDocumentSchema, feedbackSchema, decisionSchema } from './types'
import type { FeedbackDraft, MonitorDefinition, MonitorInput, OfficerReviewDecision } from './types'
import { templates } from './catalog'
import { previewRun, sampleFarms, sampleHistory, sampleTimelines } from './fixtures'
import { unavailableMonitoringBackend } from './backend-contract'
import type { MonitoringBackend } from './backend-contract'
export const MONITORING_STORAGE_KEY = 'agrilo-fieldops:monitoring:v1'
export type MonitoringDocument = { version: 1; monitors: MonitorDefinition[]; feedback: FeedbackDraft[] }
export interface MonitoringService {
  readonly backend: MonitoringBackend
  readonly execution: 'unavailable'
  listTemplates(): Promise<typeof templates>
  read(): Promise<{ document: MonitoringDocument; warning: string | null }>
  save(input: MonitorInput, target?: { id: string; version: number }): Promise<MonitorDefinition>
  duplicate(id: string): Promise<MonitorDefinition>
  setPaused(id: string, version: number, paused: boolean): Promise<MonitorDefinition>
  remove(id: string): Promise<void>
  saveFeedback(input: Pick<FeedbackDraft, 'monitorId' | 'farmId' | 'text' | 'reason' | 'evidenceIds' | 'origin'>, target?: { id: string; version: number }): Promise<FeedbackDraft>
  reviewFeedback(id: string, version: number, action: OfficerReviewDecision['action'], reviewer: string): Promise<FeedbackDraft>
  preview: typeof previewRun
  history: typeof sampleHistory
  photoTimelines: typeof sampleTimelines
}
export class LocalMonitoringService implements MonitoringService {
  readonly backend = unavailableMonitoringBackend()
  readonly execution = 'unavailable' as const
  readonly preview = previewRun
  readonly history = sampleHistory
  readonly photoTimelines = sampleTimelines
  private queue: Promise<void> = Promise.resolve()
  constructor(private readonly storage: () => Storage = () => window.localStorage) {}
  async listTemplates() { return templates }
  async read() {
    const empty: MonitoringDocument = { version: 1, monitors: [], feedback: [] }
    try {
      const raw = this.storage().getItem(MONITORING_STORAGE_KEY)
      if (!raw) return { document: empty, warning: null }
      const document = monitoringDocumentSchema.parse(JSON.parse(raw))
      for (const values of [document.monitors, document.feedback]) if (new Set(values.map(v => v.id)).size !== values.length) throw new Error('Duplicate IDs')
      if (document.feedback.some(f => !document.monitors.some(m => m.id === f.monitorId) && !/^10000000-0000-4000-8000-00000000000[1-4]$/.test(f.monitorId))) throw new Error('Unknown monitor')
      if (document.feedback.some(f => !(document.monitors.find(m => m.id === f.monitorId)?.input.scope.farms ?? sampleFarms).some(farm => farm.id === f.farmId))) throw new Error('Unknown farm')
      return { document, warning: null }
    } catch { return { document: empty, warning: 'Saved monitoring data could not be read. No schedules, results or approvals were restored. Save a new draft to replace invalid local data.' } }
  }
  private async current() { return (await this.read()).document }
  private write(document: MonitoringDocument) {
    const parsed = monitoringDocumentSchema.parse(document)
    try { this.storage().setItem(MONITORING_STORAGE_KEY, JSON.stringify(parsed)) }
    catch { throw new Error('Could not save on this device. Check browser storage permissions. Your changes have not been saved.') }
  }
  private serialize<T>(operation: () => Promise<T>) {
    const result = this.queue.then(operation); this.queue = result.then(() => {}, () => {}); return result
  }
  async save(input: MonitorInput, target?: { id: string; version: number }) {
    return this.serialize(async () => {
      const parsed = monitorInputSchema.parse(input), document = await this.current(), old = document.monitors.find(m => m.id === target?.id)
      if (target && (!old || old.version !== target.version)) throw new Error('This configuration changed. Reopen it before editing.')
      const now = new Date().toISOString(), monitor: MonitorDefinition = { id: old?.id ?? crypto.randomUUID(), version: (old?.version ?? 0) + 1, input: parsed, owner: 'this_device', configurationStatus: old?.configurationStatus ?? 'draft', createdAt: old?.createdAt ?? now, updatedAt: now }
      this.write({ ...document, monitors: [...document.monitors.filter(m => m.id !== monitor.id), monitor] }); return monitor
    })
  }
  async duplicate(id: string) {
    const monitor = (await this.current()).monitors.find(m => m.id === id)
    if (!monitor) throw new Error('Local configuration not found.')
    return this.save({ ...monitor.input, name: (monitor.input.name.slice(0, 91) + ' (copy)') })
  }
  async setPaused(id: string, version: number, paused: boolean) {
    return this.serialize(async () => {
      const document = await this.current(), old = document.monitors.find(m => m.id === id)
      if (!old || old.version !== version) throw new Error('This configuration changed. Reopen it and try again.')
      const monitor: MonitorDefinition = { ...old, version: version + 1, configurationStatus: paused ? 'paused' : 'draft', updatedAt: new Date().toISOString() }
      this.write({ ...document, monitors: document.monitors.map(m => m.id === id ? monitor : m) }); return monitor
    })
  }
  async remove(id: string) { return this.serialize(async () => { const d = await this.current(); this.write({ ...d, monitors: d.monitors.filter(m => m.id !== id), feedback: d.feedback.filter(f => f.monitorId !== id) }) }) }
  async saveFeedback(input: Pick<FeedbackDraft, 'monitorId' | 'farmId' | 'text' | 'reason' | 'evidenceIds' | 'origin'>, target?: { id: string; version: number }) {
    return this.serialize(async () => {
      const document = await this.current(), old = document.feedback.find(f => f.id === target?.id)
      if (target && (!old || old.version !== target.version)) throw new Error('This feedback changed. Reopen it before editing.')
      const monitor = document.monitors.find(m => m.id === input.monitorId)
      if (!monitor && !/^10000000-0000-4000-8000-00000000000[1-4]$/.test(input.monitorId)) throw new Error('Save the monitor first.')
      if (monitor && !monitor.input.scope.farms.some(f => f.id === input.farmId)) throw new Error('Choose a farm in this monitor.')
      if (!monitor && !sampleFarms.some(f => f.id === input.farmId)) throw new Error('Choose a farm in this sample.')
      const feedback = feedbackSchema.parse({ ...input, id: old?.id ?? crypto.randomUUID(), version: (old?.version ?? 0) + 1, updatedAt: new Date().toISOString(), decisions: old?.decisions ?? [] })
      this.write({ ...document, feedback: [...document.feedback.filter(f => f.id !== feedback.id), feedback] }); return feedback
    })
  }
  async reviewFeedback(id: string, version: number, action: OfficerReviewDecision['action'], reviewer: string) {
    return this.serialize(async () => {
      const document = await this.current(), old = document.feedback.find(f => f.id === id)
      if (!old || old.version !== version) throw new Error('Save and review the current draft version first.')
      const decision = decisionSchema.parse({ id: crypto.randomUUID(), feedbackVersion: version, action, reviewer, at: new Date().toISOString(), authority: 'local_demo' })
      const feedback = feedbackSchema.parse({ ...old, decisions: [...old.decisions, decision], updatedAt: decision.at })
      this.write({ ...document, feedback: document.feedback.map(f => f.id === id ? feedback : f) }); return feedback
    })
  }
}
