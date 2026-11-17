import { useState } from 'react'
import { PluginModal } from './PluginModal'
import { safeEndpoint } from '../../features/plugins/types'
import { currentConfig, parsePublicJson } from '../../features/plugins/managed-api'
import type { ManagedConnection, ManagedTool } from '../../features/plugins/managed-api'
import { managedApi, useManagedPlugins } from '../../features/plugins/managed-runtime'

export const starterOperation = {
  name: 'reference_lookup', description: 'Describe the reviewed read-only operation and its limitations.', capability_tags: ['reference.lookup'],
  effect_classification: 'READ_ONLY', input_json_schema: { type: 'object', properties: {}, additionalProperties: false },
  request: { method: 'GET', path: '/', query: {} }, response: { format: 'json', field_mapping: {}, normalized_output_json_schema: { type: 'object' } },
  required_data_classes: ['public_environment'],
}
export function ConnectionEditor({ kind, connection, initial, onClose, onCreated }: { kind: 'rest' | 'mcp' | 'builtin'; connection?: ManagedConnection; initial?: Record<string, unknown>; onClose(): void; onCreated(id: string): void }) {
  const s = useManagedPlugins(), config = connection ? currentConfig(connection) : initial
  const auth = config?.authentication as { type?: string; header_name?: string } | undefined
  const [name, setName] = useState(String(config?.name ?? '')), [url, setUrl] = useState(String(config?.base_url ?? ''))
  const [authType, setAuthType] = useState(auth?.type ?? 'none'), [header, setHeader] = useState(auth?.header_name ?? 'X-API-Key')
  const [classes, setClasses] = useState<string[]>(config?.egress_data_classes as string[] ?? ['public_environment'])
  const [error, setError] = useState<string | null>(null)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null)
    if (!safeEndpoint(url) || !name.trim()) { setError('Enter a name and a credential-free HTTPS endpoint (registered local test origins are validated by the backend).'); return }
    const spec = { ...config, name: name.trim(), adapter_type: kind, base_url: url.trim(), authentication: { type: authType, ...(authType === 'api_key_header' ? { header_name: header } : {}) }, egress_data_classes: classes }
    const ok = await s.perform(async signal => { const row = connection ? await managedApi.revise(connection, spec, signal) : await managedApi.create(spec, signal); onCreated(row.id) })
    if (ok) onClose()
  }
  return <PluginModal title={connection ? 'Revise backend connection' : 'Register backend connection'} onClose={onClose}><form className="plugin-config-form" onSubmit={e => void submit(e)}>
    <p>Creates a disabled, office-owned configuration. Registration does not contact the provider, approve tools or activate them.</p>
    <label>Name<input value={name} maxLength={200} onChange={e => setName(e.target.value)} required /></label>
    <label>{kind === 'mcp' ? 'MCP server URL' : 'Base URL (origin only)'}<input value={url} type="url" onChange={e => setUrl(e.target.value)} required disabled={kind === 'builtin'} /></label>
    <p className="plugin-input-help">REST paths belong to operations. The backend requires deployment-approved hosts and pinned public addresses; arbitrary forwarding is blocked. MCP supports Streamable HTTP only.</p>
    <label>Authentication method<select value={authType} disabled={kind === 'builtin'} onChange={e => setAuthType(e.target.value)}><option value="none">None</option><option value="api_key_header">API key header</option><option value="bearer">Bearer</option>{kind === 'builtin' && <option value="provider">Reviewed provider authentication</option>}</select></label>
    {authType === 'api_key_header' && <label>API key header name (no value)<input value={header} onChange={e => setHeader(e.target.value)} /></label>}
    <fieldset><legend>Permitted data classes</legend>{['public_environment', 'plot_coordinates', 'image', 'private_record'].map(value => <label className="managed-check" key={value}><input type="checkbox" checked={classes.includes(value)} disabled={kind === 'builtin'} onChange={e => setClasses(old => e.target.checked ? [...old, value] : old.filter(v => v !== value))} />{value.replaceAll('_', ' ')}</label>)}</fieldset>
    <p className="plugin-credential-note">Credential values are never read or collected here. An authorized backend operator provisions them through the existing write-only credential service. Only presence/revision metadata is displayed. No browser credential store is introduced.</p>
    {connection && <p>Expected revision {connection.revision}. Existing approvals apply only to their recorded versions; a changed configuration requires new review.</p>}
    {(error || s.error) && <p role="alert" className="plugin-field-error">{error ?? s.error}</p>}
    <footer className="plugin-form-actions"><button type="button" className="plugin-secondary" onClick={onClose}>Cancel</button><button type="submit" className="plugin-primary" disabled={s.busy}>{connection ? 'Save new connection revision' : 'Create disabled connection'}</button></footer>
  </form></PluginModal>
}

export function OperationEditor({ connection, tool, initial, onClose }: { connection: ManagedConnection; tool?: ManagedTool; initial?: Record<string, unknown>; onClose(): void }) {
  const s = useManagedPlugins(), [text, setText] = useState(JSON.stringify(tool?.specification ?? initial ?? starterOperation, null, 2)), [error, setError] = useState<string | null>(null)
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null)
    let spec: Record<string, unknown>
    try { spec = parsePublicJson(text) } catch (e) { setError(e instanceof Error ? e.message : 'Invalid definition.'); return }
    const ok = await s.perform(async signal => { await managedApi.saveTool(connection, spec, signal, tool) })
    if (ok) onClose()
  }
  return <PluginModal title={tool ? 'Review and revise operation' : 'Register REST operation'} wide onClose={onClose}><form className="plugin-config-form" onSubmit={e => void submit(e)}>
    <p>{connection.adapter_type === 'mcp' ? 'Remote descriptions and capabilities are untrusted. Review the description, assign supported capability_tags instead of unreviewed.*, and preserve the discovered schema, upstream name and digest.' : 'Declare one fixed read-only JSON operation with bounded input/output schemas and argument/response JSON-pointer mappings. This is configuration, never executable code.'}</p>
    <label>Operation definition (JSON)<textarea className="managed-json-editor" aria-label="Operation definition (JSON)" rows={20} value={text} spellCheck={false} onChange={e => setText(e.target.value)} /></label>
    <p>Credentials and arbitrary URLs do not belong in schemas, mappings or arguments. Saving registers a new unapproved version. Test and approve the exact version separately.</p>
    {(error || s.error) && <p className="plugin-field-error" role="alert">{error ?? s.error}</p>}
    <footer className="plugin-form-actions"><button type="button" className="plugin-secondary" onClick={onClose}>Cancel</button><button className="plugin-primary" disabled={s.busy}>{tool ? 'Save reviewed version' : 'Register unapproved operation'}</button></footer>
  </form></PluginModal>
}
