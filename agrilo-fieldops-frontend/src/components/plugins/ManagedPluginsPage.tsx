import { useEffect, useState } from 'react'
import type { ReactNode } from 'react'
import { ChevronDown, Plus, Search } from 'lucide-react'
import { useManagedPlugins, managedApi } from '../../features/plugins/managed-runtime'
import type { ManagedProvider } from '../../features/plugins/managed-api'
import { currentConfig } from '../../features/plugins/managed-api'
import { usePlugins } from '../../features/plugins/store'
import type { PluginDraft } from '../../features/plugins/types'
import { ProviderIcon, PluginSocketIcon } from './PluginIcon'
import { ConnectionEditor } from './ManagedForms'
import { ManagedConnectionDetails } from './ManagedConnectionDetails'
import '../../styles/plugins-managed.css'

export function ManagedPluginsPage({ local }: { local: ReactNode }) {
  const s = useManagedPlugins()
  return <ManagedWorkspace key={`${s.identity?.user}:${s.identity?.office}:${s.identity?.role}`} local={local} />
}
function ManagedWorkspace({ local }: { local: ReactNode }) {
  const s = useManagedPlugins(), drafts = usePlugins(), admin = s.identity?.role === 'office_admin'
  const [localMode, setLocalMode] = useState(false), [query, setQuery] = useState(''), [filter, setFilter] = useState('all'), [addOpen, setAddOpen] = useState(false)
  const [selected, setSelected] = useState<string | null>(null), [form, setForm] = useState<{ kind: 'rest' | 'mcp' | 'builtin'; initial?: Record<string, unknown> } | null>(null)
  const [migrationConsent, setMigrationConsent] = useState(false), [failure, setFailure] = useState<string | null>(null)
  const loadDrafts = drafts.load, identity = s.identity, loaded = s.loaded, refresh = s.refresh
  useEffect(() => { void loadDrafts() }, [loadDrafts])
  useEffect(() => { if (identity && !loaded) void refresh() }, [identity, loaded, refresh])
  const matches = (name: string) => name.toLowerCase().includes(query.toLowerCase())
  const providerConnections = (p: ManagedProvider) => s.connections.filter(c => currentConfig(c).handler_id === p.handler_id && !!p.handler_id)
  const openTemplate = async (p: ManagedProvider) => {
    setFailure(null)
    await s.perform(async signal => { const value = await managedApi.template(p.id, signal); setForm({ kind: 'builtin', initial: value.connection }) })
  }
  const migrate = (d: PluginDraft) => {
    if (!migrationConsent) return
    if (d.type === 'custom') {
      const config = d.configuration
      setForm({ kind: config.kind, initial: { name: config.name, adapter_type: config.kind, base_url: config.endpoint, authentication: { type: config.authMethod === 'api_key' ? 'api_key_header' : config.authMethod, ...(config.authMethod === 'api_key' ? { header_name: config.apiKeyHeader } : {}) }, egress_data_classes: ['public_environment'] } })
    } else {
      const p = s.providers.find(p => p.id === d.catalogId)
      if (p?.implemented) void openTemplate(p)
    }
  }
  if (localMode) return <><div className="managed-local-banner plugins-theme"><button className="plugin-secondary" onClick={() => setLocalMode(false)}>Return to backend registry</button><p>These drafts stay on this device. Explicit migration is available on the backend registry page; local IDs are not backend connection IDs.</p></div>{local}</>
  return <div className="plugins-page plugins-theme managed-plugins" key={`${s.identity?.user}:${s.identity?.office}`}>
    <aside className="plugins-secondary" aria-label="Plugin navigation"><div className="customize-heading"><span>Customize</span><PluginSocketIcon size={18} /></div><div className="customize-navigation"><button className="selected" onClick={() => { setFilter('all'); setQuery('') }}>Plugins</button></div><div className="installed-heading"><h2>Office connections</h2><span>{s.connections.length}</span></div><p className="installed-local-note">Backend records · activation is separate</p><div className="installed-plugin-list">{s.connections.map(c => <button key={c.id} onClick={() => setSelected(c.id)}><PluginSocketIcon size={18} /><span><strong>{c.name}</strong><small>{c.enabled ? `Enabled configuration ${c.enabled_revision}` : 'Disabled'} · {c.health}</small></span></button>)}</div><div className="plugins-secondary-footer"><button className="plugin-secondary" onClick={() => setLocalMode(true)}>Open local draft workspace</button></div></aside>
    <main className="plugins-main" aria-label="Backend Plugins workspace"><div className="plugins-content">
      <header className="plugins-header"><div className="plugins-heading-group"><div className="plugin-page-kicker">AGRILO CUSTOMIZE</div><div className="plugins-title-row"><h1>Plugins</h1></div><p>Bring agricultural tools into your field workspace.</p></div><div className="plugins-header-actions"><label className="plugin-search"><Search size={16} /><input aria-label="Search backend plugins" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search plugins" /></label><div className="plugin-add-wrapper"><button className="plugin-add-button" aria-expanded={addOpen} onClick={() => setAddOpen(!addOpen)} disabled={!admin || s.busy}>Add <ChevronDown size={15} /></button>{addOpen && <div className="plugin-menu add-menu"><button onClick={() => { setForm({ kind: 'rest' }); setAddOpen(false) }}>Register custom REST API</button><button onClick={() => { setForm({ kind: 'mcp' }); setAddOpen(false) }}>Register MCP server</button></div>}</div></div></header>
      <div className="plugin-filter-row">{['all', 'built-in', 'office', 'local drafts'].map(f => <button key={f} aria-pressed={filter === f} className={filter === f ? 'selected' : ''} onClick={() => setFilter(f)}>{f[0].toUpperCase() + f.slice(1)}</button>)}<span className="plugin-local-badge">{s.identity ? 'Authenticated backend' : 'Sign in required'}</span></div>
      {!s.identity ? <div className="plugin-page-warning"><p>Sign in on Home to use the same authorized office session. No connection data has been loaded.</p><a href="#home">Open Home sign-in</a><button className="plugin-secondary" onClick={() => setLocalMode(true)}>View local drafts</button></div> : <><p className="plugins-prototype-note">Office {s.identity.office} · role {s.identity.role}. Current backend state is separate from historical provider verification and local drafts.</p><div className="managed-actions"><button className="plugin-secondary" disabled={s.busy} onClick={() => void s.refresh()}>Refresh backend registry</button><button className="plugin-secondary" onClick={() => setLocalMode(true)}>Open local draft workspace</button></div></>}
      {s.busy && <p role="status" className="plugins-loading">Waiting for backend confirmation…</p>}{(s.error || failure) && <p className="plugin-page-warning" role="alert">{s.error ?? failure}</p>}{s.notice && <p role="status">{s.notice}</p>}
      {s.loaded && ['all', 'built-in'].includes(filter) && <section className="plugin-category"><h2>Agricultural providers <span>{s.providers.filter(p => p.implemented).length} implemented</span></h2><div className="plugin-catalog-grid">{s.providers.filter(p => p.implemented && matches(p.name)).map(p => {
        const connections = providerConnections(p), tools = connections.flatMap(c => s.tools[c.id] ?? []), tests = connections.flatMap(c => s.tests[c.id] ?? []).filter(j => j.kind === 'tool_test').sort((a, b) => b.created_at.localeCompare(a.created_at))
        return <article className="plugin-row managed-provider" key={p.id}><div className="plugin-row-main"><ProviderIcon id={p.id} category="custom" /><span className="plugin-row-copy"><strong>{p.name}</strong><span>{p.implemented_capabilities.join(', ')}</span><small>Implemented adapter · {connections.length ? `${connections.length} configured` : 'Not configured'}</small><small>{tools.length} registered · {tools.filter(t => t.approved).length} current approved · {tools.filter(t => t.enabled).length} enabled tools</small><small>{connections.filter(c => c.enabled).length} enabled connections · {tests[0] ? `Last recorded test: ${tests[0].status} · ${tests[0].created_at}` : 'No office test recorded'}</small><small>Historical verification: {p.historical_verification.status}{p.historical_verification.verified_at ? ` · ${p.historical_verification.verified_at}` : ''}</small></span></div><div className="managed-provider-actions">{connections.map(c => <button key={c.id} className="plugin-secondary" onClick={() => setSelected(c.id)}>Inspect {c.name}</button>)}<button aria-label={`Configure ${p.name}`} className="plugin-secondary" disabled={!admin || s.busy} onClick={() => void openTemplate(p)}><Plus size={14} />Configure</button></div></article>
      })}</div><details><summary>Other catalog providers without a reviewed backend adapter</summary>{s.providers.filter(p => !p.implemented).map(p => <p key={p.id}>{p.name}: {p.implementation_blocker} · historical {p.historical_verification.status}</p>)}</details></section>}
      {s.loaded && ['all', 'office'].includes(filter) && <section className="plugin-category"><h2>Office connections</h2>{!s.connections.length && <p>No backend connections configured.</p>}<div className="plugin-catalog-grid">{s.connections.filter(c => matches(c.name)).map(c => <article className="plugin-row" key={c.id}><button className="plugin-row-main" onClick={() => setSelected(c.id)} aria-label={`Inspect connection ${c.name}`}><PluginSocketIcon /><span className="plugin-row-copy"><strong>{c.name}</strong><span>{c.adapter_type} · configuration {c.config_revision} · {c.health}</span><small>{c.enabled ? `Enabled configuration ${c.enabled_revision}` : 'Disabled'} · {(s.tools[c.id] ?? []).length} operations</small></span></button></article>)}</div></section>}
      {['all', 'local drafts'].includes(filter) && <section className="plugin-category"><h2>Local drafts <span>{drafts.drafts.length}</span></h2><p>Drafts are preserved. Migration copies reviewed metadata into a new disabled office connection; it never deletes the local draft or automatically discovers, tests, approves or enables tools.</p><label className="managed-check"><input type="checkbox" checked={migrationConsent} onChange={e => setMigrationConsent(e.target.checked)} />I choose to review and migrate a selected draft to this office</label>{drafts.drafts.map(d => {
        const custom = d.type === 'custom' ? d.configuration : null, provider = d.type === 'catalog' ? s.providers.find(p => p.id === d.catalogId) : undefined
        const existing = s.connections.filter(c => custom ? c.name === custom.name && currentConfig(c).base_url.replace(/\/$/, '') === custom.endpoint.replace(/\/$/, '') : provider?.handler_id && currentConfig(c).handler_id === provider.handler_id)
        return <article className="managed-tool" key={d.id}><h4>{custom?.name ?? provider?.name ?? (d.type === 'catalog' ? d.catalogId : '')}</h4><p>Local ID {d.id} · not a backend identity</p>{existing.map(c => <button key={c.id} className="plugin-secondary" onClick={() => setSelected(c.id)}>Inspect existing {c.name}</button>)}<button className="plugin-secondary" disabled={!admin || s.busy || !migrationConsent || (!custom && !provider?.implemented)} onClick={() => migrate(d)}>Review migration</button>{!custom && !provider?.implemented && <p>No supported backend provider template; local draft retained.</p>}</article>
      })}<button className="plugin-secondary" onClick={() => setLocalMode(true)}>Edit local drafts</button></section>}
      <footer className="plugins-catalog-footer">Backend-confirmed state only. <span>No health probe, discovery, approval, activation or credential migration occurs automatically. Explicit skill workflows are managed on Skills. Monitoring and Outreach remain local drafts.</span></footer>
    </div></main>
    {selected && s.connections.find(c => c.id === selected) && !form && <ManagedConnectionDetails key={selected} connection={s.connections.find(c => c.id === selected)!} onClose={() => setSelected(null)} />}
    {form && <ConnectionEditor kind={form.kind} initial={form.initial} onClose={() => setForm(null)} onCreated={id => setSelected(id)} />}
  </div>
}
