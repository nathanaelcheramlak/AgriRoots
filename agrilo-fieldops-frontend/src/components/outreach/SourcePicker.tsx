import { useFieldOps } from '../../state/useFieldOps'
import { exampleSource, generateGuidance, officerSource } from '../../features/outreach/catalog'
import type { AdvisorySource, CampaignInput } from '../../features/outreach/types'
import { mapFarmRecipients } from '../../features/outreach/recipients'
import { Field } from './OutreachUi'
export function SourcePicker({ input, onChange }: { input: CampaignInput; onChange: (value: CampaignInput) => void }) {
  const home = useFieldOps()
  const choose = (id: string) => {
    let source: AdvisorySource
    if (id === 'officer') source = officerSource()
    else if (id === 'material') source = { ...officerSource(), id: 'OFFICER-MATERIAL', kind: 'material', title: 'Officer-supplied reference · approval unverified' }
    else if (id.startsWith('advisory:')) {
      const advisory = home.drafts.find(d => d.id === id.slice(9)); if (!advisory) return
      source = { id: advisory.id, kind: 'advisory', mode: 'synthetic', title: 'Local advisory draft · ' + advisory.farmId, contextId: advisory.id, farmIds: [advisory.farmId], evidence: advisory.evidence.slice(0, 100).map(e => ({ id: e.id, title: e.variable, source: e.provider, observedAt: e.observedAt ?? '', capturedAt: new Date().toISOString(), availability: e.status === 'available' ? 'available' : e.status === 'unavailable' ? 'unavailable' : 'partial', summary: String(e.value ?? 'Unavailable') + ' ' + (e.unit ?? ''), limitations: e.details, mode: 'synthetic' })), limitations: ['Local advisory and review only; not an authenticated approval.', ...advisory.missingData].slice(0, 20), originalObservation: advisory.text.slice(0, 1200), officerAssessment: '' }
    } else source = exampleSource(id as 'weekly' | 'weather' | 'health' | 'missing')
    const mapping = mapFarmRecipients(source.farmIds, source.mode === 'synthetic')
    onChange({ ...input, source, guidance: generateGuidance(input.templateId, source), selection: { ...input.selection, ids: source.farmIds.length ? mapping.ids : [], excludedIds: [], scopeFarmIds: source.farmIds } })
  }
  return <section className="outreach-source-picker"><Field label="Source of agricultural information"><select aria-label="Source of agricultural information" value="" onChange={e => choose(e.target.value)}><option value="" disabled>{input.source.title}</option><option value="officer">Officer-authored message · no findings assumed</option><option value="weekly">Synthetic farm-context records</option><option value="weather">Synthetic rainfall finding · F-001</option><option value="health">Synthetic crop-health review case · F-001</option><option value="missing">Synthetic unavailable-evidence case</option><option value="material">Officer-supplied reference material</option>{home.drafts.map(d => <option key={d.id} value={'advisory:' + d.id}>Existing local advisory · {d.farmId}</option>)}<option disabled>Home analysis · use “Prepare Farmer Guidance” on Home</option><option disabled>Monitoring findings · use “Prepare Outreach” on a result</option><option disabled>Approved source registry · backend required</option></select></Field><p className="outreach-micro-note">Changing source replaces the unsaved example draft and recipient scope. Earlier saved versions remain in history.</p>
    <div className="outreach-source-summary"><strong>{input.source.title}</strong><span>{input.source.mode === 'synthetic' ? 'Synthetic demonstration' : 'Local context · approval unverified'} · {input.source.evidence.length} source references</span>{input.source.originalObservation && <p>{input.source.originalObservation}</p>}</div>
    {input.source.kind === 'material' && <div className="outreach-material-editor"><Field label="Reference title"><input aria-label="Reference title" maxLength={160} value={input.source.title} onChange={e => onChange({ ...input, source: { ...input.source, title: e.target.value } })} /></Field><Field label="Reference text / limitations"><textarea aria-label="Reference text" rows={3} maxLength={600} value={input.source.evidence[0]?.summary ?? ''} onChange={e => onChange({ ...input, source: { ...input.source, evidence: [{ id: 'OFFICER-REFERENCE', title: input.source.title, source: 'Officer-supplied material · not independently verified', observedAt: '', capturedAt: new Date().toISOString(), availability: 'partial', summary: e.target.value, limitations: 'Approval, provenance and agronomic validity require officer and backend verification.', mode: 'local_context' }] } })} /></Field></div>}
  </section>
}
