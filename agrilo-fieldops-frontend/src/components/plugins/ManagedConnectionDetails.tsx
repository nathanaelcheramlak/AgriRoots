import { useState } from 'react'
import { PluginModal } from './PluginModal'
import { OperationEditor, ConnectionEditor } from './ManagedForms'
import { currentConfig, exactTarget, parsePublicJson, diagnosticSchema } from '../../features/plugins/managed-api'
import type { ManagedConnection, ManagedTool } from '../../features/plugins/managed-api'
import { managedApi, useManagedPlugins } from '../../features/plugins/managed-runtime'
import { useHome } from '../../state/useHome'

export function ManagedConnectionDetails({ connection: c, onClose }: { connection: ManagedConnection; onClose(): void }) {
  const s = useManagedPlugins(), admin = s.identity?.role === 'office_admin', tools = s.tools[c.id] ?? [], jobs = s.tests[c.id] ?? []
  const [tab, setTab] = useState('overview'), [edit, setEdit] = useState(false), [toolEdit, setToolEdit] = useState<ManagedTool | 'new' | null>(null), [network, setNetwork] = useState(false)
  const config = currentConfig(c), job = s.jobs[c.id]
  if (edit) return <ConnectionEditor kind={c.adapter_type} connection={c} onClose={() => setEdit(false)} onCreated={() => {}} />
  if (toolEdit) return <OperationEditor connection={c} tool={toolEdit === 'new' ? undefined : toolEdit} onClose={() => setToolEdit(null)} />
  const toggle = () => s.perform(async signal => { await managedApi.call(`/integrations/${c.id}/enabled`, signal, 'PATCH', { enabled: !c.enabled, expected_revision: c.revision, version: c.config_revision }) })
  const discover = () => s.perform(async signal => { const j = diagnosticSchema.parse(await managedApi.call(`/integrations/${c.id}/discover`, signal, 'POST', { connection_revision: c.config_revision, authorize_network: network, request_key: crypto.randomUUID() })); await s.watch(c.id, j, signal) })
  const template = () => s.perform(async signal => {
    const provider = s.providers.find(p => p.handler_id === config.handler_id)
    if (!provider) throw new Error('No current provider template matches this connection.')
    const result = await managedApi.template(provider.id, signal)
    for (const spec of result.operations) await managedApi.saveTool(c, spec, signal)
  })
  return <PluginModal title="Backend connection details" wide onClose={onClose}>
    <div className="plugin-detail-identity"><div><h3>{c.name}</h3><p>{c.adapter_type} · office-managed · ID {c.id}</p></div></div>
    <div className="plugin-detail-tabs" role="tablist" aria-label="Managed connection sections">{['overview', 'configuration', 'tools', 'testing'].map(t => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t === 'tools' ? 'Tools & operations' : t === 'testing' ? 'Testing & approval' : t[0].toUpperCase() + t.slice(1)}</button>)}</div>
    <div className="plugin-detail-content">
      {tab === 'overview' && <><dl className="plugin-status-grid"><div><dt>Configuration</dt><dd>Revision {c.config_revision} · record revision {c.revision}</dd></div><div><dt>Connection health (recorded)</dt><dd>{c.health}</dd></div><div><dt>Activation</dt><dd>{c.enabled ? `Enabled configuration ${c.enabled_revision}` : 'Disabled'}</dd></div><div><dt>Operations</dt><dd>{tools.length} registered · {tools.filter(t => t.approved).length} current versions approved · {tools.filter(t => t.enabled).length} enabled</dd></div></dl><p>Configured, tested, approved and enabled are separate states. This screen does not perform implicit health probes or model calls.</p><button className="plugin-secondary" disabled={!admin || s.busy} onClick={() => void toggle()}>{c.enabled ? 'Disable connection' : 'Enable connection'}</button><p className="plugin-input-help">Enabling requires a backend-confirmed approved tested operation for this configuration. Each tool must also be enabled separately.</p></>}
      {tab === 'configuration' && <><dl className="plugin-config-summary"><div><dt>Endpoint</dt><dd>{config.base_url}</dd></div><div><dt>Authentication method</dt><dd>{config.authentication.type}</dd></div><div><dt>Credential metadata</dt><dd>{c.credential ? `Stored on backend · revision ${c.credential.revision} · updated ${c.credential.updated_at}` : 'No backend credential recorded'}</dd></div><div><dt>Data classes</dt><dd>{config.egress_data_classes?.join(', ')}</dd></div></dl><p>Credentials are provisioned outside the browser using the secure backend write-only service; existing values cannot be read. Host policy changes require an operator. No interactive OAuth or tenant stdio is supported.</p><button className="plugin-secondary" disabled={!admin || s.busy} onClick={() => setEdit(true)}>Revise connection</button></>}
      {tab === 'tools' && <><p>Current definitions and enabled versions are displayed independently. Tools supplied by MCP servers remain untrusted until reviewed and tested.</p>{c.adapter_type === 'rest' && <button className="plugin-primary" disabled={!admin || s.busy} onClick={() => setToolEdit('new')}>Add REST operation</button>}{c.adapter_type === 'builtin' && !tools.length && <button className="plugin-primary" disabled={!admin || s.busy} onClick={() => void template()}>Register reviewed template operation</button>}{tools.map(t => <section className="managed-tool" key={t.id}><h4>{t.name}</h4><p>{t.specification.description}</p><p>Capabilities: {t.specification.capability_tags.join(', ')}</p><p>Current version {t.version} · {t.approved ? 'Approved' : 'Approval required'} · {t.enabled ? `Enabled version ${t.enabled_version}` : 'Disabled'}{t.enabled && t.enabled_version !== t.version ? ' · enabled version differs from displayed current definition' : ''}</p>{t.revoked_reason && <p>{t.revoked_reason}</p>}<details><summary>Input/output schemas, mappings and policy</summary><pre>{JSON.stringify(t.specification, null, 2)}</pre><p>Digest {t.digest} · connection revision {t.connection_revision}</p></details><button className="plugin-secondary" disabled={!admin || s.busy} onClick={() => setToolEdit(t)}>Review operation {t.name}</button></section>)}</>}
      {tab === 'testing' && <><p>Administrator diagnostics may explicitly test an unapproved definition in isolated test mode. Normal runtime remains approval-gated. There is no direct runtime invocation endpoint on this page.</p><label className="managed-check"><input type="checkbox" checked={network} onChange={e => setNetwork(e.target.checked)} />Authorize network requests for discovery/tests</label>{c.adapter_type === 'mcp' && <button className="plugin-primary" disabled={!admin || s.busy || !network} onClick={() => void discover()}>Discover MCP tools</button>}{job && <section role="status"><p>Recorded job {job.id}: {job.status}</p><button className="plugin-secondary" disabled={s.busy} onClick={() => void s.perform(async signal => { const current = diagnosticSchema.parse(await managedApi.call(`/connector-jobs/${job.id}`, signal)); await s.watch(c.id, current, signal) })}>Refresh status for this job</button><details><summary>Job diagnostics</summary><pre>{JSON.stringify(job, null, 2)}</pre></details></section>}{tools.map(tool => <OperationTest key={`${tool.id}:${tool.version}`} connection={c} tool={tool} network={network} />)}<h4>Recorded test/discovery history</h4>{!jobs.length && <p>No test or discovery evidence recorded.</p>}{jobs.map(j => <details key={j.id}><summary>{j.kind} · {j.status} · {j.created_at}</summary><pre>{JSON.stringify(j, null, 2)}</pre></details>)}</>}
      {!admin && <p>Office administrator permission is required for registration, discovery, tests, review and activation. Your current role is {s.identity?.role}.</p>}
      {s.error && <p role="alert" className="plugin-field-error">{s.error}</p>}{s.notice && <p role="status">{s.notice}</p>}
    </div><footer className="plugin-detail-actions"><button className="plugin-secondary" onClick={onClose}>Done</button></footer>
  </PluginModal>
}

function OperationTest({ connection: c, tool: t, network }: { connection: ManagedConnection; tool: ManagedTool; network: boolean }) {
  const s = useManagedPlugins(), home = useHome(), admin = s.identity?.role === 'office_admin'
  const [args, setArgs] = useState('{}'), [plotIds, setPlotIds] = useState<string[]>([]), [error, setError] = useState<string | null>(null), [preview, setPreview] = useState<unknown>(null)
  const tests = (s.tests[c.id] ?? []).filter(j => j.target_id === t.version_id && j.kind === 'tool_test'), latest = tests[0]
  const action = async (kind: 'preview' | 'test' | 'approve' | 'enabled') => {
    setError(null)
    let arguments_: Record<string, unknown>
    try { arguments_ = parsePublicJson(args) } catch (e) { setError(e instanceof Error ? e.message : 'Invalid arguments.'); return }
    await s.perform(async signal => {
      const path = `/integrations/${c.id}/tools/${t.id}/`, exact = exactTarget(t)
      if (kind === 'approve') { await managedApi.call(path + 'approve', signal, 'POST', exact); return }
      if (kind === 'enabled') { await managedApi.call(path + 'enabled', signal, 'PATCH', { enabled: !t.enabled, expected_revision: t.revision, version: t.version }); return }
      const body = { ...exact, arguments: arguments_, plot_ids: plotIds, authorize_network: network, authorize_credit_use: false, request_key: crypto.randomUUID() }
      const value = await managedApi.call(path + kind, signal, 'POST', body)
      if (kind === 'preview') setPreview(value)
      else await s.watch(c.id, diagnosticSchema.parse(value), signal)
    })
  }
  const blockedCredit = t.specification.capability_tags.includes('crop.diagnosis')
  return <section className="managed-tool"><h4>{t.name} · version {t.version}</h4><p>Approval: {t.approved ? 'Approved exact version' : 'Required'} · activation: {t.enabled ? `Enabled version ${t.enabled_version}` : 'Disabled'} · most recent exact-version test: {latest ? `${latest.status} (${latest.created_at})` : 'Not recorded'}</p>
    <label>Arguments for {t.name} (JSON)<textarea aria-label={`Arguments for ${t.name}`} value={args} spellCheck={false} onChange={e => setArgs(e.target.value)} /></label>
    <fieldset><legend>Authorized farm context for {t.name}</legend>{home.plots.map(p => <label className="managed-check" key={p.id}><input type="checkbox" checked={plotIds.includes(p.id)} disabled={plotIds.length >= 5 && !plotIds.includes(p.id)} onChange={e => setPlotIds(old => e.target.checked ? [...old, p.id] : old.filter(id => id !== p.id))} />{p.name} {p.synthetic ? '(synthetic)' : ''}</label>)}</fieldset>
    <div className="managed-actions"><button className="plugin-secondary" disabled={!admin || s.busy} onClick={() => void action('preview')}>Preview request {t.name}</button><button className="plugin-secondary" disabled={!admin || s.busy || !network || blockedCredit} onClick={() => void action('test')}>Test operation {t.name}</button><button className="plugin-primary" disabled={!admin || s.busy || !tests.some(j => j.status === 'succeeded') || t.approved || t.specification.capability_tags.some(tag => tag.startsWith('unreviewed.'))} onClick={() => void action('approve')}>Approve exact version {t.name}</button><button className="plugin-secondary" disabled={!admin || s.busy || (!t.enabled && !t.approved)} onClick={() => void action('enabled')}>{t.enabled ? 'Disable' : 'Enable'} operation {t.name}</button></div>
    {blockedCredit && <p>Credit-consuming diagnosis tests are unavailable on Plugins. Use the separately authorized private image workflow; no credit is implicitly authorized here.</p>}
    {preview !== null && <details open><summary>Backend preview · no network request executed</summary><pre>{JSON.stringify(preview, null, 2)}</pre></details>}{error && <p role="alert">{error}</p>}
  </section>
}
