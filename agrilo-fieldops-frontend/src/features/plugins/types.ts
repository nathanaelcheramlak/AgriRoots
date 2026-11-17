import { z } from 'zod'

const secretText = /(?:api[_-]?key|access[_-]?token|bearer|password|secret)\s*[:=]\s*\S+|\bBearer\s+[A-Za-z0-9._~-]{8,}|\bsk-[\w-]{12,}|-----BEGIN .*PRIVATE KEY/i
export function safeEndpoint(value: string): boolean {
  try {
    const url = new URL(value)
    const loopback = ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname.toLowerCase())
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && loopback)) return false
    if (url.username || url.password || url.search || url.hash || value.includes('?') || value.includes('#')) return false
    const path = decodeURIComponent(url.pathname)
    return !/[?#]/.test(path) && !secretText.test(path) && !/(?:token|secret|password|api[_-]?key|auth)\/[^/]+|eyJ[\w-]{12,}\./i.test(path)
  } catch { return false }
}
const cleanText = (max: number) => z.string().trim().max(max).refine(value => !secretText.test(value), 'Remove credentials or tokens before saving.')
export const customInputSchema = z.object({
  kind: z.enum(['mcp', 'rest']), name: cleanText(80).pipe(z.string().min(2, 'Enter a name of at least 2 characters.')),
  description: cleanText(500), endpoint: z.string().trim().max(1000).refine(safeEndpoint, 'Use a credential-free HTTPS URL, or HTTP on localhost. Queries, fragments and embedded authentication are not allowed.'),
  authMethod: z.enum(['none', 'api_key', 'bearer']), apiKeyHeader: cleanText(64),
}).strict().superRefine((value, ctx) => {
  if (value.kind === 'rest' && safeEndpoint(value.endpoint) && new URL(value.endpoint).protocol === 'http:') ctx.addIssue({ code: 'custom', path: ['endpoint'], message: 'Custom API base URLs must use HTTPS. HTTP loopback URLs are supported only for local MCP servers.' })
  if (value.authMethod === 'api_key' && (!/^[A-Za-z][A-Za-z0-9-]{0,63}$/.test(value.apiKeyHeader) || /^(authorization|cookie|host|proxy-|x-forwarded-|connection|content-length|transfer-encoding)/i.test(value.apiKeyHeader))) {
    ctx.addIssue({ code: 'custom', path: ['apiKeyHeader'], message: 'Enter an API key header name, such as X-API-Key. Do not enter its value.' })
  }
  if (value.authMethod !== 'api_key' && value.apiKeyHeader) ctx.addIssue({ code: 'custom', path: ['apiKeyHeader'], message: 'A header name is only used for API key authentication.' })
})
export type CustomInput = z.infer<typeof customInputSchema>
const draftBase = { id: z.string().uuid(), createdAt: z.iso.datetime(), updatedAt: z.iso.datetime(), owner: z.literal('this_device') }
export const draftSchema = z.discriminatedUnion('type', [
  z.object({ ...draftBase, type: z.literal('catalog'), catalogId: z.string().min(1) }).strict(),
  z.object({ ...draftBase, type: z.literal('custom'), configuration: customInputSchema }).strict(),
])
export const draftDocumentSchema = z.object({ version: z.literal(1), drafts: z.array(draftSchema).max(200) }).strict()
export type PluginDraft = z.infer<typeof draftSchema>
export type CatalogAvailability = 'setup_available' | 'setup_required' | 'unavailable'
export type PluginSource = 'built_in' | 'office' | 'custom'
export type PluginCategory = 'weather' | 'soil' | 'satellite' | 'diagnosis' | 'pests' | 'markets' | 'field_operations' | 'custom'
export interface CatalogItem {
  id: string; name: string; description: string; category: PluginCategory; source: 'built_in';
  resourceKind: 'provider'; availability: CatalogAvailability; requirement: string; docsUrl: string;
  snapshotDate: string; authRequired: boolean; ownerScope: 'system';
}
export interface PluginEntry {
  id: string; name: string; description: string; category: PluginCategory; source: PluginSource;
  availability: CatalogAvailability; requirement: string; catalog?: CatalogItem; draft?: PluginDraft;
}
// Runtime states are derived from authoritative service evidence, never restored from local drafts.
export const LOCAL_STATUS = Object.freeze({ installation: 'Saved locally', configuration: 'Draft', health: 'Not connected', approval: 'Not submitted', enablement: 'Not enabled' })
export const availabilityLabels: Record<CatalogAvailability, string> = { setup_available: 'Setup available', setup_required: 'Setup required', unavailable: 'Setup unavailable' }
export const categoryLabels: Record<PluginCategory, string> = { weather: 'Weather & rainfall', soil: 'Soil & water', satellite: 'Satellite & vegetation', diagnosis: 'Crop health', pests: 'Pests & observations', markets: 'Markets & access', field_operations: 'Field operations', custom: 'Custom connections' }
