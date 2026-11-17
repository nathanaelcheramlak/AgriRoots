import { describe, it, expect, vi } from 'vitest'
import { z } from 'zod'
import { HomeApi } from '../src/api/home-api'
import { ManagedPluginApi, publicDocument, parsePublicJson, exactTarget, connectionSchema, toolSchema } from '../src/features/plugins/managed-api'
import { createManagedStore } from '../src/features/plugins/managed-store'

const identity = { user: 'fixture-admin', office: 'fixture-office', role: 'office_admin' }
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status })
const conn = connectionSchema.parse({ id: 'connection', name: 'Explicit fixture', adapter_type: 'rest', revision: 4, config_revision: 2, enabled_revision: 1, enabled: true, health: 'NOT_TESTED', credential: null, versions: [{ revision: 2, digest: 'c'.repeat(64), configuration: { name: 'Explicit fixture', adapter_type: 'rest', base_url: 'https://example.invalid', authentication: { type: 'none' } } }] })
const tool = toolSchema.parse({ id: 'tool', version_id: 'version', name: 'fixture_lookup', revision: 7, version: 3, digest: 'd'.repeat(64), connection_revision: 2, connection_digest: 'c'.repeat(64), approved: false, enabled: true, enabled_version: 1, revoked_reason: null, specification: { name: 'fixture_lookup', description: 'Fixture only', capability_tags: ['reference.lookup'], input_json_schema: { type: 'object' } } })

describe('managed connector boundary', () => {
  it('rejects credentials in nested definitions/arguments without changing the local draft format', () => {
    expect(() => publicDocument({ request: { query: { api_key: 'fixture-secret' } } })).toThrow('Credential')
    expect(() => parsePublicJson('{"description":"Bearer fixture-secret"}')).toThrow('credentials')
    expect(() => parsePublicJson('invalid')).toThrow('valid JSON')
    expect(publicDocument({ authentication: { type: 'api_key_header', header_name: 'X-API-Key' } })).toEqual({ authentication: { type: 'api_key_header', header_name: 'X-API-Key' } })
  })
  it('reads all backend pages rather than substituting a static provider/draft catalog', async () => {
    const urls: string[] = []
    const api = new ManagedPluginApi(new HomeApi('/backend', async input => { const url = String(input); urls.push(url); return response({ items: url.endsWith('offset=0') ? Array.from({ length: 100 }, (_, i) => ({ id: String(i) })) : [{ id: '100' }] }) }))
    expect(await api.pages('/integrations', z.object({ id: z.string() }), new AbortController().signal)).toHaveLength(101)
    expect(urls).toEqual(['/backend/api/v1/integrations?limit=100&offset=0', '/backend/api/v1/integrations?limit=100&offset=100'])
  })
  it('preserves exact connection/tool revisions independently of enabled older versions', async () => {
    const bodies: unknown[] = []
    const api = new ManagedPluginApi(new HomeApi('/backend', async (_input, init) => { bodies.push(JSON.parse(String(init?.body))); return response(tool) }))
    await api.saveTool(conn, tool.specification, new AbortController().signal, tool)
    expect(bodies[0]).toEqual({ expected_revision: 7, connection_revision: 2, specification: tool.specification })
    expect(exactTarget(tool)).toEqual({ version: 3, connection_revision: 2, digest: tool.digest })
    expect(tool.enabled_version).toBe(1)
    expect(tool.approved).toBe(false)
  })
  it('drops a connection response when the shared auth session changes in flight', async () => {
    let resolve!: (r: Response) => void
    const session = new HomeApi('/backend', () => new Promise(r => { resolve = r }))
    const pending = session.connectorRequest('/api/v1/integrations', new AbortController().signal)
    session.clearSession(); resolve(response({ items: [] }))
    await expect(pending).rejects.toThrow('Session changed')
    await expect(session.connectorRequest('/api/auth/login', new AbortController().signal)).rejects.toThrow('Unsupported')
  })
  it('clears office snapshots and ignores a late registry read after logout', async () => {
    let resolve!: (r: Response) => void
    const api = new ManagedPluginApi(new HomeApi('/backend', async input => String(input).includes('/providers') ? new Promise(r => { resolve = r }) : response({ items: [] })))
    const store = createManagedStore(api)
    store.getState().reset(identity)
    const pending = store.getState().refresh()
    store.getState().reset(null)
    resolve(response({ items: [] }))
    await pending
    expect(store.getState().identity).toBeNull()
    expect(store.getState().loaded).toBe(false)
    expect(store.getState().connections).toEqual([])
  })
  it('retains backend failure states and does not report an approval or test success', async () => {
    const api = new ManagedPluginApi(new HomeApi('/backend', async () => response({ items: [] })))
    const store = createManagedStore(api, 1)
    store.getState().reset(identity)
    const failure = { id: 'failed-test', kind: 'tool_test', target_id: 'version', status: 'failed' as const, result: null, error: { code: 'AUTH_INVALID', message: 'Provider rejected authentication' }, created_at: '2026-11-17T00:00:00Z', updated_at: '2026-11-17T00:00:00Z' }
    expect(await store.getState().perform(signal => store.getState().watch('connection', failure, signal))).toBe(false)
    expect(store.getState().jobs.connection.status).toBe('failed')
    expect(store.getState().error).toContain('AUTH_INVALID')
    expect(store.getState().notice).toBeNull()
    expect(store.getState().tools).toEqual({})
  })
  it('blocks a concurrent mutation instead of creating duplicate registration requests', async () => {
    const api = new ManagedPluginApi(new HomeApi('/backend', async () => response({ items: [] })))
    const store = createManagedStore(api); store.getState().reset(identity)
    let release!: () => void
    const first = store.getState().perform(() => new Promise<void>(r => { release = r }))
    const duplicate = vi.fn(async () => {})
    expect(await store.getState().perform(duplicate)).toBe(false)
    expect(duplicate).not.toHaveBeenCalled()
    release(); expect(await first).toBe(true)
  })
})
