import { useEffect, useMemo, useState } from 'react'
import { Check, ChevronDown, ChevronRight, ListFilter, MoreHorizontal, PanelLeftClose, PanelLeftOpen, Plus, Radio, Search, X, Globe2 } from 'lucide-react'
import { entriesFor, usePlugins } from '../../features/plugins/store'
import { availabilityLabels, categoryLabels } from '../../features/plugins/types'
import type { PluginDraft, PluginEntry, PluginSource } from '../../features/plugins/types'
import { PluginSocketIcon, ProviderIcon } from './PluginIcon'
import { PluginForm } from './PluginForm'
import { PluginDetails } from './PluginDetails'
import { ManagedPluginsPage } from './ManagedPluginsPage'

export default function PluginsPage() {
  return import.meta.env.VITE_API_MODE === 'http' ? <ManagedPluginsPage local={<LocalPluginsPage />} /> : <LocalPluginsPage />
}
function LocalPluginsPage() {
  const s = usePlugins(), { load, notice, dismissNotice } = s
  const [query, setQuery] = useState(''), [source, setSource] = useState<'all' | PluginSource>('all'), [addOpen, setAddOpen] = useState(false), [menu, setMenu] = useState<string | null>(null)
  const [sidebarOpen, setSidebarOpen] = useState(true), [mobileSidebar, setMobileSidebar] = useState(false), [selectedId, setSelectedId] = useState<string | null>(null)
  const [form, setForm] = useState<{ kind: 'mcp' | 'rest'; existing?: PluginDraft } | null>(null), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  useEffect(() => { void load() }, [load])
  useEffect(() => { if (!notice) return; const timer = setTimeout(dismissNotice, 5500); return () => clearTimeout(timer) }, [notice, dismissNotice])
  useEffect(() => {
    if (!mobileSidebar) return
    const previous = document.activeElement as HTMLElement | null, main = document.querySelector<HTMLElement>('.plugins-main')
    if (main) main.inert = true
    const controls = () => Array.from(document.querySelectorAll<HTMLElement>('.plugins-secondary.is-mobile-open button:not(:disabled)')).filter(el => getComputedStyle(el).display !== 'none')
    controls()[0]?.focus()
    const trap = (event: KeyboardEvent) => { if (event.key !== 'Tab') return; const items = controls(), first = items[0], last = items.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() } }
    document.addEventListener('keydown', trap)
    return () => { document.removeEventListener('keydown', trap); if (main) main.inert = false; if (previous?.isConnected) previous.focus() }
  }, [mobileSidebar])
  useEffect(() => {
    if (!addOpen && !menu && !mobileSidebar) return
    const click = (event: PointerEvent) => { if (!(event.target as Element).closest('[data-plugin-menu]')) { setAddOpen(false); setMenu(null) } }
    const key = (event: KeyboardEvent) => { if (event.key === 'Escape') { setAddOpen(false); setMenu(null); setMobileSidebar(false) } }
    document.addEventListener('pointerdown', click); document.addEventListener('keydown', key)
    return () => { document.removeEventListener('pointerdown', click); document.removeEventListener('keydown', key) }
  }, [addOpen, menu, mobileSidebar])
  const entries = useMemo(() => entriesFor(s.catalog, s.drafts), [s.catalog, s.drafts]), installed = entries.filter(e => e.draft)
  const selected = entries.find(e => e.id === selectedId)
  const filtered = entries.filter(e => (source === 'all' || source === e.source) && `${e.name} ${e.description} ${categoryLabels[e.category]}`.toLowerCase().includes(query.trim().toLowerCase()))
  const categories = Object.keys(categoryLabels) as Array<keyof typeof categoryLabels>
  const openDetails = (id: string) => { setSelectedId(id); setError(null); setMenu(null); setMobileSidebar(false) }
  const edit = (entry: PluginEntry) => { if (entry.draft?.type !== 'custom') return; setForm({ kind: entry.draft.configuration.kind, existing: entry.draft }); setSelectedId(null); setMenu(null); setError(null) }
  const add = async (entry: PluginEntry) => {
    if (busy) return; setBusy(true); setError(null)
    try { await s.addCatalog(entry.id); openDetails(entry.id) }
    catch { setError('The draft could not be saved. Check local storage permissions and the provider’s setup availability.') }
    finally { setBusy(false) }
  }
  const remove = async (entry: PluginEntry) => {
    if (!entry.draft || busy) return; setBusy(true); setError(null)
    try { await s.removeDraft(entry.draft.id); setSelectedId(null); setMenu(null) }
    catch { setError('The local draft could not be removed. Check browser storage permissions and try again.') }
    finally { setBusy(false) }
  }
  const openForm = (kind: 'mcp' | 'rest') => { setForm({ kind }); setAddOpen(false); setSelectedId(null); setError(null) }
  return <div className="plugins-page plugins-theme">
    {mobileSidebar && <button className="plugin-sidebar-backdrop" aria-label="Close installed drafts" onClick={() => setMobileSidebar(false)} />}
    <aside className={`plugins-secondary ${sidebarOpen ? '' : 'is-collapsed'} ${mobileSidebar ? 'is-mobile-open' : ''}`} aria-label="Plugin navigation">
      <div className="customize-heading"><span>Customize</span><button className="plugin-desktop-collapse" aria-label="Collapse plugin sidebar" onClick={() => setSidebarOpen(false)}><PanelLeftClose size={17} /></button><button className="plugin-mobile-close" aria-label="Close installed drafts" onClick={() => setMobileSidebar(false)}><X size={19} /></button></div>
      <div className="customize-navigation"><button className="selected" onClick={() => { setSource('all'); setQuery(''); setMobileSidebar(false) }}><PluginSocketIcon size={17} />Plugins</button></div>
      <div className="installed-heading"><h2>Installed</h2><span>{installed.length}</span></div><p className="installed-local-note">Local drafts · not connected</p>
      {!installed.length ? <div className="installed-empty"><PluginSocketIcon size={24} /><p>No plugins saved yet.</p><span>Add a draft from the catalog or bring your own connection.</span></div> : <div className="installed-plugin-list">{installed.map(entry => <button key={entry.id} onClick={() => openDetails(entry.id)}><ProviderIcon id={entry.id} category={entry.category} /><span><strong>{entry.name}</strong><small>Saved locally</small></span></button>)}</div>}
      <div className="plugins-secondary-footer"><span className="local-state-dot" /><span>Configurations stay on this device.<br />No services are connected.</span></div>
    </aside>
    <main className="plugins-main" aria-label="Plugins workspace">
      <div className="plugins-content">
        <header className="plugins-header"><div className="plugins-heading-group"><div className="plugin-page-kicker">AGRILO CUSTOMIZE</div><div className="plugins-title-row">{!sidebarOpen && <button className="plugin-desktop-collapse" aria-label="Open plugin sidebar" onClick={() => setSidebarOpen(true)}><PanelLeftOpen size={20} /></button>}<h1>Plugins</h1><button className="plugin-installed-button" aria-label="Open installed drafts" onClick={() => setMobileSidebar(true)}><ListFilter size={19} /></button></div><p>Bring agricultural tools into your field workspace.</p></div><div className="plugins-header-actions"><label className="plugin-search"><Search size={16} /><input aria-label="Search plugins" value={query} onChange={e => setQuery(e.target.value)} placeholder="Search plugins" /></label><div className="plugin-add-wrapper" data-plugin-menu><button className="plugin-add-button" aria-label="Add plugin" aria-expanded={addOpen} aria-haspopup="menu" onClick={() => setAddOpen(!addOpen)}>Add <ChevronDown size={15} /></button>{addOpen && <div className="plugin-menu add-menu" role="menu"><button role="menuitem" onClick={() => openForm('mcp')}><Radio size={18} /><span><strong>Add MCP server</strong><small>Save an HTTP server configuration</small></span></button><button role="menuitem" onClick={() => openForm('rest')}><Globe2 size={18} /><span><strong>Add API plugin</strong><small>Save a REST API configuration</small></span></button></div>}</div></div></header>
        <div className="plugin-filter-row" aria-label="Plugin sources">{([{ id: 'all', label: 'All' }, { id: 'built_in', label: 'Built-in' }, { id: 'office', label: 'Office' }, { id: 'custom', label: 'Custom' }] as const).map(filter => <button key={filter.id} aria-pressed={source === filter.id} className={source === filter.id ? 'selected' : ''} onClick={() => setSource(filter.id)}>{filter.label}</button>)}<span className="plugin-local-badge"><span />Local drafts</span></div>
        <p className="plugins-prototype-note">Explore the catalog and save draft configurations. Connection setup and administrator review will be available in a later phase.</p>
        {s.warning && <div className="plugin-page-warning" role="status">{s.warning}</div>}{error && !selected && <div className="plugin-page-warning" role="alert">{error}</div>}
        {s.loading && <div className="plugins-loading" role="status">Reading local configurations…</div>}
        {!s.loading && !filtered.length && <div className="plugin-empty-state"><Search size={27} /><h2>{source === 'office' ? 'An office catalog, when you’re ready.' : query ? 'No matching plugins' : source === 'custom' ? 'Your own connections belong here.' : 'No plugins to show'}</h2><p>{source === 'office' ? 'Office-specific integrations require an authenticated backend. Your local drafts do not belong to an office yet.' : query ? 'Try another name, category, or description.' : 'Choose Add to save an MCP server or API plugin configuration.'}</p>{query && <button className="plugin-secondary" onClick={() => setQuery('')}>Clear search</button>}</div>}
        {categories.map(category => { const items = filtered.filter(entry => entry.category === category); if (!items.length) return null; return <section className="plugin-category" key={category}><h2>{categoryLabels[category]}<ChevronRight size={15} /><span>{items.length}</span></h2><div className="plugin-catalog-grid">{items.map(entry => <article className="plugin-row" key={entry.id}><button className="plugin-row-main" aria-label={`View ${entry.name} details`} onClick={() => openDetails(entry.id)}><ProviderIcon id={entry.id} category={entry.category} /><span className="plugin-row-copy"><strong>{entry.name}</strong><span>{entry.description}</span><small className={entry.draft ? 'saved' : ''}>{entry.draft ? <><Check size={10} />Saved locally · Not connected</> : availabilityLabels[entry.availability]}</small></span></button><div className="plugin-row-action" data-plugin-menu>{entry.draft ? <><button aria-label={`Manage ${entry.name}`} aria-expanded={menu === entry.id} aria-haspopup="menu" onClick={() => setMenu(menu === entry.id ? null : entry.id)}><MoreHorizontal size={20} /></button>{menu === entry.id && <div className="plugin-menu row-menu" role="menu"><button role="menuitem" onClick={() => openDetails(entry.id)}>View details</button>{entry.draft.type === 'custom' && <button role="menuitem" onClick={() => edit(entry)}>Edit configuration</button>}<button role="menuitem" className="menu-danger" disabled={busy} onClick={() => { void remove(entry) }}>Remove local draft</button></div>}</> : <button disabled={busy || !s.loaded || entry.availability === 'unavailable'} aria-label={`Save ${entry.name} draft`} title={entry.availability === 'unavailable' ? 'Setup unavailable. Open details for requirements.' : 'Save a local draft'} onClick={() => { void add(entry) }}><Plus size={21} /></button>}</div></article>)}</div></section> })}
        <footer className="plugins-catalog-footer">Catalog snapshot · 16 November 2026 <span>Built-in availability is separate from connection health and office approval.</span></footer>
      </div>
    </main>
    {selected && !form && <PluginDetails key={selected.id} entry={selected} busy={busy} error={error} onAdd={() => { void add(selected) }} onEdit={() => edit(selected)} onRemove={() => { void remove(selected) }} onClose={() => { setSelectedId(null); setError(null) }} />}
    {form && <PluginForm key={form.existing?.id ?? form.kind} kind={form.kind} existing={form.existing} onClose={() => setForm(null)} onSaved={id => { setForm(null); setSelectedId(id); setError(null) }} />}
    {notice && <div className="plugin-toast" role="status"><span>{notice}</span><button aria-label="Dismiss plugin notification" onClick={dismissNotice}><X size={16} /></button></div>}
  </div>
}
