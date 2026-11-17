import { z } from 'zod'
import { homeToolSchema } from '../../api/home-contracts'
import type { HomeApi } from '../../api/home-api'
import { publicDocument } from '../plugins/managed-api'

export const manifestSchema = z.object({ name: z.string(), description: z.string(), instructions: z.string(), required_capabilities: z.array(z.string()), optional_capabilities: z.array(z.string()), allowed_internal_actions: z.array(z.string()).default([]), max_followup_rounds: z.number().optional(), triggers: z.array(z.string()).optional() }).strict()
export const skillSchema = z.object({ id: z.string(), name: z.string(), revision: z.number(), version: z.number(), version_id: z.string(), digest: z.string(), manifest: manifestSchema, approved: z.boolean(), enabled: z.boolean(), enabled_version: z.number().nullable(),
  execution: z.object({ available: z.boolean(), blocked_reason: z.string().nullable(), blocked_code: z.string().nullable(), version: z.number(), approved: z.boolean(), manifest: manifestSchema,
    dependencies: z.array(z.object({ capability: z.string(), required: z.boolean(), available: z.boolean() })), missing_optional_capabilities: z.array(z.string()),
    tools: z.array(homeToolSchema.extend({ source: z.object({ name: z.string(), host: z.string().nullable() }) })),
  }).optional(),
})
export type Skill = z.infer<typeof skillSchema>
export type Manifest = z.infer<typeof manifestSchema>
export class SkillsApi {
  constructor(private readonly session: HomeApi) {}
  call(path: string, signal: AbortSignal, method = 'GET', body?: unknown) {
    return this.session.skillRequest('/api/v1/skills' + path, signal, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  }
  async list(signal: AbortSignal) {
    const rows: Skill[] = []
    for (let page = 0; page < 100; page++) {
      const data = z.object({ items: z.array(skillSchema) }).parse(await this.call(`?include_execution=true&limit=100&offset=${page * 100}`, signal))
      rows.push(...data.items)
      if (data.items.length < 100) return rows
    }
    throw new Error('The office skill registry exceeds this screen’s 10,000-record limit; no truncated catalog was substituted.')
  }
  async save(manifest: unknown, signal: AbortSignal, existing?: Skill) {
    const value = manifestSchema.parse(publicDocument(manifest))
    return skillSchema.parse(await this.call(existing ? `/${existing.id}/versions` : '', signal, 'POST', existing ? { expected_revision: existing.revision, manifest: value } : value))
  }
}
