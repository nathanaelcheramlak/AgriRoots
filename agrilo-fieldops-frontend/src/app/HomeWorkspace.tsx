// Layout and CSS modules adapted from Leoul39/AgroSphere (MIT).
import { lazy, Suspense, useEffect, useState } from 'react'
import { ClipboardList, HelpCircle, LayoutDashboard, Leaf, Maximize2, MessageSquare, Minimize2, Sprout, X } from 'lucide-react'
import { useFieldOps } from '../state/useFieldOps'
import { visibleFarms } from '../state/store'
import { OverviewTab } from '../components/sidebar/OverviewTab'
import { FarmsTab } from '../components/sidebar/FarmsTab'
import { AssistantTab } from '../components/sidebar/AssistantTab'
import { AdvisoriesTab } from '../components/sidebar/AdvisoriesTab'
import { CoordinateWidget } from '../components/map/CoordinateWidget'
import type { Coordinate } from '../components/map/CoordinateWidget'
import { prepareHomeOutreach } from '../features/outreach/transfer'
import styles from './App.module.css'
const LiveHomeWorkspace = lazy(() => import('./LiveHomeWorkspace'))
const FieldOpsMap = lazy(() => import('../components/map/FieldOpsMap'))
const tabs = [{ id: 'overview', label: 'Overview', icon: LayoutDashboard }, { id: 'farms', label: 'Farms', icon: Sprout }, { id: 'assistant', label: 'Assistant', icon: MessageSquare }, { id: 'advisories', label: 'Advisories', icon: ClipboardList }] as const
const phaseText = { idle: 'Ready to explore', selecting: 'Selecting area', loading_farms: 'Discovering farms', screening: 'Screening demo records', preparing_candidates: 'Preparing candidates', completed: 'Screening complete', partial: 'Screening complete · partial data', failed: 'Screening failed' }
function DemoHomeWorkspace({ active }: { active: boolean }) {
  const s = useFieldOps(), [help, setHelp] = useState(false), [coordinate, setCoordinate] = useState<Coordinate | null>(null), [controlsTarget, setControlsTarget] = useState<HTMLDivElement | null>(null)
  const [mapExpanded, setMapExpanded] = useState(false)
  const busy = ['loading_farms', 'screening', 'preparing_candidates'].includes(s.phase)
  const activeFilter = Object.values(s.filters).some(Boolean), { toast, notify } = s
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => notify(null), 5500); return () => clearTimeout(timer) }, [toast, notify])
  useEffect(() => {
    if (!help || !active) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { setHelp(false); return }
      if (event.key !== 'Tab') return
      const controls = document.querySelectorAll<HTMLButtonElement>('.help-modal button'), first = controls[0], last = controls[controls.length - 1]
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus() }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus() }
    }
    window.addEventListener('keydown', onKey); return () => window.removeEventListener('keydown', onKey)
  }, [help, active])
  return <div className={`${styles.appContainer} agrosphere-app${mapExpanded ? ' map-expanded' : ''}`}>
    <aside id="field-map-pane" className={`${styles.sidebar} selection-sidebar`} aria-label="Map and area selection">
      <a className={`${styles.brandHeader} brand-header`} href="#home" aria-label="AgriLo FieldOps home"><img src="/fieldops-mark.svg" alt="" className={`${styles.logo} brand-mark`} /><div className={styles.brandTextContainer}><h1 className={`${styles.brandTitle} brand-title`}><span className={styles.textMain}>AgriLo</span><span className={styles.textGreen}> FieldOps</span></h1><p className={`${styles.tagline} brand-tagline`}>Data. Context. Considered decisions.</p></div></a>
      <div className="sidebar-meta"><span className="demo-badge"><i />{s.mode === 'mock' ? 'Synthetic demo data' : 'Independent backend'}</span><span>Adama · Ethiopia</span></div>
      <div className="map-view-header"><span>FIELD MAP</span><button className="map-layout-toggle" aria-label={mapExpanded ? 'Return to compact map' : 'Expand map to half screen'} aria-pressed={mapExpanded} aria-controls="field-map-pane officer-workspace" onClick={() => setMapExpanded(value => !value)}>{mapExpanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}<span>{mapExpanded ? 'Compact map' : 'Expand map'}</span></button></div>
      <div className={`${styles.mapCard} map-card`}><Suspense fallback={<div className="map-loading">Preparing Leaflet map…</div>}><FieldOpsMap active={active} controlsTarget={controlsTarget} coordinate={coordinate} onCoordinate={setCoordinate} /></Suspense></div>
      <div ref={setControlsTarget} className="map-controls-host" />
      <p className={styles.mapHintText}>{s.selection ? 'Your rectangle defines the screening area.' : 'Draw a rectangle to screen farms. Click the map to choose a coordinate.'}</p>
      <CoordinateWidget coordinate={coordinate} onCoordinate={setCoordinate} />
      <div className="map-legend" aria-label="Farm priority legend">{(['high', 'moderate', 'low', 'unknown'] as const).map(r => <span key={r}><i className={r} />{r[0].toUpperCase() + r.slice(1)}</span>)}</div>
      <div className="sidebar-note"><Leaf size={15} /><p>Independent frontend test.<br />Farm evidence and crop candidates are synthetic.</p></div>
      <button className="text-button sidebar-help" onClick={() => setHelp(true)}><HelpCircle size={15} />About this workspace</button>
    </aside>
    <main id="officer-workspace" className={`${styles.mainContent} report-main`} aria-label="Extension officer workspace">
      <header className="report-topbar"><div className="workspace-label"><span className="status-dot" />EXTENSION WORKSPACE</div><div className="officer"><span>DO</span><div>Demo officer<small>Local review only</small></div></div></header>
      <div className="report-navigation" role="tablist" aria-label="Field operations tabs">{tabs.map(({ id, label, icon: Icon }) => <button role="tab" aria-label={label} aria-selected={s.tab === id} aria-controls={`panel-${id}`} id={`tab-${id}`} key={id} onClick={() => s.setTab(id)} className={s.tab === id ? 'active' : ''}><Icon size={17} /><span>{label}</span>{id === 'farms' && s.analysis && <i data-testid="metric-farms">{s.farms.length}</i>}{id === 'advisories' && s.drafts.length > 0 && <i>{s.drafts.length}</i>}</button>)}</div>
      <div className="analysis-status"><span className={busy ? 'status-indicator busy' : 'status-indicator'} /><span role="status">{phaseText[s.phase]}</span>{activeFilter && <button onClick={s.clearFilters}>Clear filters · {visibleFarms(s).length} visible</button>}<span className="status-right">{s.mode === 'mock' ? 'Demo screening' : 'Backend screening'}</span></div>
      {s.analysis && visibleFarms(s).length > 0 && <div className="home-outreach-action"><button onClick={() => { const farms = s.selectedFarmId ? s.farms.filter(f => f.id === s.selectedFarmId) : visibleFarms(s); void prepareHomeOutreach(farms, s.analysis!, s.mode === 'mock').catch(() => s.notify('The source could not be prepared. Check the evidence metadata and try again.')) }}><MessageSquare size={15} />Prepare Farmer Guidance</button><span>{s.selectedFarmId ? 'Selected farm · ' + s.selectedFarmId : visibleFarms(s).length + ' visible farms'} · source snapshot for officer review</span></div>}
      <section className={`main-report tab-${s.tab}`} role="tabpanel" id={`panel-${s.tab}`} aria-labelledby={`tab-${s.tab}`}>
        {s.tab === 'overview' && <OverviewTab />}{s.tab === 'farms' && <FarmsTab />}{s.tab === 'assistant' && <AssistantTab />}{s.tab === 'advisories' && <AdvisoriesTab />}
      </section>
    </main>
    {toast && <div className="toast" role="status"><span>{toast}</span><button aria-label="Dismiss notification" onClick={() => notify(null)}><X size={17} /></button></div>}
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="help-modal" role="dialog" aria-modal="true" aria-label="About this workspace" onClick={e => e.stopPropagation()}><button autoFocus className="close-modal" aria-label="Close help" onClick={() => setHelp(false)}><X size={20} /></button><Sprout size={32} /><h2>AgriLo FieldOps</h2><p>Frontend adapted from AgroSphere. This test is independent of AgriRoots and the API evaluation project.</p><ol><li>Draw a rectangle, choose Try demo area, or enter coordinates and an area width.</li><li>Review each farm, its evidence, and its illustrative crop candidates.</li><li>Use Assistant to filter the map. Prepare an advisory and record an officer review locally.</li></ol><p className="tiny">Satellite imagery is a visual basemap. Agricultural screening uses synthetic fixtures; satellite analytics and live agricultural integrations are unavailable.</p><a href="https://github.com/Leoul39/AgroSphere" target="_blank" rel="noreferrer">AgroSphere source · MIT license</a><button className="primary" onClick={() => setHelp(false)}>Continue exploring</button></section></div>}
  </div>
}

export default function HomeWorkspace({ active }: { active: boolean }) {
  return import.meta.env.VITE_API_MODE === 'http' ? <Suspense fallback={<p>Opening backend Home…</p>}><LiveHomeWorkspace active={active} /></Suspense> : <DemoHomeWorkspace active={active} />
}
