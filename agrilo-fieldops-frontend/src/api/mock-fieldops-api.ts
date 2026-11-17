import { analysisSchema, selectionSchema } from './schemas'
import type { AnalysisOptions, FieldOpsApi } from './fieldops-api'
import { abortableDelay } from './fieldops-api'
import type { AssistantContext, Selection } from './types'
import { areaEvidence, providers, syntheticFarms } from '../demo/synthetic-farms'
import { farmsInside } from '../lib/geo'
import { parseAssistant } from '../features/assistant/parser'
export class MockFieldOpsApi implements FieldOpsApi {
  readonly mode = 'mock' as const
  constructor(private readonly scenario: 'success' | 'partial' | 'error' = 'success', private readonly stageMs = 360) {}
  async analyzeArea(selection: Selection, { signal, onProgress }: AnalysisOptions) {
    selectionSchema.parse(selection)
    onProgress('loading_farms')
    await abortableDelay(this.stageMs, signal)
    if (this.scenario === 'error') throw new Error('Demo provider error. Your rectangle is preserved. Retry or change VITE_DEMO_SCENARIO to success.')
    const farms = structuredClone(farmsInside(syntheticFarms, selection.bbox))
    onProgress('screening', farms)
    await abortableDelay(this.stageMs, signal)
    onProgress('preparing_candidates')
    await abortableDelay(this.stageMs, signal)
    if (this.scenario === 'partial') for (const f of farms) {
      f.rainfall.amount = undefined; f.riskLevel = 'unknown'; f.droughtRisk = 'unknown'; f.candidates = []
      f.riskReasons = ['Demo rainfall provider unavailable. Risk and candidates withheld.']
      f.evidence = f.evidence.map(e => e.id.endsWith('RAIN') ? { ...e, value: undefined, status: 'unavailable', details: 'Developer fixture: provider unavailable.' } : e)
    }
    const sourceStatus = providers.map(p => this.scenario === 'partial' && p.id === 'weather' ? { ...p, status: 'unavailable' as const, detail: 'Developer fixture: rainfall provider unavailable; assessments withheld.' } : p)
    return analysisSchema.parse({ id: `analysis-${selection.bbox.join('-')}`, selection_id: selection.selection_id, mode: 'mock', status: sourceStatus.some(p => p.status !== 'available') ? 'partial' : 'completed', checkedAt: new Date().toISOString(), farms, providers: sourceStatus, evidence: this.scenario === 'partial' ? [] : areaEvidence })
  }
  async queryAssistant(text: string, context: AssistantContext, signal: AbortSignal) { await abortableDelay(160, signal); return parseAssistant(text, context) }
}
