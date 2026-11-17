import { lazy, Suspense, useState } from 'react'
import { LogOut, Maximize2, Minimize2, RefreshCw, Sprout } from 'lucide-react'
import { useHome, liveMapBinding } from '../state/useHome'
import { investigationBlock } from '../state/home-store'
import { InvestigationControls } from '../components/home/InvestigationControls'
import { InvestigationResults } from '../components/home/InvestigationResults'
import { CoordinateWidget, type Coordinate } from '../components/map/CoordinateWidget'
import '../styles/home-live.css'

const FieldOpsMap = lazy(() => import('../components/map/FieldOpsMap'))
function HomeExperience({ active }: { active: boolean }) {
  const s = useHome(), [phone, setPhone] = useState(''), [password, setPassword] = useState(''), [question, setQuestion] = useState(''), [controls, setControls] = useState<HTMLDivElement | null>(null), [coordinate, setCoordinate] = useState<Coordinate | null>(null), [expanded, setExpanded] = useState(false)
  const block = investigationBlock(s)
  if (s.session !== 'ready') return <main className="live-login"><Sprout size={36} /><h1>AgriLo FieldOps</h1><p>Sign in to the agricultural backend with an existing officer account.</p><p className="live-mode-label">Live backend mode · no automatic demo fallback</p><form onSubmit={e => { e.preventDefault(); const secret = password; setPassword(''); void s.login(phone, secret) }}><label>Phone number<input type="tel" autoComplete="username" value={phone} onChange={e => setPhone(e.target.value)} required /></label><label>Password<input type="password" autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)} required minLength={8} /></label><button className="primary" disabled={s.session === 'loading'}>{s.session === 'loading' ? 'Signing in…' : 'Sign in'}</button></form>{s.error && <p role="alert">{s.error}</p>}<p>No provider API key belongs in this form. Sessions stay in memory and end on page reload.</p></main>
  return <div className={'agrosphere-app live-home' + (expanded ? ' map-expanded' : '')}>
    <aside className="selection-sidebar live-map-panel" aria-label="Authorized farm map" tabIndex={0}>
      <div className="brand-header"><Sprout size={27} /><div><h1>AgriLo FieldOps</h1><p>{s.context?.office_name}</p></div></div>
      <div className="sidebar-meta"><span className="live-mode-label">Live backend</span><button className="map-layout-toggle" aria-pressed={expanded} onClick={() => setExpanded(!expanded)}>{expanded ? <Minimize2 size={14} /> : <Maximize2 size={14} />}{expanded ? 'Compact map' : 'Expand map'}</button></div>
      <div className="map-card"><Suspense fallback={<p>Opening map…</p>}><FieldOpsMap active={active} binding={liveMapBinding} controlsTarget={controls} coordinate={coordinate} onCoordinate={setCoordinate} /></Suspense></div>
      <div ref={setControls} className="map-controls-host" />
      <CoordinateWidget binding={liveMapBinding} coordinate={coordinate} onCoordinate={setCoordinate} />
      <p className="tiny">Coordinates move the map only. Tools use authorized farm records. The rectangle filters authorized points locally; server spatial intersection is unavailable.</p>
      <label className="live-search">Filter farms<input value={s.search} placeholder="Name, ID or recorded crop" onChange={e => s.setSearch(e.target.value)} /></label>
      <p>{s.farms.length} visible · {s.selectedIds.length} selected</p>
      <div className="live-farm-list">{s.farms.map(farm => <label key={farm.id}><input type="checkbox" checked={s.selectedIds.includes(farm.id)} onChange={() => s.selectFarm(farm.id)} /><span><strong>{farm.displayName}</strong><small>{farm.currentCrop} · {s.plots.find(p => p.id === farm.id)?.synthetic ? 'Synthetic registered context' : 'Registered farm'} · risk not assessed</small></span></label>)}</div>
      {!s.farms.length && <p>No authorized farm records match this filter.</p>}
    </aside>
    <main className="report-main live-workspace" aria-label="Live officer companion">
      <header className="report-topbar"><div><strong>Officer companion</strong><small>{s.context?.role} · {s.context?.model.provider} / {s.context?.model.model}</small></div><div className="live-actions"><button onClick={() => void s.reload()} aria-label="Refresh backend availability"><RefreshCw size={16} />Refresh</button><button onClick={s.logout}><LogOut size={16} />Sign out</button></div></header>
      <div className="live-workspace-body" role="region" aria-label="Farm context and investigation results" tabIndex={0}>
      <div className="live-banner">Provider results remain distinct from farm context. No risk rating, crop recommendation, satellite overlay or advisory release is inferred from the map.</div>
      {s.selectedIds.length > 0 && <details className="live-details"><summary>Selected farm details ({s.selectedIds.length})</summary>{s.plots.filter(p => s.selectedIds.includes(p.id)).map(p => <article key={p.id}><h3>{p.name}</h3><p>{p.id} · {p.area} {p.area_unit} · {p.crop ?? 'Crop not recorded'} · planting date: {p.planting_date ?? 'Not recorded'}</p><p>WGS84 longitude {p.longitude}, latitude {p.latitude}. {p.synthetic ? 'Synthetic registered context; not a validated real farm.' : 'Authorized registered farm point; no boundary is recorded.'}</p></article>)}</details>}
      <InvestigationControls /><InvestigationResults />
      {s.error && <p role="alert">{s.error}</p>}{s.toast && <p role="status" className="live-toast">{s.toast}<button onClick={() => s.notify(null)}>Dismiss</button></p>}
      </div>
      <form className="live-question" onSubmit={e => { e.preventDefault(); const text = question; setQuestion(''); void s.submit(text) }}><label htmlFor="live-question">Agricultural question</label><textarea id="live-question" maxLength={2000} minLength={3} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Investigate this farm's soil, rainfall history and available weather forecast. Explain limitations and what else should be checked." /><button className="primary" disabled={!!block || !!s.activeId || question.trim().length < 3}>{s.activeId ? 'Investigation in progress…' : 'Start investigation'}</button></form>
    </main>
  </div>
}

export default function LiveHomeWorkspace({ active }: { active: boolean }) {
  const s = useHome()
  return <HomeExperience key={s.conversationId} active={active} />
}
