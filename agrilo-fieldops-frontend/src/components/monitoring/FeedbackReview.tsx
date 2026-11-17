import { useState } from 'react'
import { Check, ClipboardCheck, MessageSquare, Save } from 'lucide-react'
import { monitoringService, useMonitoring } from '../../features/monitoring/store'
import type { FeedbackDraft, MonitorDefinition, OfficerReviewDecision } from '../../features/monitoring/types'
import type { FeedbackSeed } from './PhotoWorkspace'
import { sampleTimelines } from '../../features/monitoring/fixtures'
import { Field, formatDate } from './MonitoringUi'
const actions = { save_later: 'Saved for later', approve_demo: 'Demo approval recorded', reject: 'Rejected locally', inspection: 'Inspection requested locally' }
export function FeedbackReview({ monitor, seed, sample }: { monitor: MonitorDefinition; seed?: FeedbackSeed; sample: boolean }) {
  const state = useMonitoring(), [farmId, setFarmId] = useState(seed?.farmId ?? monitor.input.scope.farms[0]?.id ?? '')
  const saved = state.feedback.filter(f => f.monitorId === monitor.id && f.farmId === farmId).at(-1)
  const [text, setText] = useState(saved?.text ?? (sample || seed ? "Thank you for sharing your crop observation. The agricultural officer would like a clear image of the affected leaves and surrounding plants to help assess the situation." : ''))
  const [reason, setReason] = useState(saved?.reason ?? seed?.reason ?? (sample ? 'Illustrative leaf-color difference requires officer review.' : ''))
  const [target, setTarget] = useState<FeedbackDraft | undefined>(saved), [dirty, setDirty] = useState(!saved), [reviewer, setReviewer] = useState(''), [confirm, setConfirm] = useState(false)
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const samplePhoto = sample ? sampleTimelines().find(t => t.farm.id === farmId)?.submissions.at(-1) : undefined
  const [evidenceIds, setEvidenceIds] = useState(seed?.evidenceIds ?? saved?.evidenceIds ?? (samplePhoto ? [samplePhoto.id] : []))
  const [origin, setOrigin] = useState<FeedbackDraft['origin']>(seed?.origin ?? saved?.origin ?? (sample ? 'synthetic' : 'local_draft'))
  const changeFarm = (id: string) => {
    const record = state.feedback.filter(f => f.monitorId === monitor.id && f.farmId === id).at(-1)
    setFarmId(id); setTarget(record); setText(record?.text ?? ''); setReason(record?.reason ?? ''); setEvidenceIds(record?.evidenceIds ?? []); setOrigin(record?.origin ?? 'local_draft'); setDirty(!record); setConfirm(false); setError(null)
  }
  const save = async () => {
    setError(null)
    if (!text.trim() || !reason.trim()) { setError('Enter a reason and a feedback draft before saving.'); return }
    setBusy(true)
    try {
      const draft = await monitoringService.saveFeedback({ monitorId: monitor.id, farmId, text, reason, evidenceIds, origin }, target ? { id: target.id, version: target.version } : undefined)
      await state.refresh(); setTarget(draft); setDirty(false); setConfirm(false); state.notify('Feedback draft saved locally. No message was transmitted.')
    } catch { setError('Could not save the draft. Check the text for credentials, storage permissions, and the current configuration version.') }
    finally { setBusy(false) }
  }
  const review = async (action: OfficerReviewDecision['action']) => {
    if (!target || dirty) return
    if (!reviewer.trim() || (action === 'approve_demo' && !confirm)) { setError('Enter a local reviewer name and acknowledge the demonstration-only approval.'); return }
    setBusy(true); setError(null)
    try { const next = await monitoringService.reviewFeedback(target.id, target.version, action, reviewer); await state.refresh(); setTarget(next); state.notify(actions[action] + '. No delivery was authorized or sent.') }
    catch { setError('Could not record this local review. Reopen the current draft and check browser storage permissions.') }
    finally { setBusy(false) }
  }
  const latest = target?.decisions.filter(d => d.feedbackVersion === target.version).at(-1)
  return <section className="monitor-feedback"><div className="monitor-section-heading"><div><h2>Feedback & officer review</h2><p>Prepare a farmer-facing draft and record a local review decision.</p></div><MessageSquare size={22} /></div>
    <div className="monitor-info"><ClipboardCheck size={18} /><p>Local draft review only. This prototype cannot authenticate an officer, authorize delivery or contact a farmer. Real transmission requires explicit authorized approval, recipients and an approved connector.</p></div>
    <div className="monitor-feedback-layout"><div className="monitor-feedback-form">
      <Field label="Farm"><select aria-label="Feedback farm" value={farmId} onChange={e => changeFarm(e.target.value)}>{monitor.input.scope.farms.map(f => <option key={f.id} value={f.id}>{f.name} · {f.crop}</option>)}</select></Field>
      <Field label="Reason for follow-up"><textarea aria-label="Feedback reason" maxLength={400} rows={2} value={reason} onChange={e => { setReason(e.target.value); setDirty(true) }} /></Field>
      <Field label="Farmer feedback draft"><textarea aria-label="Farmer feedback draft" maxLength={2000} rows={6} value={text} onChange={e => { setText(e.target.value); setDirty(true) }} /></Field>
      <p className="monitor-muted">Evidence references: {evidenceIds.length ? evidenceIds.join(', ') : 'None supplied. Add supporting context before a real review.'}</p>
      <button className="monitor-primary" disabled={busy} onClick={() => { void save() }}><Save size={15} />Save feedback draft</button>
    </div><aside className="monitor-review-panel"><small>LOCAL REVIEW</small><h3>{dirty ? 'Unsaved changes' : latest ? actions[latest.action] : 'Awaiting local review'}</h3><p>{target ? 'Draft version ' + target.version + (dirty ? ' · editing requires a new review' : '') : 'Save the draft before recording a decision.'}</p>
      <Field label="Local reviewer name"><input aria-label="Local reviewer name" maxLength={80} autoComplete="off" value={reviewer} onChange={e => setReviewer(e.target.value)} /></Field>
      <label className="monitor-check-label"><input type="checkbox" checked={confirm} onChange={e => setConfirm(e.target.checked)} />I understand this records a demo approval only and authorizes no delivery.</label>
      <div className="monitor-review-actions"><button className="monitor-primary" disabled={busy || dirty || !target} onClick={() => { void review('approve_demo') }}><Check size={14} />Record demo approval</button><button className="plugin-secondary" disabled={busy || dirty || !target} onClick={() => { void review('save_later') }}>Save for later</button><button className="plugin-secondary" disabled={busy || dirty || !target} onClick={() => { void review('inspection') }}>Request field inspection</button><button className="plugin-danger" disabled={busy || dirty || !target} onClick={() => { void review('reject') }}>Reject draft</button></div>
      <button disabled className="plugin-secondary">Delivery unavailable</button><p className="monitor-muted">Future SMS, email, intake and voice connectors will be managed in Plugins.</p>
    </aside></div>
    {error && <div className="monitor-errors" role="alert">{error}</div>}
    {!!target?.decisions.length && <section className="monitor-review-audit"><h3>Local decision history</h3>{target.decisions.slice().reverse().map(d => <div key={d.id}><strong>{actions[d.action]}</strong><span>Version {d.feedbackVersion} · {d.reviewer} · {formatDate(d.at)}</span><small>{d.feedbackVersion !== target.version ? 'Superseded by a newer draft version · review again' : 'Local demo decision · no authenticated authority or delivery'}</small></div>)}</section>}
  </section>
}
