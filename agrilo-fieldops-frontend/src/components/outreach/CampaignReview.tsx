import { useState } from 'react'
import { ShieldCheck } from 'lucide-react'
import type { OutreachCampaign, ReviewDecision } from '../../features/outreach/types'
import { channelLabels } from '../../features/outreach/types'
import { groupRecipients } from '../../features/outreach/recipients'
import { reviewWarnings } from '../../features/outreach/messages'
import { groupDecision, latestVersion } from '../../features/outreach/service'
import { outreachService, useOutreach } from '../../features/outreach/store'
import { Field, formatDate, LocalNotice } from './OutreachUi'
import { ChannelPreview } from './ChannelPreview'
export function CampaignReview({ campaign, dirty, onEdit }: { campaign: OutreachCampaign; dirty: boolean; onEdit: (key?: string) => void }) {
  const state = useOutreach(), version = latestVersion(campaign), groups = groupRecipients(version.input)
  const [key, setKey] = useState('*'), [reviewer, setReviewer] = useState(''), [reason, setReason] = useState(''), [ack, setAck] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null)
  const group = groups.find(g => g.key === key), scoped = group ? [group] : groups, issues = [...new Set(scoped.flatMap(g => reviewWarnings(g, version.input)))], memberCount = scoped.reduce((n, g) => n + g.recipientIds.length, 0)
  const record = async (action: ReviewDecision['action']) => {
    if (dirty) return; setError(null); setBusy(true)
    try { await outreachService.review(campaign.id, version.digest, key, action, reviewer, reason, ack); await state.refresh(); setAck(false); state.notify('Demo review decision recorded locally — not valid for delivery.') }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not save this local decision.') }
    finally { setBusy(false) }
  }
  return <section className="outreach-review"><LocalNotice>Demo review decision — not valid for delivery. The backend must authenticate the officer and enforce approval again at the real dispatch boundary.</LocalNotice>
    {dirty && <div className="monitor-errors" role="status">Unsaved changes are present. Save the new revision or discard changes before reviewing the saved version.</div>}
    <div className="monitor-section-heading"><div><h2>Review the exact scope</h2><p>Version {version.number} · {channelLabels[version.input.communication.channel]} · {version.snapshot.eligibleIds.length} eligible candidates · {version.snapshot.excluded.length} exclusions</p></div><ShieldCheck size={22} /></div>
    <div className="outreach-review-layout"><div><Field label="Review scope"><select aria-label="Review scope" value={key} onChange={e => { setKey(e.target.value); setAck(false) }}><option value="*">All current eligible groups</option>{groups.map(g => <option key={g.key} value={g.key}>{g.label} · {g.language} · {g.recipientIds.length}</option>)}</select></Field><div className="outreach-review-target"><strong>{memberCount.toLocaleString()} recipients in this review</strong><p>Snapshot {version.snapshot.digest.slice(0, 16)}…<br />Content {version.digest.slice(0, 16)}…</p><small>Includes exact message wording, personalization, farm scope, channel and evidence. New material changes require a new review.</small></div>
      {!!issues.length && <div className="outreach-review-issues"><h3>Resolve before a demo approval</h3>{issues.map(w => <p key={w}>{w}</p>)}<button className="plugin-secondary" onClick={() => onEdit(group?.key)}>Edit guidance / inspect group</button></div>}
      {!groups.length && <p className="outreach-warning-text">No eligible advisory groups. Review contact, consent and recipient scope first.</p>}
      <Field label="Local reviewer name"><input aria-label="Review officer name" maxLength={80} value={reviewer} onChange={e => setReviewer(e.target.value)} autoComplete="off" /></Field><Field label="Review reason"><textarea aria-label="Review reason" rows={3} maxLength={600} value={reason} onChange={e => setReason(e.target.value)} /></Field>
      <label className="outreach-check-label"><input type="checkbox" checked={ack} onChange={e => setAck(e.target.checked)} />I reviewed the exact recipients, exclusions, evidence, limitations, message and personalization. This is a local demo decision and authorizes no delivery.</label>
      <div className="outreach-review-buttons"><button className="monitor-primary" disabled={busy || dirty || !groups.length || !!issues.length || !ack || !reviewer.trim() || !reason.trim() || campaign.archived} onClick={() => { void record('approve_demo') }}>Record demo approval</button><button className="plugin-secondary" disabled={busy || dirty || !reviewer.trim() || !reason.trim()} onClick={() => { void record('request_evidence') }}>Request more evidence</button><button className="plugin-danger" disabled={busy || dirty || !reviewer.trim() || !reason.trim()} onClick={() => { void record('reject') }}>Reject with reason</button><button className="plugin-secondary" disabled={busy || dirty || !reviewer.trim() || !reason.trim()} onClick={() => { void record('return_draft') }}>Return to draft</button></div>{error && <div className="monitor-errors" role="alert">{error}</div>}
      <details className="outreach-review-members"><summary>Inspect exact recipient IDs ({memberCount})</summary><p>{scoped.flatMap(g => g.recipientIds).join(', ')}</p></details>
    </div><div><ChannelPreview input={version.input} group={group ?? groups[0]} /><div className="outreach-group-decisions"><h3>Current group reviews</h3>{groups.slice(0, 12).map(g => <div key={g.key}><span>{g.label} · {g.language}</span><strong>{groupDecision(campaign, g.key)?.action === 'approve_demo' ? 'Demo approval · no delivery authority' : 'Review needed'}</strong></div>)}{groups.length > 12 && <small>Choose a specific scope above to inspect the remaining groups.</small>}</div></div></div>
    <section className="outreach-audit-history"><h3>Decision history</h3>{!campaign.decisions.length && <p>No local review decisions yet.</p>}{campaign.decisions.slice().reverse().map(d => <article key={d.id}><strong>{d.action.replaceAll('_', ' ')} · version {d.version}</strong><p>{d.reason}</p><small>{d.reviewer} · {formatDate(d.at)} · {d.recipientIds.length} recipients · {d.versionDigest === version.digest ? 'Current version' : 'Previous version — does not apply to current content'}</small><span>Local demonstration only · not valid for delivery</span></article>)}</section>
  </section>
}
