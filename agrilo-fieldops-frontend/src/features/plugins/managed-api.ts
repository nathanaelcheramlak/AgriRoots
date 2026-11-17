import { z } from 'zod'
import type { HomeApi } from '../../api/home-api'

export const documentSchema = z.record(z.string(), z.unknown())
const configuration = z.object({ name: z.string(), adapter_type: z.enum(['rest', 'mcp', 'builtin']), base_url: z.string(), handler_id: z.string().nullable().optional(), authentication: z.object({ type: z.string(), header_name: z.string().nullable().optional() }), egress_data_classes: z.array(z.string()).optional() }).passthrough()
export const connectionSchema = z.object({ id: z.string(), name: z.string(), adapter_type: z.enum(['rest', 'mcp', 'builtin']), revision: z.number(), config_revision: z.number(), enabled_revision: z.number().nullable(), enabled: z.boolean(), health: z.string(), credential: z.object({ reference: z.string(), revision: z.number(), updated_at: z.string() }).nullable(), versions: z.array(z.object({ revision: z.number(), digest: z.string(), configuration })) })
export const toolSchema = z.object({ id: z.string(), version_id: z.string(), name: z.string(), revision: z.number(), version: z.number(), digest: z.string(), connection_revision: z.number(), connection_digest: z.string(), approved: z.boolean(), enabled: z.boolean(), enabled_version: z.number().nullable(), revoked_reason: z.string().nullable(), specification: z.object({ name: z.string(), description: z.string(), capability_tags: z.array(z.string()), input_json_schema: documentSchema, context_bindings: z.record(z.string(), z.string()).optional() }).passthrough() })
export const providerSchema = z.object({ id: z.string(), name: z.string(), category: z.string(), handler_id: z.string().nullable(), implemented: z.boolean(), implemented_capabilities: z.array(z.string()), implementation_blocker: z.string().nullable(), historical_verification: z.object({ status: z.string(), verified_at: z.string().nullable().optional() }).passthrough() })
export const diagnosticSchema = z.object({ id: z.string(), kind: z.string(), target_id: z.string(), status: z.enum(['queued', 'running', 'succeeded', 'partial', 'failed', 'cancelled']), result: z.unknown().nullable(), error: z.object({ code: z.string(), message: z.string() }).nullable(), created_at: z.string(), updated_at: z.string() })
export type ManagedConnection = z.infer<typeof connectionSchema>
export type ManagedTool = z.infer<typeof toolSchema>
export type ManagedProvider = z.infer<typeof providerSchema>
export type Diagnostic = z.infer<typeof diagnosticSchema>
export const currentConfig = (c: ManagedConnection) => c.versions.find(v => v.revision === c.config_revision)!.configuration
export const exactTarget = (t: ManagedTool) => ({ version: t.version, connection_revision: t.connection_revision, digest: t.digest })

// Metadata editors are never a substitute for the backend's write-only credential service.
export function publicDocument(value: unknown): Record<string, unknown> {
  const result = documentSchema.parse(value)
  const inspect = (item: unknown): void => {
    if (typeof item === 'string' && /(?:api[_-]?key|password|secret|access[_-]?token)\s*[:=]\s*\S+|\bBearer\s+\S+|-----BEGIN .*PRIVATE KEY|\bsk-[\w-]{12,}/i.test(item)) throw new Error('Remove credentials. Configure authentication through the backend credential service.')
    if (Array.isArray(item)) item.forEach(inspect)
    else if (item && typeof item === 'object') for (const [key, val] of Object.entries(item)) {
      if (val && /^(api[_-]?key|password|secret|token|authorization|cookie|credential_value)$/i.test(key)) throw new Error('Credential fields are not accepted in connection metadata or arguments.')
      inspect(val)
    }
  }
  inspect(result)
  return result
}
export function parsePublicJson(text: string) {
  if (text.length > 100000) throw new Error('Configuration is too large.')
  try { return publicDocument(JSON.parse(text)) } catch (e) { if (e instanceof SyntaxError) throw new Error('Enter a valid JSON object.'); throw e }
}

export class ManagedPluginApi {
  constructor(private readonly session: HomeApi) {}
  async call(path: string, signal: AbortSignal, method = 'GET', body?: unknown) {
    return this.session.connectorRequest('/api/v1' + path, signal, { method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) })
  }
  async pages<T>(path: string, schema: z.ZodType<T>, signal: AbortSignal): Promise<T[]> {
    const items: T[] = []
    for (let page = 0; page < 100; page++) {
      const data = z.object({ items: z.array(schema) }).parse(await this.call(`${path}?limit=100&offset=${page * 100}`, signal))
      items.push(...data.items)
      if (data.items.length < 100) return items
    }
    throw new Error('Registry exceeds this screen’s 10,000-record limit. No truncated registry was substituted.')
  }
  async providers(signal: AbortSignal) { return z.object({ items: z.array(providerSchema) }).parse(await this.call('/providers', signal)).items }
  async template(id: string, signal: AbortSignal) { return z.object({ connection: documentSchema, operations: z.array(documentSchema) }).parse(await this.call(`/providers/${encodeURIComponent(id)}/template`, signal)) }
  async create(spec: unknown, signal: AbortSignal) { return connectionSchema.parse(await this.call('/integrations', signal, 'POST', publicDocument(spec))) }
  async revise(c: ManagedConnection, spec: unknown, signal: AbortSignal) { return connectionSchema.parse(await this.call(`/integrations/${c.id}/versions`, signal, 'POST', { expected_revision: c.revision, configuration: publicDocument(spec) })) }
  async saveTool(c: ManagedConnection, spec: unknown, signal: AbortSignal, tool?: ManagedTool) {
    return toolSchema.parse(await this.call(`/integrations/${c.id}/tools${tool ? `/${tool.id}/versions` : ''}`, signal, 'POST', tool ? { expected_revision: tool.revision, connection_revision: c.config_revision, specification: publicDocument(spec) } : publicDocument(spec)))
  }
}
