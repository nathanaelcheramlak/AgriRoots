import { describe, expect, it, vi, afterEach } from 'vitest'
import { customInputSchema, draftSchema, LOCAL_STATUS, safeEndpoint } from '../src/features/plugins/types'
import type { CustomInput } from '../src/features/plugins/types'
import { LocalPluginService, PLUGIN_STORAGE_KEY } from '../src/features/plugins/service'
import { createPluginStore, entriesFor } from '../src/features/plugins/store'
import { pluginCatalog } from '../src/features/plugins/catalog'
import { unsupportedBackend } from '../src/features/plugins/backend-contract'
import type { ConnectionId, DiagnosticRequest, VersionTarget } from '../src/features/plugins/backend-contract'

const input: CustomInput = { kind: 'mcp', name: 'Adama field MCP', description: 'Local field context', endpoint: 'https://fields.example/mcp', authMethod: 'none', apiKeyHeader: '' }
afterEach(() => vi.unstubAllGlobals())
describe('untrusted plugin configurations', () => {
  it.each(['https://fields.example/mcp', 'http://localhost:8787/mcp', 'http://127.0.0.1:3000/mcp', 'http://[::1]:8787/mcp'])('accepts a credential-free endpoint %s', value => expect(safeEndpoint(value)).toBe(true))
  it.each(['javascript:alert(1)', 'file:///server/mcp', 'data:text/plain,hello', 'http://fields.example/mcp', 'https://name:password@fields.example/mcp', 'https://fields.example/mcp?api_key=do-not-store', 'https://fields.example/mcp#access-token', 'https://fields.example/mcp?', 'https://fields.example/token/do-not-store', 'https://fields.example/mcp%3Ftoken%3Ddo-not-store', 'https://fields.example/sk-abcdefghijklmnop'])('rejects an unsafe endpoint %s', value => expect(safeEndpoint(value)).toBe(false))
  it('validates header names without accepting credential values or arbitrary auth fields', () => {
    expect(customInputSchema.safeParse({ ...input, authMethod: 'api_key', apiKeyHeader: 'X-API-Key' }).success).toBe(true)
    for (const apiKeyHeader of ['Authorization', 'Cookie', 'X-Forwarded-Host', 'sk-abcdefghijklmnop', 'Bearer do-not-store']) expect(customInputSchema.safeParse({ ...input, authMethod: 'api_key', apiKeyHeader }).success).toBe(false)
    expect(customInputSchema.safeParse({ ...input, token: 'do-not-store' }).success).toBe(false)
    expect(customInputSchema.safeParse({ ...input, description: 'Bearer do-not-store-token' }).success).toBe(false)
    for (const endpoint of ['http://localhost:3000', 'HTTP://localhost:3000', 'h\tttp://localhost:3000']) expect(customInputSchema.safeParse({ ...input, kind: 'rest', endpoint }).success).toBe(false)
  })
  it('keeps local state independent from forged runtime, ownership and approval fields', () => {
    const record = { id: crypto.randomUUID(), type: 'custom', configuration: input, owner: 'this_device', createdAt: new Date().toISOString(), updatedAt: new Date().toISOString() }
    for (const extra of [{ health: 'Connected' }, { approved: true }, { enabled: true }, { officeId: 'some-office' }, { token: 'do-not-store' }]) expect(draftSchema.safeParse({ ...record, ...extra }).success).toBe(false)
    expect(LOCAL_STATUS).toEqual({ installation: 'Saved locally', configuration: 'Draft', health: 'Not connected', approval: 'Not submitted', enablement: 'Not enabled' })
  })
})
describe('local plugin service', () => {
  it('starts empty, preserves catalog provenance, and cannot invent office integrations', async () => {
    const service = new LocalPluginService(), catalog = await service.listCatalog()
    expect(catalog).toHaveLength(22); expect(catalog.every(c => c.source === 'built_in' && c.resourceKind === 'provider' && c.ownerScope === 'system')).toBe(true)
    expect((await service.listDrafts()).drafts).toEqual([])
    expect(entriesFor(catalog, []).some(e => e.source === 'office')).toBe(false)
    expect(catalog.find(c => c.id === 'isda_soil')?.availability).toBe('setup_required')
    expect(catalog.find(c => c.id === 'fao_gaez')?.availability).toBe('unavailable')
  })
  it('serializes concurrent saves and prevents duplicate catalog installation', async () => {
    const service = new LocalPluginService()
    const [a, b] = await Promise.all([service.addCatalog('open_meteo'), service.addCatalog('open_meteo')]); expect(a.id).toBe(b.id)
    await Promise.all([service.addCatalog('nasa_power'), service.saveCustom(input)])
    const restored = await new LocalPluginService().listDrafts(); expect(restored.drafts).toHaveLength(3)
    expect(entriesFor(pluginCatalog, restored.drafts).filter(e => e.draft)).toHaveLength(3)
    await expect(service.addCatalog('fao_gaez')).rejects.toThrow('unavailable')
  })
  it('edits and removes drafts, without persisting credentials or state claims', async () => {
    const service = new LocalPluginService(), draft = await service.saveCustom({ ...input, authMethod: 'api_key', apiKeyHeader: 'X-API-Key' })
    const edited = await service.saveCustom({ ...input, name: 'Updated field MCP' }, draft.id)
    expect(edited.id).toBe(draft.id); expect(edited.createdAt).toBe(draft.createdAt)
    expect(JSON.parse(localStorage.getItem(PLUGIN_STORAGE_KEY)!)).toEqual({ version: 1, drafts: [edited] })
    expect(localStorage.getItem(PLUGIN_STORAGE_KEY)).not.toMatch(/approved|enabled|health|password|credential|Connected/)
    await service.removeDraft(draft.id); expect((await service.listDrafts()).drafts).toEqual([])
  })
  it('rejects secret-bearing submissions before writing storage', async () => {
    const service = new LocalPluginService()
    await expect(service.saveCustom({ ...input, endpoint: 'https://fields.example/mcp?token=do-not-store' })).rejects.toThrow()
    expect(localStorage.getItem(PLUGIN_STORAGE_KEY)).toBeNull()
  })
  it('rejects malformed or tampered stored drafts instead of restoring authority', async () => {
    const service = new LocalPluginService(), draft = await service.saveCustom(input)
    localStorage.setItem(PLUGIN_STORAGE_KEY, JSON.stringify({ version: 1, drafts: [{ ...draft, health: 'Connected', approved: true, enabled: true }] }))
    const result = await service.listDrafts(); expect(result.drafts).toEqual([]); expect(result.warning).toBeTruthy()
    localStorage.setItem(PLUGIN_STORAGE_KEY, '{broken'); expect((await service.listDrafts()).warning).toBeTruthy()
  })
  it('reports storage failure without adding a supposedly saved entry', async () => {
    const service = new LocalPluginService(() => { throw new Error('Storage blocked') }), store = createPluginStore(service)
    await store.getState().load(); expect(store.getState().warning).toBeTruthy()
    await expect(store.getState().saveCustom(input)).rejects.toThrow('Could not save')
    expect(store.getState().drafts).toEqual([]); expect(store.getState().notice).toBeNull()
  })
  it('keeps all backend discovery, testing, approval and enablement operations unsupported', async () => {
    const fetchSpy = vi.fn(); vi.stubGlobal('fetch', fetchSpy)
    const backend = unsupportedBackend(), target = { connectionId: 'future' as ConnectionId, connectionRevision: 1, toolId: 'future-tool', version: 1, digest: 'a'.repeat(64) } as VersionTarget
    const request: DiagnosticRequest = { target, arguments: {}, plotIds: [], requestKey: 'local-test', authorizeNetwork: false }
    const results = await Promise.all([backend.discoverMcpTools(target.connectionId, 1, 'local-test', false), backend.testConnection(request), backend.previewOperation(request), backend.approveToolVersion(target), backend.setConnectionEnabled(target.connectionId, 1, true), backend.listSkills(), backend.listPacks()])
    expect(results.every(r => !r.ok && r.error.code === 'BACKEND_REQUIRED')).toBe(true)
    const service = new LocalPluginService(); await service.addCatalog('open_meteo'); await service.saveCustom(input); expect(fetchSpy).not.toHaveBeenCalled()
  })
})
