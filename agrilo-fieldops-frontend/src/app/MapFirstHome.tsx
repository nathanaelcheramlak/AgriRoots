import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { ArrowDown, Check, ChevronDown, LogOut, MessageSquare, Plus, RefreshCw, Sprout, SquareDashed, X } from 'lucide-react'
import type { MultiPolygon, Polygon } from 'geojson'
import { homeStore, useHome } from '../state/useHome'
import { investigationBlock } from '../state/home-store'
import { territoryStore, useTerritory } from '../features/territory/store'
import { bounds, center, contained, measuredArea, sharedArea } from '../features/territory/geometry'
import { mergeHomePlots, parsePlot, registryRequest, write } from '../features/territory/backend'
import { territorySchema, type Territory } from '../features/territory/types'
import { HomeApiError } from '../api/home-api'
import { InvestigationControls } from '../components/home/InvestigationControls'
import { InvestigationResults } from '../components/home/InvestigationResults'
import '../styles/home-live.css'
import '../styles/home-map-first.css'

const AreaCanvas = lazy(() => import('../components/map/AreaCanvas'))
type Boundary = Polygon | MultiPolygon
type Area = { geometry: Boundary; territoryId: string | null; proposal?: Territory }

export default function MapFirstHome({ active }: { active: boolean }) {
  const h = useHome(), registry = useTerritory()
  const [area, setArea] = useState<Area | null>(null), [overviewOpen, setOverviewOpen] = useState(true)
  const [drawing, setDrawing] = useState<'overview' | 'farm' | null>(null), [parcel, setParcel] = useState<Polygon | null>(null)
  const [farmer, setFarmer] = useState({ name: '', reference: '', phone: '' }), [chatOpen, setChatOpen] = useState(false), [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false), [ambiguous, setAmbiguous] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('')
  const requestKey = useRef(crypto.randomUUID()), controller = useRef(new AbortController()), crop = useRef<HTMLElement>(null), form = useRef<HTMLFormElement>(null)
  const previousSkill = useRef(h.skillId), chatButton = useRef<HTMLButtonElement>(null), chat = useRef<HTMLElement>(null)
  const assigned = registry.territories.filter(t => t.origin === 'backend' && t.status === 'assigned')
  const current = registry.territories.find(t => t.id === registry.currentId)
  const areaTerritory = registry.territories.find(t => t.id === area?.territoryId)
  const authorizedArea = !!area && !!areaTerritory && areaTerritory.status === 'assigned'
  const selected = h.plots.find(p => p.id === h.selectedFarmId)
  const plots = registry.plots.filter(p => p.origin === 'backend' && p.territoryId === area?.territoryId && !!area && sharedArea(p.geometry, area.geometry) > 0)
  const block = investigationBlock(h)
  useEffect(() => { const c = new AbortController(); controller.current = c; return () => c.abort() }, [])
  useEffect(() => { if (!active) setDrawing(null) }, [active])
  useEffect(() => {
    if (area?.territoryId && areaTerritory?.status === 'assigned') void territoryStore.getState().loadRegisteredPlots(bounds(area.geometry))
  }, [area, areaTerritory?.status, h.context?.territory_workspace])
  useEffect(() => {
    if (h.activeId || (h.selectedIds.length > 0 && previousSkill.current !== h.skillId)) setChatOpen(true)
    previousSkill.current = h.skillId
  }, [h.activeId, h.selectedIds.length, h.skillId])
  useEffect(() => {
    if (!chatOpen) return
    chat.current?.focus()
    const key = (e: KeyboardEvent) => {
      if (e.key === 'Escape') { setChatOpen(false); chatButton.current?.focus() }
      if (e.key === 'Tab') {
        const items = Array.from(chat.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],summary') ?? []).filter(el => el.getClientRects().length)
        const first = items[0], last = items.at(-1)
        if (e.shiftKey && (document.activeElement === first || document.activeElement === chat.current)) { e.preventDefault(); last?.focus() }
        else if (!e.shiftKey && (document.activeElement === last || document.activeElement === chat.current)) { e.preventDefault(); first?.focus() }
      }
    }
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key)
  }, [chatOpen])
  useEffect(() => { if (parcel) form.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' }) }, [parcel])
  const fail = (e: unknown) => { if (!controller.current.signal.aborted) setError(e instanceof Error ? e.message : 'The request could not be completed.') }
  const chooseArea = (geometry: Boundary, territory?: Territory) => {
    if (parcel || busy) { setError('Finish or cancel the farm form before changing the area.'); return }
    const owner = territory ?? assigned.find(t => t.id === registry.currentId && contained(geometry, t.boundary)) ?? assigned.find(t => contained(geometry, t.boundary))
    if (owner) territoryStore.getState().switchTerritory(owner.id, true)
    setArea({ geometry, territoryId: owner?.id ?? null }); setOverviewOpen(false); setDrawing(null); setError(''); setNotice('')
    requestAnimationFrame(() => crop.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  const proposeArea = async () => {
    if (!area || busy) return
    setBusy(true); setError('')
    try {
      const point = center(area.geometry)
      const proposal = territorySchema.parse(await registryRequest('/territory-proposals', write({
        name: `Field area ${point.lat.toFixed(3)}, ${point.lng.toFixed(3)}`, boundary: area.geometry,
      }), controller.current.signal))
      territoryStore.setState(s => ({ territories: [...s.territories, proposal] }))
      setArea({ geometry: area.geometry, territoryId: null, proposal })
    } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const approveArea = async () => {
    if (!area?.proposal || busy) return
    setBusy(true); setError('')
    try {
      const approved = territorySchema.parse(await registryRequest(`/territories/${area.proposal.id}/review`, write({
        expected_revision: area.proposal.revision, decision: 'approve',
      }), controller.current.signal))
      territoryStore.setState(s => ({ territories: [...s.territories.filter(t => t.id !== approved.id), approved] }))
      territoryStore.getState().switchTerritory(approved.id, true)
      setArea({ geometry: area.geometry, territoryId: approved.id }); setNotice('Area approved. Draw the first farm below.')
    } catch (e) { fail(e) } finally { setBusy(false) }
  }
  const selectPlot = async (id: string) => {
    if (parcel || drawing || busy) return
    setError('')
    try {
      const result = parsePlot(await registryRequest(`/plots/${encodeURIComponent(id)}`, {}, controller.current.signal))
      mergeHomePlots([...homeStore.getState().plots, result.home])
      homeStore.setState({ selectedIds: [id], highlightedIds: [id], selectedFarmId: id, localDraftSelected: false })
      territoryStore.setState({ selectedPlotId: id })
    } catch (e) { fail(e) }
  }
  const saveFarm = async () => {
    if (!area?.territoryId || !parcel || busy) return
    setBusy(true); setError('')
    try {
      const result = parsePlot(await registryRequest(`/territories/${encodeURIComponent(area.territoryId)}/farm-registrations`, write({
        selection_boundary: area.geometry, geometry: parcel, farmer_name: farmer.name, farmer_reference: farmer.reference,
        phone: farmer.phone, request_key: requestKey.current,
      }), controller.current.signal))
      mergeHomePlots([...homeStore.getState().plots, result.home])
      territoryStore.setState(s => ({ plots: [...s.plots.filter(p => p.id !== result.plot.id), result.plot],
        farmers: [...s.farmers.filter(f => !result.farmers.some(saved => saved.id === f.id)), ...result.farmers],
        territories: s.territories.map(t => t.id === area.territoryId ? { ...t, authorizedPlotIds: [...new Set([...(t.authorizedPlotIds ?? []), result.plot.id])] } : t),
        selectedPlotId: result.plot.id, plotTotal: s.plots.some(p => p.id === result.plot.id) ? s.plotTotal : s.plotTotal + 1 }))
      homeStore.setState({ selectedIds: [result.plot.id], highlightedIds: [result.plot.id], selectedFarmId: result.plot.id, localDraftSelected: false })
      setParcel(null); setFarmer({ name: '', reference: '', phone: '' }); setAmbiguous(false)
      setNotice('Farm saved. Select AI Chat when you are ready to explore it.')
    } catch (e) { setAmbiguous(e instanceof HomeApiError && e.ambiguous); fail(e) } finally { setBusy(false) }
  }
  const startFarm = () => { setError(''); setNotice(''); setDrawing('farm'); setParcel(null); requestKey.current = crypto.randomUUID() }
  return <main className="map-first-home" aria-label="Agricultural map workspace">
    <div className="map-first-content" inert={chatOpen}><header className="map-first-header"><a href="#home" className="map-first-brand"><Sprout size={25} /><span>AgriLo <strong>FieldOps</strong><small>{h.context?.office_name}</small></span></a><div className="map-first-actions"><button title="Refresh saved areas and farms" aria-label="Refresh saved records" disabled={busy || !!parcel} onClick={() => void h.reload()}><RefreshCw size={16} /></button><button ref={chatButton} className="map-chat-button" disabled={!selected} onClick={() => setChatOpen(true)}><MessageSquare size={17} />AI Chat{h.activeId && <span className="chat-running-dot" />}</button><button aria-label="Sign out" title="Sign out" onClick={h.logout}><LogOut size={16} /></button></div></header>
    <nav className="map-first-steps" aria-label="Farm registration steps"><span className={!area ? 'current' : 'complete'}><b>{area ? <Check size={13} /> : '1'}</b>Select an area</span><span className={area && !parcel ? 'current' : ''}><b>2</b>Draw a farm</span><span className={parcel ? 'current' : ''}><b>3</b>Farmer details</span></nav>
    <section className={'overview-step' + (area ? ' has-area' : '')} aria-label="Select an area">
      <div className="area-section-heading"><div><span className="area-eyebrow">STEP 1</span><h1>{area ? 'Your selected area' : 'Start with your area'}</h1>{!area && <p>Find your land on the satellite map, then draw a blue box around the area you want to work in.</p>}</div><div className="area-step-actions">{area && <button disabled={!!parcel || busy} onClick={() => setOverviewOpen(!overviewOpen)}><ChevronDown size={15} />{overviewOpen ? 'Hide overview' : 'Change area'}</button>}{(!area || overviewOpen) && <button className="primary" disabled={!!parcel || busy} onClick={() => setDrawing(drawing === 'overview' ? null : 'overview')}><SquareDashed size={16} />{drawing === 'overview' ? 'Cancel drawing' : area ? 'Redraw area' : 'Draw area'}</button>}</div></div>
      {overviewOpen && <Suspense fallback={<div className="area-loading">Opening satellite map…</div>}><AreaCanvas kind="overview" active={active} drawing={drawing === 'overview'} boundary={area?.geometry ?? current?.boundary ?? null} preview={null} onDraw={g => chooseArea(g)} onCancel={() => setDrawing(null)} onError={setError} /></Suspense>}
      {!area && assigned.length > 0 && <div className="existing-areas"><span>Or continue in a saved area</span>{assigned.map(t => <button key={t.id} onClick={() => chooseArea(t.boundary, t)}>{t.name}<ArrowDown size={14} /></button>)}</div>}
    </section>
    {error && <p className="map-first-error" role="alert">{error}</p>}{notice && <p className="map-first-notice" role="status">{notice}</p>}
    {area && <section ref={crop} className="farm-crop-step" aria-label="Cropped area and farms">
      <div className="area-section-heading"><div><span className="area-eyebrow">STEP 2 · SELECTED AREA ONLY</span><h2>Draw farms here</h2><p>This is a separate map of your selected area. Farm boundaries stay inside the blue edge.</p></div><div className="area-step-actions"><span className="area-size">{(measuredArea(area.geometry) / 1e6).toFixed(2)} km²</span><button className="primary" disabled={!authorizedArea || busy || !!parcel || h.context?.role === 'viewer'} onClick={startFarm}><Plus size={16} />Draw farm plot</button></div></div>
      {!authorizedArea && <div className="area-access-note">{area.proposal ? <><p>This area is awaiting office approval{h.context?.role === 'office_admin' ? '.' : ' and an officer assignment. You can view it while approval is pending.'}</p>{h.context?.role === 'office_admin' && <button disabled={busy} onClick={() => void approveArea()}>Approve area and continue</button>}</> : <><p>This selection is outside your assigned areas. Submit it for office approval before registering farms.</p><button disabled={busy} onClick={() => void proposeArea()}>Submit area for approval</button></>}</div>}
      <Suspense fallback={<div className="area-loading">Opening your cropped area…</div>}><AreaCanvas kind="farm" active={active} drawing={drawing === 'farm'} boundary={area.geometry} preview={parcel} plots={plots} selectedId={h.selectedFarmId} onDraw={g => { setParcel(g); setFarmer({ name: '', reference: '', phone: '' }); setAmbiguous(false) }} onCancel={() => setDrawing(null)} onError={setError} onSelect={id => void selectPlot(id)} /></Suspense>
      {parcel && <form ref={form} className="quick-farm-form" aria-label="Farmer details" onSubmit={e => { e.preventDefault(); void saveFarm() }}><div><span className="area-eyebrow">STEP 3</span><h3>Who farms this plot?</h3><p>{(measuredArea(parcel) / 1e4).toFixed(2)} hectares selected. Enter three details to save the farm.</p></div><fieldset disabled={busy || ambiguous}><label>Farmer name<input required autoComplete="off" maxLength={120} value={farmer.name} onChange={e => setFarmer({ ...farmer, name: e.target.value })} /></label><label>Farmer ID<input required autoComplete="off" maxLength={80} value={farmer.reference} onChange={e => setFarmer({ ...farmer, reference: e.target.value })} /></label><label>Phone number<input required type="tel" autoComplete="off" maxLength={40} minLength={7} inputMode="tel" value={farmer.phone} onChange={e => setFarmer({ ...farmer, phone: e.target.value })} /></label></fieldset><div className="quick-form-actions"><button type="button" disabled={busy || ambiguous} onClick={() => { setParcel(null); setError('') }}>Cancel</button><button className="primary" disabled={busy}>{busy ? 'Saving farm…' : ambiguous ? 'Retry the same save' : 'Save farm'}</button></div>{ambiguous && <p role="status">The save was not confirmed. Retry safely with the same details; a second farm will not be created.</p>}</form>}
      {!parcel && <div className="saved-farms"><div className="saved-farms-heading"><h3>{plots.length ? 'Saved farms' : 'Your first farm starts here'}</h3>{selected && <button onClick={() => setChatOpen(true)}><MessageSquare size={15} />Ask about {selected.name}</button>}</div>{!plots.length && <p>Choose “Draw farm plot” and mark farmland on the cropped map above.</p>}<div className="saved-farm-list">{plots.map(p => <button key={p.id} aria-pressed={h.selectedFarmId === p.id} onClick={() => void selectPlot(p.id)}><span>{p.name}</span><small>{(measuredArea(p.geometry) / 1e4).toFixed(2)} ha</small>{h.selectedFarmId === p.id && <Check size={15} />}</button>)}</div>{registry.plotTotal > plots.length && <p>{plots.length} of {registry.plotTotal} matches loaded. The map loads up to 100 farm boundaries.</p>}</div>}
    </section>}
    </div>{chatOpen && <><button className="farm-chat-backdrop" aria-label="Close AI chat" onClick={() => setChatOpen(false)} /><section ref={chat} tabIndex={-1} className="farm-ai-chat live-home" role="dialog" aria-modal="true" aria-label="Farm AI Chat"><header><div><MessageSquare size={18} /><span>AI Chat<small>{selected?.name ?? 'Farm investigation'}</small></span></div><button aria-label="Close chat" onClick={() => { setChatOpen(false); chatButton.current?.focus() }}><X size={20} /></button></header><div className="farm-chat-body"><p className="chat-welcome">What do you have in mind for this farm? {h.context?.model.plot_data_policy === 'environment_only' ? 'Choose weather, soil, or both for this farm and ask your question below.' : 'Describe your idea or choose an analysis below.'}</p>{selected && h.context?.model.plot_data_policy === 'environment_only' && <p className="tiny">Weather and soil use the saved farm point: {selected.latitude.toFixed(5)}, {selected.longitude.toFixed(5)}. Soil values are mapped estimates.</p>}<InvestigationControls compact /><InvestigationResults />{h.error && <p role="alert">{h.error}</p>}</div><form className="live-question" onSubmit={e => { e.preventDefault(); const text = question; setQuestion(''); void h.submit(text) }}><label htmlFor="farm-question">Farming idea or question</label><textarea id="farm-question" minLength={3} maxLength={2000} value={question} onChange={e => setQuestion(e.target.value)} placeholder="I want to grow maize. What should I check about this farm?" /><button className="primary" disabled={!!block || !!h.activeId || question.trim().length < 3}>{h.activeId ? 'Analyzing…' : 'Start analysis'}</button></form></section></>}
  </main>
}
