import { z } from 'zod'

const object = z.record(z.string(), z.unknown())
export const plotSchema = z.object({
  id: z.string(), name: z.string(), latitude: z.number().min(-90).max(90), longitude: z.number().min(-180).max(180),
  area: z.number().positive(), area_unit: z.string(), synthetic: z.boolean(), crop: z.string().nullable(), planting_date: z.string().nullable(),
})
export const homeToolSchema = z.object({ name: z.string(), version_id: z.string(), capabilities: z.array(z.string()), input_schema: object, plot_scoped: z.boolean(), requires_image: z.boolean(), optional: z.boolean() })
export const homeSkillSchema = z.object({ id: z.string(), name: z.string(), description: z.string(), version: z.number().nullable(), available: z.boolean(), blocked_reason: z.string().nullable(), tools: z.array(homeToolSchema), missing_optional_capabilities: z.array(z.string()) })
export const homeContextSchema = z.object({
  user_id: z.string(), office_id: z.string(), office_name: z.string(), role: z.string(), plots: z.array(plotSchema), skills: z.array(homeSkillSchema),
  model: z.object({ provider: z.enum(['gemini', 'local']), model: z.string(), configured: z.boolean(), execution_enabled: z.boolean(), blocked_reason: z.string().nullable(), plot_data_policy: z.string(), reachability_verified: z.boolean() }),
  max_plots_per_run: z.number().int().positive().max(5), server_area_query: z.boolean(), shared_conversation: z.literal(false),
  // Optional future metadata; validate independently so unavailable territory data
  // cannot break the existing authenticated farm/investigation workspace.
  territory_workspace: z.unknown().optional(),
  registry_workspace: z.object({ available: z.boolean(), version: z.number(), spatial_engine: z.string(), plot_page_limit: z.number(), territory_total: z.number() }).optional(),
})
export const authSchema = z.object({ access_token: z.string().min(1), token_type: z.literal('bearer'), user: z.object({ user_id: z.string() }) })
const sourceSchema = z.object({ provider: z.string().optional(), url: z.string().optional(), units: z.unknown().optional(), value_kind: z.string().optional(), observed_at: z.string().nullable().optional(), valid_time_range: z.object({ from: z.string(), to: z.string() }).nullable().optional() }).passthrough()
export const outcomeSchema = z.object({ execution_outcome: z.string(), data_outcome: z.string(), evidence_ids: z.array(z.string()).optional(), data: z.unknown().optional(), source: sourceSchema.optional(), limitations: z.array(z.string()).optional(), classification: z.string().optional(), cache_hit: z.boolean().optional(), error: z.object({ code: z.string(), message: z.string() }).optional() }).passthrough()
export const resultSchema = z.object({ status: z.enum(['completed', 'partial']), answer: z.string(), evidence_ids: z.array(z.string()), outcomes: z.array(outcomeSchema), skill_version: z.number(), model: object, missing_optional_capabilities: z.array(z.string()).optional(), input_provenance: object.optional() }).passthrough()
export const jobSchema = z.object({
  id: z.string(), kind: z.string(), target_id: z.string(), status: z.enum(['queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled']),
  result: z.unknown().nullable(), error: z.object({ code: z.string(), message: z.string(), retryable: z.boolean().optional() }).nullable(),
  attempts: z.number(), created_at: z.string(), updated_at: z.string(), status_url: z.string(),
  progress: z.object({ calls: z.array(z.object({ id: z.string(), name: z.string(), status: z.string(), started_at: z.string(), finished_at: z.string().nullable() })) }).optional(),
})
export const evidenceResponseSchema = z.object({ id: z.string(), data: z.object({
  source: sourceSchema, retrieved_at: z.string(), valid_time_range: z.object({ from: z.string(), to: z.string() }).nullable().optional(),
  validation_status: z.string(), classification: z.string(), input_synthetic: z.boolean().nullable(), plot_id: z.string().nullable(),
  permitted_plot_ids: z.array(z.string()), limitations: z.array(z.string()), tool_version_id: z.string(),
  values: z.object({ kind: z.string(), payload: z.unknown() }),
}).passthrough() })
export type HomeContext = z.infer<typeof homeContextSchema>
export type HomePlot = z.infer<typeof plotSchema>
export type HomeSkill = z.infer<typeof homeSkillSchema>
export type HomeJob = z.infer<typeof jobSchema>
export type HomeResult = z.infer<typeof resultSchema>
export type HomeEvidence = z.infer<typeof evidenceResponseSchema>
export type HomeOutcome = z.infer<typeof outcomeSchema>
export type HomeRunInput = { task: string; plot_ids: string[]; parameters: Record<string, string>; request_key: string; authorize_network: boolean; authorize_model: boolean; authorize_credit_use: boolean; image_asset_id?: string }
export type HomeInput = { key: string; type: 'text' | 'date'; required: boolean }

export function skillInputs(skill: HomeSkill): HomeInput[] {
  const fields = new Map<string, HomeInput>()
  for (const tool of skill.tools) {
    const properties = tool.input_schema.properties
    if (!properties || typeof properties !== 'object') continue
    for (const [key, schema] of Object.entries(properties)) {
      // This is the actual bounded SkillRunRequest.parameters contract, not arbitrary tool forwarding.
      if (!['start', 'end', 'market_name', 'commodity_name', 'eppo_code', 'from_plot_id', 'to_plot_id', 'resume_invocation_id'].includes(key)) continue
      const required = !tool.optional && Array.isArray(tool.input_schema.required) && tool.input_schema.required.includes(key)
      const isDate = !!schema && typeof schema === 'object' && 'format' in schema && schema.format === 'date'
      fields.set(key, { key, type: isDate ? 'date' : 'text', required: required || !!fields.get(key)?.required })
    }
  }
  return [...fields.values()]
}

export function jobLabel(job: HomeJob): string {
  return ({ queued: 'Queued', running: 'Running', succeeded: 'Completed', partial: 'Partially completed', failed: 'Failed', cancelled: 'Cancelled' })[job.status]
}
