import type { AnalysisJob, AnalysisPhase, AreaAnalysis, AssistantContext, AssistantResponse, Farm, Selection } from './types'
export type AnalysisOptions = { signal: AbortSignal; onProgress: (phase: AnalysisPhase, farms?: Farm[]) => void }
export interface FieldOpsApi {
  readonly mode: 'mock' | 'http'
  analyzeArea(selection: Selection, options: AnalysisOptions): Promise<AreaAnalysis>
  queryAssistant(text: string, context: AssistantContext, signal: AbortSignal): Promise<AssistantResponse>
  getAnalysisJob?(jobId: string, signal: AbortSignal): Promise<AnalysisJob>
}
export function abortableDelay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new DOMException('Aborted', 'AbortError')); return }
    const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
    const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, ms)
    signal.addEventListener('abort', abort, { once: true })
  })
}
