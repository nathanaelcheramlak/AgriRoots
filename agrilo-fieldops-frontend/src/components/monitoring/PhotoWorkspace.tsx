import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Columns2, ImagePlus, Leaf, MessageSquare, X } from 'lucide-react'
import type { FarmPhotoTimeline, FarmReference, PhotoSubmission } from '../../features/monitoring/types'
import { PluginModal } from '../plugins/PluginModal'
import { Field, formatDate, QuietState, SampleNotice } from './MonitoringUi'
export interface FeedbackSeed { farmId: string; reason: string; evidenceIds: string[]; origin: 'synthetic' | 'session_sample' | 'local_draft' }
function SamplePlant({ index = 0 }: { index?: number }) {
  return <svg viewBox="0 0 440 280" role="img" aria-label={'Original maize illustration, sample week ' + (index + 1)} className="monitor-plant-illustration">
    <rect width="440" height="280" fill="#1a2520" /><path d="M0 232 Q100 218 210 238 T440 226 V280 H0Z" fill="#343229" />
    <path d="M0 257 Q150 234 440 251" fill="none" stroke="#59513b" strokeWidth="2" />
    {[100, 215, 330].map((x, i) => <g key={x} transform={'translate(' + x + ' 240) scale(' + (0.7 + index * 0.08 + (i === 1 ? 0.15 : 0)) + ')'}><path d="M0 0 Q5 -90 0 -170" stroke="#8ba56a" strokeWidth="5" fill="none" /><path d="M0 -55 Q-70 -120 -84 -80 Q-40 -95 0 -55" fill="#719769" /><path d="M0 -80 Q75 -148 90 -111 Q40 -122 0 -80" fill="#588163" /><path d="M0 -115 Q-65 -166 -63 -144 Q-30 -145 0 -115" fill={index === 3 && i === 1 ? '#baac64' : '#82a374'} /><path d="M0 -138 Q43 -184 48 -163 Q20 -162 0 -138" fill="#729969" /></g>)}
    <text x="18" y="26" fill="#adbfad" fontSize="10" letterSpacing="1.5">AGRILO · ILLUSTRATIVE SAMPLE</text>
    <text x="18" y="266" fill="#afa88a" fontSize="10">Week {index + 1} · not a field photograph</text>
  </svg>
}
function PhotoImage({ photo }: { photo: PhotoSubmission }) { return photo.kind === 'session_sample' && photo.objectUrl ? <img src={photo.objectUrl} alt={'Session-only sample for farm ' + photo.farmId} /> : <SamplePlant index={photo.imageIndex} /> }
const analysisLabels: Record<PhotoSubmission['analysis'], string> = { not_analyzed: 'Not analyzed', unavailable: 'Analysis unavailable', pending: 'Analysis pending', possible_issue: 'Possible issue · unconfirmed', no_specific_issue: 'No specific issue identified by available analysis', field_inspection: 'Requires field inspection' }
export function PhotoWorkspace({ timelines, farms, sample, onFeedback, onOutreach }: { timelines: FarmPhotoTimeline[]; farms: FarmReference[]; sample: boolean; onFeedback: (seed: FeedbackSeed) => void; onOutreach?: (photo: PhotoSubmission, officerNotes: string) => void }) {
  const [selected, setSelected] = useState<PhotoSubmission | null>(null), [compare, setCompare] = useState(false), [priorId, setPriorId] = useState(''), [farmId, setFarmId] = useState(farms[0]?.id ?? '')
  const [uploads, setUploads] = useState<PhotoSubmission[]>([]), [failure, setFailure] = useState<string | null>(null), [notes, setNotes] = useState<Record<string, string>>({})
  const urls = useRef<string[]>([])
  const alive = useRef(false)
  useEffect(() => { alive.current = true; return () => { alive.current = false; urls.current.forEach(url => URL.revokeObjectURL(url)); urls.current = [] } }, [])
  const records = (sample ? timelines : []).flatMap(t => t.submissions).concat(uploads)
  const ordered = records.filter(p => p.farmId === selected?.farmId).sort((a, b) => a.submittedAt.localeCompare(b.submittedAt))
  const currentIndex = ordered.findIndex(p => p.id === selected?.id), prior = ordered.find(p => p.id === priorId && p.id !== selected?.id) ?? ordered[currentIndex > 0 ? currentIndex - 1 : 1]
  const open = (photo: PhotoSubmission) => { setSelected(photo); setCompare(false); setPriorId('') }
  const intake = async (file?: File) => {
    setFailure(null)
    if (!file) return
    if (!farmId || !['image/jpeg', 'image/png', 'image/webp'].includes(file.type) || file.size > 8 * 1024 * 1024) { setFailure('Choose a farm and a JPEG, PNG, or WebP sample image up to 8 MB.'); return }
    const url = URL.createObjectURL(file)
    try {
      const img = new Image(); img.src = url; await img.decode()
      if (!alive.current) { URL.revokeObjectURL(url); return }
      if (img.naturalWidth * img.naturalHeight > 24000000) throw new Error('Image dimensions')
      const farm = farms.find(f => f.id === farmId)!
      const photo: PhotoSubmission = { id: crypto.randomUUID(), farmId, crop: farm.crop, stage: null, submittedAt: new Date().toISOString(), expectedDate: '', note: 'Explicitly selected local sample. Not a live farmer submission.', quality: 'unassessed', analysis: 'not_analyzed', kind: 'session_sample', objectUrl: url, observations: [], limitations: 'Session-only image. No upload, image analysis, or diagnosis. Removed when this view closes.' }
      urls.current.push(url); setUploads(previous => [...previous, photo]); open(photo)
    } catch { URL.revokeObjectURL(url); setFailure('This sample image could not be decoded, or exceeds 24 megapixels. Choose a smaller raster image.') }
  }
  const expected = sample ? timelines.reduce((n, t) => n + t.expectedDates.length, 0) : null, missing = sample ? timelines.reduce((n, t) => n + t.missingDates.length, 0) : null
  return <section className="monitor-photos">
    {sample && <SampleNotice>Original crop illustrations and deterministic submission records. They are not farmer photographs or completed diagnoses.</SampleNotice>}
    <div className="monitor-section-heading"><div><h2>Crop photo monitoring</h2><p>Observe submissions over time and prepare follow-up for review.</p></div><Leaf size={21} /></div>
    <div className="monitor-stat-grid photo-stat-grid">{[['Expected weekly records', expected], ['Submissions received', records.length], ['Not analyzed / unavailable', records.length], ['Officer-review examples', records.filter(p => p.observations.length).length], ['Missing / late', missing], ['Unmatched / invalid', sample ? 0 : null]].map(([label, value]) => <div className="monitor-stat" key={label}><span>{label}</span><strong>{value ?? '—'}</strong><small>{sample ? 'Synthetic records' : 'Session data only'}</small></div>)}</div>
    <div className="monitor-photo-intake"><div><h3>Inspect your own sample</h3><p>Explicitly select a local image. It stays in memory while this photo view is open and is never saved in browser storage.</p></div><div className="monitor-intake-controls"><select aria-label="Sample image farm" value={farmId} onChange={e => setFarmId(e.target.value)}>{farms.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select><label className="plugin-secondary"><ImagePlus size={15} />Select sample image<input aria-label="Select sample image" type="file" accept="image/jpeg,image/png,image/webp" onChange={e => { void intake(e.target.files?.[0]); e.target.value = '' }} /></label></div>{failure && <p role="alert" className="monitor-error-text">{failure}</p>}</div>
    {!sample && !uploads.length && <QuietState title="No photo records connected">Farmer intake and crop-health analysis require approved backend services. You can inspect an explicitly selected sample image.</QuietState>}
    {(sample ? [...timelines, ...farms.filter(f => !timelines.some(t => t.farm.id === f.id) && uploads.some(p => p.farmId === f.id)).map(farm => ({ farm, submissions: [], missingDates: [], expectedDates: [] }))] : farms.map(farm => ({ farm, submissions: [], missingDates: [], expectedDates: [] }))).map(t => <section className="monitor-photo-timeline" key={t.farm.id}><header><h3>{t.farm.name} <span>{t.farm.crop}</span></h3><small>{sample ? 'Illustrative weekly timeline' : 'Session-only samples'}</small></header><div className="monitor-photo-gallery">
      {records.filter(p => p.farmId === t.farm.id).sort((a, b) => a.submittedAt.localeCompare(b.submittedAt)).map(photo => <button key={photo.id} className="monitor-photo-card" onClick={() => open(photo)}><PhotoImage photo={photo} /><span><strong>{photo.submittedAt.slice(0, 10)}</strong><small>{photo.observations.length ? 'Possible concern · review example' : analysisLabels[photo.analysis]}</small></span></button>)}
      {t.missingDates.map(date => <div className="monitor-missing-photo" key={date}><ImagePlus size={22} /><strong>{date}</strong><span>Awaiting submission</span><small>Operational reminder · crop condition unknown</small></div>)}
    </div></section>)}
    {selected && <PluginModal title="Crop photo details" wide onClose={() => setSelected(null)}>
      <div className="monitor-photo-viewer"><div className="monitor-viewer-heading"><span>{selected.farmId} · {selected.crop}</span><button className="plugin-secondary" disabled={ordered.length < 2} onClick={() => setCompare(!compare)}><Columns2 size={14} />{compare ? 'Single image' : 'Compare images'}</button></div>
        {compare && <Field label="Compare with"><select aria-label="Compare with" value={prior?.id ?? ''} onChange={e => setPriorId(e.target.value)}>{ordered.filter(p => p.id !== selected.id).map(p => <option key={p.id} value={p.id}>{p.submittedAt.slice(0, 10)}</option>)}</select></Field>}
        <div className={'monitor-photo-comparison ' + (compare ? 'is-comparing' : '')}>{compare && prior && prior.id !== selected.id && <figure><PhotoImage photo={prior} /><figcaption>Earlier · {prior.submittedAt.slice(0, 10)}</figcaption></figure>}<figure><PhotoImage photo={selected} /><figcaption>Selected · {selected.submittedAt.slice(0, 10)}</figcaption></figure></div>
        <p className="monitor-comparison-note">Different lighting, angles, distances and plant selection may prevent reliable quantitative growth comparisons. These sample illustrations demonstrate the interface only.</p>
        <div className="monitor-inline-actions"><button disabled={currentIndex <= 0} onClick={() => { setSelected(ordered[currentIndex - 1]); setPriorId('') }}><ArrowLeft size={13} />Previous</button><button disabled={currentIndex >= ordered.length - 1} onClick={() => { setSelected(ordered[currentIndex + 1]); setPriorId('') }}>Next<ArrowRight size={13} /></button></div>
        <dl className="monitor-photo-metadata"><div><dt>Submitted</dt><dd>{formatDate(selected.submittedAt)}</dd></div><div><dt>Crop stage</dt><dd>{selected.stage ?? 'Not recorded'}</dd></div><div><dt>Image quality</dt><dd>{selected.quality === 'illustrative' ? 'Schematic illustration' : 'Unassessed'}</dd></div><div><dt>Analysis status</dt><dd>{analysisLabels[selected.analysis]} · no connected tool</dd></div></dl>
        <section><h4>Accompanying note</h4><p>{selected.note}</p></section>
        {selected.observations.map(o => <section className="monitor-observation" key={o.id}><h4>Possible observation · unconfirmed</h4><p>{o.text}</p><small>Evidence: {o.evidenceIds.join(', ')}. {o.limitations}</small></section>)}
        <section><h4>Evidence & limitations</h4><p>{selected.limitations}</p></section>
        <Field label="Officer notes (session only)"><textarea aria-label="Officer photo notes" maxLength={1000} rows={2} value={notes[selected.id] ?? ''} onChange={e => setNotes(previous => ({ ...previous, [selected.id]: e.target.value }))} /></Field>
        <footer className="monitor-viewer-footer"><button className="plugin-secondary" onClick={() => setSelected(null)}><X size={14} />Close</button><button className="monitor-primary" onClick={() => { onFeedback({ farmId: selected.farmId, reason: selected.observations[0]?.text ?? 'Request a clearer observation for officer review.', evidenceIds: [selected.id], origin: selected.kind === 'illustration' ? 'synthetic' : 'session_sample' }); setSelected(null) }}><MessageSquare size={14} />Prepare feedback draft</button>{onOutreach && <button className="plugin-secondary" disabled={!notes[selected.id]?.trim()} title="Add officer notes before transferring a reviewed crop context." onClick={() => { onOutreach(selected, notes[selected.id]); setSelected(null) }}>Prepare Feedback in Outreach</button>}</footer>
      </div>
    </PluginModal>}
  </section>
}
