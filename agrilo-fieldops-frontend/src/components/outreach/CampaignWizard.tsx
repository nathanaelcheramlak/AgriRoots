import { useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, Users } from 'lucide-react'
import { PluginModal } from '../plugins/PluginModal'
import { campaignTemplates, newCampaignInput } from '../../features/outreach/catalog'
import { campaignInputSchema, categoryLabels, channelLabels } from '../../features/outreach/types'
import type { CampaignInput, OutreachCampaign } from '../../features/outreach/types'
import { groupRecipients, resolveRecipients } from '../../features/outreach/recipients'
import { reviewWarnings } from '../../features/outreach/messages'
import { latestVersion } from '../../features/outreach/service'
import { outreachService, useOutreach } from '../../features/outreach/store'
import { Field, LocalNotice, OutreachIcon } from './OutreachUi'
import { SourcePicker } from './SourcePicker'
import { RecipientPicker } from './RecipientPicker'
import { ChannelSelector } from './ChannelPreview'
import { GuidanceEditor, GroupInspector } from './GuidanceEditor'
const steps = ['Purpose', 'Recipients', 'Channels', 'Guidance', 'Groups', 'Review']
const fields = [['name', 'description', 'category', 'templateId', 'instructions', 'source'], ['selection'], ['communication'], ['guidance'], []]
export function CampaignWizard({ initial, existing, origin, unmapped, onClose, onSaved }: { initial?: CampaignInput; existing?: OutreachCampaign; origin?: string; unmapped?: string[]; onClose: () => void; onSaved: (campaign: OutreachCampaign) => void }) {
  const state = useOutreach(), previous = existing ? latestVersion(existing) : undefined
  const [input, setInput] = useState<CampaignInput>(() => structuredClone(previous?.input ?? initial ?? newCampaignInput())), [step, setStep] = useState(0), [furthest, setFurthest] = useState(existing ? 5 : 0)
  const [errors, setErrors] = useState<string[]>([]), [busy, setBusy] = useState(false), [editGroup, setEditGroup] = useState<string>(), body = useRef<HTMLDivElement>(null), navigation = useRef<HTMLElement>(null)
  const update = <K extends keyof CampaignInput>(key: K, value: CampaignInput[K]) => setInput(p => ({ ...p, [key]: value }))
  const move = (next: number) => { setStep(next); setErrors([]); requestAnimationFrame(() => { body.current?.querySelector<HTMLElement>('h3')?.focus(); navigation.current?.querySelector<HTMLElement>('[aria-current="step"]')?.scrollIntoView({ block: 'nearest', inline: 'center' }) }) }
  const advance = () => {
    const result = campaignInputSchema.safeParse(input), issues = result.success ? [] : result.error.issues.filter(i => fields[step]?.includes(String(i.path[0])))
    if (step === 3 && !input.guidance.body.trim()) { setErrors(['Write a shared message before continuing.']); return }
    if (issues.length) { setErrors([...new Set(issues.map(i => i.message))]); return }
    setFurthest(Math.max(furthest, step + 1)); move(step + 1)
  }
  const save = async () => {
    const parsed = campaignInputSchema.safeParse(input)
    if (!parsed.success) { setErrors([...new Set(parsed.error.issues.map(i => i.message))]); return }
    setBusy(true); setErrors([])
    try { const campaign = existing && previous ? await outreachService.update(existing.id, previous.number, parsed.data, 'Campaign configuration edited; scope and content require a new review.', 'Local officer · identity unverified') : await outreachService.create(parsed.data); await state.refresh(); state.notify('Campaign saved locally. No delivery was requested.'); onSaved(campaign) }
    catch (e) { setErrors([e instanceof Error ? e.message : 'Could not save this local campaign.']); setBusy(false) }
  }
  const groups = groupRecipients(input), records = resolveRecipients(input), eligible = records.filter(r => r.eligibility.eligible).length
  return <PluginModal title={existing ? 'Edit campaign' : 'New Campaign'} wide onClose={onClose}>
    <div className="outreach-wizard"><nav className="outreach-wizard-steps" ref={navigation} aria-label="Campaign setup steps">{steps.map((name, i) => <button type="button" key={name} disabled={busy || i > furthest} aria-current={step === i ? 'step' : undefined} onClick={() => move(i)}><span>{i < step ? <Check size={12} /> : i + 1}</span>{name}</button>)}</nav>
    <div className={'outreach-wizard-layout ' + (step === 3 || step === 4 ? 'wide-step' : '')}><div className="outreach-wizard-body" ref={body}><div className="outreach-step-heading"><small>STEP {step + 1} OF 6{origin && ' · FROM ' + origin.toUpperCase()}</small><h3 tabIndex={-1}>{['Give the campaign a clear purpose', 'Choose farmers and inspect their eligibility', 'Prepare the right communication format', 'Review the evidence and improve the wording', 'Inspect personalized groups and exceptions', 'Save a precise local draft'][step]}</h3></div>
        {!!errors.length && <div className="monitor-errors" role="alert"><strong>Check the campaign</strong><ul>{errors.map(e => <li key={e}>{e}</li>)}</ul></div>}
        <div className="outreach-step-content">
          {step === 0 && <><Field label="Campaign template"><select aria-label="Campaign template" value={input.templateId} onChange={e => setInput(newCampaignInput(e.target.value as CampaignInput['templateId']))}>{campaignTemplates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field><Field label="Campaign name"><input aria-label="Campaign name" maxLength={120} value={input.name} onChange={e => update('name', e.target.value)} placeholder="Weekly maize farmer guidance" /></Field><div className="monitor-form-grid"><Field label="Campaign category"><select aria-label="Campaign category" value={input.category} onChange={e => update('category', e.target.value as CampaignInput['category'])}>{Object.entries(categoryLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></Field><Field label="Description"><textarea aria-label="Campaign description" rows={2} maxLength={600} value={input.description} onChange={e => update('description', e.target.value)} /></Field></div><SourcePicker input={input} onChange={setInput} /><Field label="Officer instructions (optional)"><textarea aria-label="Campaign instructions" rows={2} maxLength={1200} value={input.instructions} onChange={e => update('instructions', e.target.value)} /><small>Planning notes only. No AI request or executable workflow is created.</small></Field></>}
          {step === 1 && <>{!!unmapped?.length && <div className="monitor-errors" role="status">No authorized contact mapping for: {unmapped.join(', ')}. No recipients were invented for these farm references.</div>}<RecipientPicker input={input} onChange={setInput} /></>}
          {step === 2 && <ChannelSelector input={input} onChange={setInput} />}
          {step === 3 && <GuidanceEditor key={editGroup ?? 'base'} input={input} onChange={setInput} initialGroupKey={editGroup} />}
          {step === 4 && <GroupInspector input={input} onEditGroup={key => { setEditGroup(key); move(3) }} />}
          {step === 5 && <div className="outreach-final-summary"><LocalNotice /><h4>{input.name}</h4><p>{input.description}</p><dl><div><dt>Recipient snapshot</dt><dd>{input.selection.ids.length.toLocaleString()} selected farmers · {eligible.toLocaleString()} eligible in demo · {records.length - eligible} excluded or requiring contact review<small>{input.selection.scopeFarmIds.length ? input.selection.scopeFarmIds.length + ' imported farm references; no scope expansion' : 'Concrete selected IDs; future filter changes cannot add people automatically'}</small></dd></div><div><dt>Source</dt><dd>{input.source.title}<small>{input.source.mode === 'synthetic' ? 'Synthetic evidence' : 'Local context · unverified'} · {input.source.evidence.length} references</small></dd></div><div><dt>Communication</dt><dd>{channelLabels[input.communication.channel]} · Not configured<small>Language: {input.communication.language} · fallback: {input.communication.fallback.replaceAll('_', ' ')} · no costs or delivery integration</small></dd></div><div><dt>Message & groups</dt><dd>{input.guidance.body.length} characters in shared template · {groups.length} eligible advisory groups<small>{groups.filter(g => reviewWarnings(g, input).length).length} groups held for evidence, translation or wording review</small></dd></div><div><dt>Human review</dt><dd>Draft creation is not permission to send. Demo decisions will bind to this exact version, message, variables, recipient snapshot and channel.</dd></div></dl><details><summary>Inspect shared message</summary><p className="outreach-whitespace">{input.guidance.body}</p></details><details><summary>Inspect source limitations</summary>{input.source.limitations.map((s, i) => <p key={i}>{s}</p>)}</details></div>}
        </div>
      </div>{step !== 3 && step !== 4 && <aside className="outreach-wizard-summary"><OutreachIcon template={input.templateId} size={27} /><small>CAMPAIGN DRAFT</small><h4>{input.name || 'Untitled campaign'}</h4><p>{categoryLabels[input.category]}</p><dl><div><dt>Selected farmers</dt><dd>{input.selection.ids.length.toLocaleString()}</dd></div><div><dt>Eligible in demo</dt><dd>{eligible.toLocaleString()}</dd></div><div><dt>Advisory groups</dt><dd>{groups.length}</dd></div><div><dt>Channel</dt><dd>{channelLabels[input.communication.channel]} · not configured</dd></div></dl><span>Review first.<br />No external communication.</span></aside>}</div>
      <footer className="outreach-wizard-footer"><button type="button" className="plugin-secondary" disabled={busy} onClick={step ? () => move(step - 1) : onClose}>{step ? <><ArrowLeft size={14} />Back</> : 'Cancel'}</button><span><Users size={13} />{input.selection.ids.length.toLocaleString()} selected · {eligible.toLocaleString()} eligible</span>{step < 5 ? <button type="button" className="monitor-primary" onClick={advance}>Continue<ArrowRight size={14} /></button> : <button type="button" className="monitor-primary" disabled={busy} onClick={() => { void save() }}>{busy ? 'Saving…' : 'Save local campaign'}<Check size={14} /></button>}</footer>
    </div>
  </PluginModal>
}
