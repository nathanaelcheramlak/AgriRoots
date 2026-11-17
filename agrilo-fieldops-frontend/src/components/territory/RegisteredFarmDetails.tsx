import { useEffect, useState } from 'react'
import { z } from 'zod'
import { useTerritory, territoryStore } from '../../features/territory/store'
import { useHome, homeStore } from '../../state/useHome'
import { registryRequest, parsePlot, farmerPageSchema, write } from '../../features/territory/backend'
import { jobSchema, jobLabel } from '../../api/home-contracts'

export function RegisteredFarmDetails({ id }: { id: string }) {
  const s = useTerritory(), h = useHome(), [data, setData] = useState<ReturnType<typeof parsePlot> | null>(null)
  const [tab, setTab] = useState('Overview'), [records, setRecords] = useState<unknown[]>([]), [error, setError] = useState('')
  const [metric, setMetric] = useState(''), [value, setValue] = useState(''), [unit, setUnit] = useState(''), [source, setSource] = useState('')
  const [provenance, setProvenance] = useState('self-reported'), [observedAt, setObservedAt] = useState(''), [serial, setSerial] = useState(0)
  useEffect(() => {
    const controller = new AbortController(); setError(''); setData(null); setRecords([])
    registryRequest(`/plots/${id}`, {}, controller.signal).then(parsePlot).then(setData).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Farm unavailable') })
    const suffix = { 'Crop Records': 'crop-seasons', Observations: 'observations', Investigations: 'investigations' }[tab]
    if (suffix) registryRequest(`/plots/${id}/${suffix}?limit=25`, {}, controller.signal).then(farmerPageSchema.parse).then(p => setRecords(p.items)).catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Farm history unavailable') })
    return () => controller.abort()
  }, [id, tab, serial])
  if (!data) return <p role={error ? 'alert' : 'status'}>{error || 'Loading registered farm…'}</p>
  const { plot, season, farmers } = data
  return <div className="territory-record"><span className="territory-status">Registered · {data.home.synthetic ? 'Synthetic test farm record' : 'Real farm record'}</span><h3>{plot.name}</h3><p>{plot.id}</p>
    <div className="territory-detail-tabs" role="tablist" aria-label="Farm record sections">{['Overview', 'Crop Records', 'Observations', 'Investigations'].map(t => <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}>{t}</button>)}</div>
    {error && <p role="alert">{error}</p>}
    {tab === 'Overview' && <><dl><dt>Recorded area</dt><dd>{data.home.area.toFixed(3)} ha</dd><dt>Crop / planting</dt><dd>{season?.crop ?? 'Unknown'} / {season?.plantingDate || 'Unknown'}</dd><dt>Stage / irrigation</dt><dd>{season?.stage ?? 'Unknown'} / {season?.irrigation ?? 'unknown'}</dd><dt>Private farm notes</dt><dd>{plot.notes || 'None recorded'}</dd><dt>Registration state</dt><dd>{plot.status} · revision {plot.revision}</dd></dl><h4>Associated farmers</h4>{farmers.map(f => <p key={f.id}>{f.displayName} · {f.reference}</p>)}<p>Point-based agricultural tools use the server-recorded interior sampling point. Their estimates do not describe every part of the plot.</p></>}
    {tab === 'Crop Records' && records.map((r, i) => { const c = z.object({ crop: z.string().nullable(), planting_date: z.string().nullable(), stage: z.string().nullable() }).parse(r); return <p key={i}>{c.crop ?? 'Unknown crop'} · planted {c.planting_date ?? 'Unknown'} · {c.stage ?? 'Unknown stage'}</p> })}
    {tab === 'Observations' && <><p>Officer field notes (self-reported, private): {plot.observation || 'None recorded'}</p>{records.map((r, i) => { const o = z.object({ metric: z.string(), value: z.number(), unit: z.string(), source: z.string(), provenance: z.string(), observed_at: z.string().nullable() }).parse(r); return <p key={i}>{o.metric}: {o.value} {o.unit} · {o.provenance} · {o.source} · {o.observed_at ?? 'Observation date unknown'}</p> })}<form className="territory-form" onSubmit={async e => { e.preventDefault(); try { await registryRequest(`/plots/${id}/observations`, write({ metric, value: Number(value), unit, source, provenance, observed_at: observedAt ? new Date(observedAt).toISOString() : null })); setSerial(v => v + 1) } catch (e) { setError(e instanceof Error ? e.message : 'Observation not saved') } }}><h4>Record a structured field observation</h4><label>Metric<input required maxLength={80} value={metric} onChange={e => setMetric(e.target.value)} /></label><label>Value<input required type="number" step="any" value={value} onChange={e => setValue(e.target.value)} /></label><label>Unit<input required maxLength={40} value={unit} onChange={e => setUnit(e.target.value)} /></label><label>Source<input required maxLength={200} value={source} onChange={e => setSource(e.target.value)} /></label><label>Observation date<input type="datetime-local" value={observedAt} onChange={e => setObservedAt(e.target.value)} /></label><label>Provenance<select value={provenance} onChange={e => setProvenance(e.target.value)}>{['self-reported','measured','model-derived','synthetic'].map(p => <option key={p}>{p}</option>)}</select></label><button className="plugin-primary">Save observation</button></form></>}
    {tab === 'Investigations' && <>{records.map(r => { const job = jobSchema.parse(r); return <p key={job.id}>{jobLabel(job)} · {job.id}<button className="plugin-secondary" disabled={!!h.activeId} onClick={() => { void h.openSavedJob(job.id, id); s.close(true) }}>Open saved findings and evidence</button></p> })}{!records.length && <p>No investigations have been submitted for this plot.</p>}</>}
    <div className="territory-actions"><button className="plugin-secondary" onClick={() => s.fit(plot.geometry)}>Inspect boundary</button><button className="plugin-secondary" onClick={() => { territoryStore.setState(v => ({ plots: v.plots.map(p => p.id === id ? plot : p) })); s.beginPlot(id) }}>Edit registered plot</button><button className="plugin-primary" onClick={() => { homeStore.getState().setLocalDraftSelected(false); if (!homeStore.getState().selectedIds.includes(id)) homeStore.getState().selectFarm(id); s.close(true) }}>Select for Analysis</button></div>
    {!data.home.synthetic && h.context?.model.plot_data_policy === 'synthetic_only' && <p className="territory-callout">Real farm registration is supported. Gemini investigations remain blocked by the current privacy policy. Approved provider testing uses the existing controlled executor.</p>}
  </div>
}
