import { useEffect, useRef, useState } from 'react'
import { MapPinned, Plus, Users, X } from 'lucide-react'
import { useTerritory } from '../../features/territory/store'
import { measuredArea } from '../../features/territory/geometry'
import { PluginModal } from '../plugins/PluginModal'
import { FarmerRegistrationForm, PlotRegistrationForm, TerritorySetupForm } from './TerritoryForms'
import { RegistryAdministration } from './RegistryAdministration'
import { FarmDetails, FarmerDetails, FarmersDirectory } from './TerritoryDirectory'

export function TerritoryHomeControls() {
  const s = useTerritory(), t = s.territories.find(t => t.id === s.currentId), ref = useRef<HTMLElement>(null)
  const [confirm, setConfirm] = useState<{ title: string; body: string; run: () => void } | null>(null)
  const act = (run: () => void) => { if (s.dirty) setConfirm({ title: 'Discard unsaved registration?', body: 'The unsaved form and boundary preview will be discarded. Saved territories and plots remain.', run: () => { s.close(true); run() } }); else run() }
  const close = () => { if (!s.close()) act(() => s.close(true)) }
  const title = s.panel === 'territory-setup' ? 'Set Up My Territory' : s.panel === 'plot-form' ? 'Register Farm Plot' : s.panel === 'farmer-form' ? 'Register Farmer' : s.panel === 'farmers' ? 'Farmers directory' : s.panel === 'farmer-details' ? 'Farmer profile' : s.panel === 'plot-details' ? 'Farm details' : 'My Territory'
  const drawing = s.mode.startsWith('draw-') || s.mode.startsWith('edit-')
  useEffect(() => { if (!s.panel || drawing) return; const previous = document.activeElement as HTMLElement | null; ref.current?.focus(); return () => { if (previous?.isConnected) previous.focus() } }, [s.panel, drawing])
  useEffect(() => { if (!s.panel || drawing) return; const key = (e: KeyboardEvent) => { if (e.key === 'Escape' && ref.current?.contains(e.target as Node)) { e.stopPropagation(); close() } }; const el = ref.current; el?.addEventListener('keydown', key); return () => el?.removeEventListener('keydown', key) })
  const localPlots = s.plots.filter(p => p.territoryId === t?.id), linkedFarmers = new Set(localPlots.flatMap(p => p.farmerIds))
  return <>
    <section className="territory-home-toolbar" aria-label="Territory workspace controls"><div className="territory-current"><MapPinned size={17} /><span><strong>{t?.name ?? 'Your agricultural workspace'}</strong><small>{t ? t.status === 'assigned' ? 'Backend assignment' : t.status === 'pending-approval' ? 'Pending office verification' : t.status === 'inactive' ? 'Inactive territory' : 'Local proposal · not assigned' : s.assignments.status === 'available' ? 'No assigned territory' : 'Territory assignments unavailable'}</small></span></div>{t && <p className="territory-counts">{s.backendReady && t?.origin === 'backend' ? s.plotTotal : localPlots.length} {t?.origin === 'backend' ? 'registered plots' : 'local plots'} / {s.backendReady && t?.origin === 'backend' ? s.farmerTotal : linkedFarmers.size} farmer profiles</p>}<div className="territory-home-actions"><button onClick={() => act(() => s.open('territory'))}><MapPinned size={14} />My Territory</button><button onClick={() => act(() => s.open('farmers'))}><Users size={14} />Farmers</button><button onClick={() => act(() => t ? s.beginPlot() : s.beginTerritory())}><Plus size={14} />{t ? 'Register Farm Plot' : 'Set Up My Territory'}</button></div></section>
    {s.backendReady && s.plotTotal > localPlots.length && <p className="territory-inline-notice" role="status">Showing {localPlots.length} of {s.plotTotal} matching plot boundaries. Zoom into a smaller area to inspect more farms; the map loads at most 100 boundaries per query.</p>}
    {s.notice && <p className="territory-inline-notice" role="status">{s.notice}</p>}
    {s.storageError && <p className="territory-inline-error" role="alert">{s.storageError}</p>}
    {s.error && !s.panel && <p className="territory-inline-error" role="alert">{s.error}</p>}
    {s.panel && <section className="territory-drawer plugins-theme" hidden={drawing} ref={ref} tabIndex={-1} role="dialog" aria-modal="false" aria-label={title}><header><div><span>AGRILO HOME</span><h2>{title}</h2></div><button onClick={close} aria-label="Close territory panel"><X size={20} /></button></header><div className="territory-drawer-body">
      {s.error && <p className="territory-inline-error" role="alert">{s.error}</p>}
      {s.panel === 'territory-setup' && <TerritorySetupForm />}
      {s.panel === 'plot-form' && <PlotRegistrationForm />}
      {s.panel === 'farmer-form' && <FarmerRegistrationForm />}
      {s.panel === 'farmers' && <FarmersDirectory />}
      {s.panel === 'farmer-details' && <FarmerDetails />}
      {s.panel === 'plot-details' && <FarmDetails onDelete={id => setConfirm({ title: 'Delete local plot?', body: 'This removes the local geometry and its crop draft. The linked farmer profile is retained.', run: () => s.removePlot(id) })} />}
      {s.panel === 'territory' && <div className="territory-record">{s.backendReady && <RegistryAdministration />}
        {!t && <><h3>Welcome to Your Agricultural Workspace</h3><p>Start by defining the agricultural area you are responsible for. You'll then be able to register farms, manage farmer profiles, and investigate agricultural conditions.</p></>}
        {s.assignments.status !== 'available' && <p className="territory-callout">{s.assignments.message}</p>}
        {s.assignments.status === 'available' && !s.assignments.territories.length && <p>No assigned territory is recorded in the authorized response.</p>}
        {s.territories.length > 1 && <label>Territory switcher<select value={s.currentId ?? ''} onChange={e => { const id = e.target.value; if (!s.switchTerritory(id)) act(() => s.switchTerritory(id, true)) }}>{s.territories.map(t => <option key={t.id} value={t.id}>{t.name} · {t.status}</option>)}</select></label>}
        {t && <><h3>{t.name}</h3><span className="territory-status">{t.origin === 'synthetic' ? 'Synthetic demo · ' : ''}{t.status === 'assigned' ? 'Assigned by backend' : t.status === 'pending-approval' ? 'Pending office verification' : t.status === 'inactive' ? 'Inactive territory' : 'Local draft · not assigned'}</span><dl><dt>Area</dt><dd>{(measuredArea(t.boundary) / 1e6).toFixed(3)} km²</dd><dt>Region / district</dt><dd>{t.region || 'Not retained'} / {t.district || 'Not retained'}</dd><dt>Office</dt><dd>{s.officeName ?? 'No authorized office loaded'}</dd><dt>Official registered farmers</dt><dd>{s.backendReady && t?.origin === 'backend' ? s.farmerTotal : 'Unavailable from current registry'}</dd><dt>Authorized farm points</dt><dd>{t.authorizedPlotIds?.length ?? 'Not supplied'}</dd><dt>Loaded plots / linked profiles</dt><dd>{localPlots.length} / {linkedFarmers.size}</dd><dt>Crop records</dt><dd>{s.seasons.filter(c => localPlots.some(p => p.id === c.plotId)).length} records</dd></dl><div className="territory-actions"><button className="plugin-secondary" onClick={() => s.fit(t.boundary)}>Inspect territory boundary</button>{<button className="plugin-secondary" onClick={() => s.beginTerritory(t.id)}>{t.origin === 'backend' ? 'Edit territory (permission checked)' : 'Edit territory draft'}</button>}<button className="plugin-secondary" onClick={() => s.open('farmers')}>View farm records</button></div><h3>Farm plots</h3>{localPlots.map(p => <button key={p.id} className="territory-profile-link" onClick={() => { s.selectPlot(p.id); s.fit(p.geometry) }}>{p.name} · {p.status}</button>)}{!localPlots.length && <p>No local plots have been drawn in this territory.</p>}</>}
        <div className="territory-actions"><button className="plugin-primary" onClick={() => s.beginTerritory()}>Set Up My Territory</button><button className="plugin-secondary" onClick={s.loadDemo}>Explore Demo Workspace</button><button className="plugin-secondary" onClick={() => s.beginFarmer()}>Register Farmer</button></div><p className="territory-hint">Green: territory · blue: local plot · gold: selected / unsaved plot · purple: temporary analysis area. Local boundaries confer no permissions.</p>
      </div>}
    </div><footer>Local drafts are separate from official assignments and registrations.</footer></section>}
    {confirm && <PluginModal title={confirm.title} onClose={() => setConfirm(null)}><p>{confirm.body}</p><div className="plugin-detail-actions"><button className="plugin-secondary" onClick={() => setConfirm(null)}>Keep editing</button><button className="plugin-danger" onClick={() => { confirm.run(); setConfirm(null) }}>Discard and continue</button></div></PluginModal>}
  </>
}
