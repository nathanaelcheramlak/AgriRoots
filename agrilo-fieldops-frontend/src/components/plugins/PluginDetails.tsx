import { useState } from 'react'
import { ExternalLink, Globe2, LockKeyhole, Pencil, Plus, Trash2 } from 'lucide-react'
import { LOCAL_STATUS, availabilityLabels, categoryLabels } from '../../features/plugins/types'
import type { PluginEntry } from '../../features/plugins/types'
import { ProviderIcon } from './PluginIcon'
import { PluginModal } from './PluginModal'
import { dateTime } from '../../lib/format'

export function PluginDetails({ entry, busy, error, onAdd, onEdit, onRemove, onClose }: { entry: PluginEntry; busy: boolean; error: string | null; onAdd: () => void; onEdit: () => void; onRemove: () => void; onClose: () => void }) {
  const [tab, setTab] = useState('overview'), custom = entry.draft?.type === 'custom' ? entry.draft.configuration : null
  const tabs = [{ id: 'overview', label: 'Overview' }, { id: 'configuration', label: 'Configuration' }, { id: 'tools', label: 'Tools & operations' }, { id: 'testing', label: 'Testing & approval' }]
  return <PluginModal title="Plugin details" wide onClose={onClose}>
    <div className="plugin-detail-identity"><ProviderIcon id={entry.id} category={entry.category} /><div><h3>{entry.name}</h3><p>{entry.description}</p></div></div>
    <div className="plugin-detail-tags"><span>{entry.source === 'built_in' ? 'Built-in provider' : entry.source === 'office' ? 'Office integration' : 'Custom configuration'}</span>{entry.draft && <span>Saved locally</span>}<span>Not connected</span></div>
    <div className="plugin-detail-tabs" role="tablist" aria-label="Plugin detail sections">{tabs.map(t => <button key={t.id} role="tab" aria-selected={tab === t.id} aria-controls={`plugin-section-${t.id}`} id={`plugin-detail-${t.id}`} className={tab === t.id ? 'selected' : ''} onClick={() => setTab(t.id)}>{t.label}</button>)}</div>
    <div className="plugin-detail-content" role="tabpanel" id={`plugin-section-${tab}`} aria-labelledby={`plugin-detail-${tab}`}>
      {tab === 'overview' && <>
        <dl className="plugin-status-grid"><div><dt>Catalog availability</dt><dd>{entry.catalog ? availabilityLabels[entry.availability] : 'Custom draft'}</dd></div><div><dt>Local installation</dt><dd>{entry.draft ? LOCAL_STATUS.installation : 'Not saved'}</dd></div><div><dt>Connection health</dt><dd>{LOCAL_STATUS.health}</dd></div><div><dt>Administrative approval</dt><dd>{LOCAL_STATUS.approval}</dd></div><div><dt>Runtime enablement</dt><dd>{LOCAL_STATUS.enablement}</dd></div><div><dt>Ownership</dt><dd>{entry.draft ? 'This device · no office assigned' : 'System catalog'}</dd></div></dl>
        <section className="plugin-requirements"><h4>Setup requirements</h4><p>{entry.requirement}</p></section>
        <div className="plugin-metadata"><span>{categoryLabels[entry.category]}</span>{entry.catalog && <span>Catalog snapshot · {dateTime(entry.catalog.snapshotDate)} EAT</span>}{entry.draft && <span>Updated · {dateTime(entry.draft.updatedAt)} EAT</span>}</div>
        {entry.catalog && <a className="plugin-docs-link" href={entry.catalog.docsUrl} target="_blank" rel="noreferrer">Provider documentation <ExternalLink size={13} /></a>}
      </>}
      {tab === 'configuration' && <>
        {custom ? <><dl className="plugin-config-summary"><div><dt>Connection type</dt><dd>{custom.kind === 'mcp' ? 'MCP over HTTP' : 'REST API'}</dd></div><div><dt>{custom.kind === 'mcp' ? 'Server URL' : 'Base URL'}</dt><dd className="plugin-endpoint-text">{custom.endpoint}</dd></div><div><dt>Authentication method</dt><dd>{custom.authMethod === 'api_key' ? 'API key' : custom.authMethod === 'bearer' ? 'Bearer token' : 'None'}</dd></div>{custom.apiKeyHeader && <div><dt>Header name only</dt><dd>{custom.apiKeyHeader}</dd></div>}</dl><button className="plugin-secondary" onClick={onEdit}><Pencil size={14} />Edit configuration</button></> : <div className="plugin-future-state"><Globe2 size={28} /><h4>{entry.draft ? 'Provider draft saved on this device' : 'Provider configuration'}</h4><p>Connection setup will be available in a later phase. Saving a draft keeps a reference on this device without contacting the provider or setting up authentication.</p></div>}
        <div className="plugin-credential-note"><LockKeyhole size={16} /><p>No credential values are collected or saved. Authentication will be configured through the backend.</p></div>
      </>}
      {tab === 'tools' && <div className="plugin-future-state"><Globe2 size={30} /><h4>No tools or operations registered</h4><p>MCP discovery and REST operation definitions need a connected backend. Input/output schemas, request mappings, and response mappings will appear here when that workflow is available.</p><div className="plugin-disabled-actions"><button disabled className="plugin-secondary" title="A connected backend is required">Discover MCP tools</button><button disabled className="plugin-secondary" title="A connected backend is required">Add REST operation</button></div><span>Upcoming · No discovery or tool call has been made.</span></div>}
      {tab === 'testing' && <div className="plugin-future-state"><LockKeyhole size={30} /><h4>Testing and review come after connection setup.</h4><p>A saved draft has no test evidence, approval or permission to run. Future reviews will refer to the exact backend configuration and tool versions.</p><dl className="plugin-status-grid"><div><dt>Connection health</dt><dd>Not connected</dd></div><div><dt>Approval</dt><dd>Not submitted</dd></div><div><dt>Enablement</dt><dd>Not enabled</dd></div></dl><div className="plugin-disabled-actions"><button disabled className="plugin-secondary">Test connection</button><button disabled className="plugin-secondary">Submit for approval</button><button disabled className="plugin-secondary">Enable integration</button></div><span>Upcoming · Backend evidence required.</span></div>}
    </div>
    {error && <p className="plugin-detail-error" role="alert">{error}</p>}
    <footer className="plugin-detail-actions">{entry.draft ? <><button className="plugin-danger" onClick={onRemove} disabled={busy}><Trash2 size={14} />Remove local draft</button>{custom && <button className="plugin-secondary" onClick={onEdit}><Pencil size={14} />Edit</button>}</> : <button className="plugin-primary" onClick={onAdd} disabled={busy || entry.availability === 'unavailable'}><Plus size={15} />{busy ? 'Saving…' : entry.availability === 'unavailable' ? 'Setup unavailable' : 'Save local draft'}</button>}<button className="plugin-secondary" onClick={onClose}>Done</button></footer>
  </PluginModal>
}
