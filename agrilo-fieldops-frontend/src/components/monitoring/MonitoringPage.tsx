import { useEffect, useState } from 'react'
import { ArrowUpRight, ChevronRight, CirclePause, History, LayoutList, Leaf, ListFilter, PanelLeftClose, Plus, Radar, Search, X } from 'lucide-react'
import { newMonitorInput, templates } from '../../features/monitoring/catalog'
import { monitoringService, useMonitoring } from '../../features/monitoring/store'
import { categoryLabels, scheduleSentence } from '../../features/monitoring/types'
import type { MonitorDefinition, MonitorInput } from '../../features/monitoring/types'
import { sampleMonitor, sampleScenarios } from '../../features/monitoring/fixtures'
import type { SampleScenario } from '../../features/monitoring/fixtures'
import { MonitorWizard } from './MonitorWizard'
import { MonitorDetail } from './MonitorDetail'
import { MonitorSymbol, QuietState } from './MonitoringUi'
import { MonitoringHistory } from './MonitoringHistory'
function currentRoute() { return window.location.hash.replace(/^#monitoring\/?/, '') }
export default function MonitoringPage() {
  const state = useMonitoring(), { load, notice, notify } = state
  const [route, setRoute] = useState(currentRoute), [query, setQuery] = useState(''), [filter, setFilter] = useState('all'), [sort, setSort] = useState('recent')
  const [sidebar, setSidebar] = useState(true), [drawer, setDrawer] = useState(false), [sampleHistory, setSampleHistory] = useState(false)
  const [form, setForm] = useState<{ existing?: MonitorDefinition; initial?: MonitorInput } | null>(null)
  useEffect(() => { void load() }, [load])
  useEffect(() => { const change = () => { setRoute(currentRoute()); setDrawer(false) }; window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change) }, [])
  useEffect(() => { if (!notice) return; const timer = setTimeout(() => notify(null), 6000); return () => clearTimeout(timer) }, [notice, notify])
  useEffect(() => { const resize = () => { if (window.innerWidth > 1050) setDrawer(false) }; window.addEventListener('resize', resize); return () => window.removeEventListener('resize', resize) }, [])
  useEffect(() => {
    if (!drawer) return
    const previous = document.activeElement as HTMLElement | null, main = document.querySelector<HTMLElement>('.monitoring-main')
    if (main) main.inert = true
    const controls = () => Array.from(document.querySelectorAll<HTMLElement>('.monitoring-sidebar.is-open button,.monitoring-sidebar.is-open a,.monitoring-sidebar.is-open input,.monitoring-sidebar.is-open select')).filter(el => !el.hasAttribute('disabled') && el.getClientRects().length)
    controls()[0]?.focus()
    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawer(false)
      if (event.key === 'Tab') { const items = controls(), first = items[0], last = items.at(-1); if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() } else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() } }
    }
    document.addEventListener('keydown', key); return () => { document.removeEventListener('keydown', key); if (main) main.inert = false; if (previous?.isConnected) previous.focus() }
  }, [drawer])
  const showCategory = (value: string) => { setFilter(value); window.location.hash = 'monitoring'; setDrawer(false) }
  const monitors = state.monitors.filter(m => (!query || (m.input.name + ' ' + m.input.description).toLowerCase().includes(query.toLowerCase())) && (filter === 'all' || filter === 'paused' ? filter !== 'paused' || m.configurationStatus === 'paused' : m.input.category === filter)).sort((a, b) => sort === 'name' ? a.input.name.localeCompare(b.input.name) : b.updatedAt.localeCompare(a.updatedAt))
  const scenario = route.startsWith('demo/') && sampleScenarios.some(s => s.id === route.slice(5)) ? route.slice(5) as SampleScenario : undefined
  const monitor = scenario ? sampleMonitor(scenario) : state.monitors.find(m => m.id === route)
  const isHistory = route === 'history', isList = !route
  const create = (templateId: MonitorInput['templateId'] = 'custom') => { setForm({ initial: newMonitorInput(templateId) }); setDrawer(false) }
  const edit = (value: MonitorDefinition, copy = false) => { setForm(copy ? { initial: value.input } : { existing: value }); setDrawer(false) }
  return <div className="monitoring-page plugins-theme">
    {drawer && <button className="monitor-sidebar-backdrop" aria-label="Close monitoring sidebar" onClick={() => setDrawer(false)} />}
    <aside className={'monitoring-sidebar ' + (!sidebar ? 'is-collapsed ' : '') + (drawer ? 'is-open' : '')} aria-label="Monitoring navigation">
      <div className="monitor-sidebar-heading"><strong>Monitoring</strong><button className="monitor-collapse-desktop" aria-label="Collapse monitoring sidebar" onClick={() => setSidebar(false)}><PanelLeftClose size={17} /></button><button className="monitor-drawer-close" aria-label="Close monitoring sidebar" onClick={() => setDrawer(false)}><X size={18} /></button></div>
      <button className="monitor-new-action" onClick={() => create()}><Plus size={17} />New Monitor</button>
      <label className="monitor-sidebar-search"><Search size={14} /><input aria-label="Search monitors" value={query} placeholder="Search monitors" onChange={e => { setQuery(e.target.value); window.location.hash = 'monitoring' }} /></label>
      <nav className="monitor-category-nav" aria-label="Monitor categories">{[{ id: 'all', name: 'All Monitors', icon: LayoutList }, { id: 'environment', name: 'Environmental Monitoring', icon: Radar }, { id: 'crop_health', name: 'Crop Health', icon: Leaf }, { id: 'report', name: 'Reports', icon: History }, { id: 'paused', name: 'Paused', icon: CirclePause }].map(({ id, name, icon: Icon }) => <button key={id} className={isList && filter === id ? 'selected' : ''} onClick={() => showCategory(id)}><Icon size={16} /><span>{name}</span>{id === 'all' && <small>{state.monitors.length}</small>}</button>)}<a href="#monitoring/history" className={isHistory ? 'selected' : ''}><History size={16} />Monitoring History</a></nav>
      <div className="monitor-sidebar-list-title"><span>Local configurations</span><select aria-label="Sort monitors" value={sort} onChange={e => setSort(e.target.value)}><option value="recent">Recent</option><option value="name">Name</option></select></div>
      {!state.monitors.length && <p className="monitor-sidebar-empty">Your saved monitor drafts will appear here.</p>}
      <div className="monitor-sidebar-list">{monitors.map(m => <a key={m.id} href={'#monitoring/' + m.id} aria-current={route === m.id ? 'page' : undefined}><MonitorSymbol template={m.input.templateId} size={16} /><span><strong>{m.input.name}</strong><small>{m.configurationStatus === 'paused' ? 'Paused locally' : 'Draft · Saved locally'}</small></span></a>)}</div>
      <footer className="monitor-sidebar-footer"><span />Local configuration workspace<small>No scheduler or delivery connected.</small></footer>
    </aside>
    <main className="monitoring-main" aria-label="Monitoring workspace">
      <div className="monitoring-content"><header className="monitor-workspace-header"><div><button aria-label="Open monitoring sidebar" onClick={() => { setSidebar(true); setDrawer(window.matchMedia('(max-width: 1050px)').matches) }}><ListFilter size={18} /></button><span>AGRILO <ChevronRight size={12} /> MONITORING</span></div><span className="monitor-local-pill">Local prototype</span></header>
        {state.warning && <div className="monitor-errors" role="status">{state.warning}</div>}
        {state.loading && <QuietState title="Reading local configurations">Your browser’s saved monitor drafts are loading.</QuietState>}
        {isHistory && <><div className="monitor-page-heading"><div><h1>Monitoring history</h1><p>No authenticated execution history is connected.</p></div><button className="plugin-secondary" onClick={() => setSampleHistory(!sampleHistory)}>{sampleHistory ? 'Hide sample history' : 'Show sample history'}</button></div><MonitoringHistory runs={sampleHistory ? sampleScenarios.flatMap(s => { const m = sampleMonitor(s.id); return monitoringService.history(m.input, m.id, m.version) }) : []} /></>}
        {monitor && <MonitorDetail key={monitor.id} monitor={monitor} scenario={scenario} onEdit={edit} />}
        {!isList && !isHistory && !monitor && !state.loading && <QuietState title="Monitor configuration not found">It may have been deleted or is not saved on this device. <a href="#monitoring">Return to all monitors</a>.</QuietState>}
        {isList && !state.loading && <>
          {!state.monitors.length && !query ? <section className="monitor-welcome"><span className="monitor-welcome-symbol"><Radar size={31} strokeWidth={1.4} /></span><small>YOUR FIELDWORK, WITH FORESIGHT</small><h1>Put your farms under<br />intelligent monitoring</h1><p>Let AgriLo periodically analyze agricultural conditions, track crop observations, and prepare reports for your review.</p><button className="monitor-primary" onClick={() => create()}><Plus size={16} />Create Monitor</button><span className="monitor-welcome-note">Start with a local draft. Background execution comes later.</span></section> : <><div className="monitor-page-heading"><div><h1>{filter === 'all' ? 'Your monitors' : filter === 'paused' ? 'Paused configurations' : categoryLabels[filter as keyof typeof categoryLabels]}</h1><p>{state.monitors.length} saved locally · no active schedules</p></div><button className="monitor-primary" onClick={() => create()}><Plus size={15} />Create Monitor</button></div><div className="monitor-configuration-list">{monitors.map(m => <a href={'#monitoring/' + m.id} key={m.id}><span className="monitor-list-symbol"><MonitorSymbol template={m.input.templateId} /></span><div><h2>{m.input.name}</h2><p>{m.input.scope.farms.length} farms · {scheduleSentence(m.input.schedule)}</p><small>{m.input.rules.length} thresholds · {categoryLabels[m.input.category]}</small></div><span className="monitor-draft-badge">{m.configurationStatus === 'paused' ? 'Paused locally' : 'Draft'}</span><ArrowUpRight size={17} /></a>)}</div>{!monitors.length && <QuietState title="No matching configurations">Try another search or category.</QuietState>}</>}
          <section className="monitor-templates"><div className="monitor-section-heading"><div><h2>{state.monitors.length ? 'Start another monitor' : 'A good place to start'}</h2><p>Choose a template and make it fit your farms.</p></div></div><div className="monitor-template-grid">{templates.map(t => <button key={t.id} onClick={() => create(t.id)}><span><MonitorSymbol template={t.id} size={23} /></span><div><h3>{t.name}</h3><p>{t.description}</p><small>{t.frequency} <i />{t.capabilityIds.length ? t.capabilityIds.length + ' example capabilities' : 'Your configuration'}</small></div><Plus size={17} /></button>)}</div></section>
          <section className="monitor-scenario-section"><div><h2>Explore the workflow</h2><p>Clearly labeled synthetic examples. No live observations or background jobs.</p></div><div className="monitor-scenario-grid">{sampleScenarios.map(s => <a key={s.id} href={'#monitoring/demo/' + s.id}><strong>{s.name}<ArrowUpRight size={13} /></strong><span>{s.description}</span></a>)}</div></section>
        </>}
        <footer className="monitor-page-footer"><span>Officer control at every step.</span>Draft configurations, traceable evidence, and human review.</footer>
      </div>
    </main>
    {form && <MonitorWizard existing={form.existing} initial={form.initial} onClose={() => setForm(null)} onSaved={m => { setForm(null); window.location.hash = 'monitoring/' + m.id }} />}
    {notice && <div className="plugin-toast" role="status"><span>{notice}</span><button aria-label="Dismiss monitoring notification" onClick={() => notify(null)}><X size={16} /></button></div>}
  </div>
}
