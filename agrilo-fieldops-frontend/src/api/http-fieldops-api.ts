import { z } from 'zod'
import { analysisSchema, assistantResponseSchema, selectionSchema } from './schemas'
import type { AnalysisOptions, FieldOpsApi } from './fieldops-api'
import { abortableDelay } from './fieldops-api'
import type { AssistantContext, Selection } from './types'
const jobSchema = z.object({ job_id: z.string(), status: z.enum(['queued', 'running', 'completed', 'partial', 'failed']), stage: z.enum(['loading_farms', 'screening', 'preparing_candidates']).optional(), updatedAt: z.string(), result: analysisSchema.optional(), error: z.string().optional() })
export class HttpFieldOpsApi implements FieldOpsApi {
  readonly mode = 'http' as const
  constructor(private readonly baseUrl: string) {}
  private async request(path: string, signal: AbortSignal, body?: unknown): Promise<unknown> {
    if (!this.baseUrl) throw new Error('No independent FieldOps backend URL configured. Set VITE_API_BASE_URL or return to mock mode.')
    const response = await fetch(`${this.baseUrl.replace(/\/$/, '')}/api/v1${path}`, { signal, method: body === undefined ? 'GET' : 'POST', headers: { 'Content-Type': 'application/json' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
    if (!response.ok) throw new Error(`FieldOps backend returned HTTP ${response.status}. Retry after checking the independent service.`)
    return response.json()
  }
  async getAnalysisJob(jobId: string, signal: AbortSignal) { return jobSchema.parse(await this.request(`/analysis/${encodeURIComponent(jobId)}`, signal)) }
  async analyzeArea(selection: Selection, { signal, onProgress }: AnalysisOptions) {
    onProgress('loading_farms')
    const data = await this.request('/areas/analyze', signal, selectionSchema.parse(selection))
    const direct = analysisSchema.safeParse(data)
    if (direct.success) return direct.data
    let job = jobSchema.parse(data)
    for (let attempt = 0; attempt < 60; attempt++) {
      if (job.status === 'failed') throw new Error(job.error ?? 'Area analysis failed.')
      if (job.status === 'completed' || job.status === 'partial') { if (!job.result) throw new Error('Completed job has no result.'); return job.result }
      onProgress(job.stage ?? 'screening')
      await abortableDelay(1000, signal); job = await this.getAnalysisJob(job.job_id, signal)
    }
    throw new Error('Area analysis timed out. Your selection is preserved for retry.')
  }
  async queryAssistant(text: string, context: AssistantContext, signal: AbortSignal) { return assistantResponseSchema.parse(await this.request('/assistant/query', signal, { text, context })) }
}
