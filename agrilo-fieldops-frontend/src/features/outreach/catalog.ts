import type { AdvisorySource, CampaignInput, GuidanceDraft, WeeklyAction } from './types'
import { emptyRecipientFilters } from './recipients'
export const campaignTemplates: { id: CampaignInput['templateId']; name: string; description: string; category: CampaignInput['category']; icon: 'calendar' | 'rain' | 'leaf' | 'water' | 'visit' | 'custom' }[] = [
  { id: 'weekly', name: 'Weekly Farm Guidance', description: 'Prepare practical weekly actions from available farm context and reviewed evidence.', category: 'weekly', icon: 'calendar' },
  { id: 'weather', name: 'Weather & Rainfall Advisory', description: 'Prepare a location-relevant draft and explain weather-data limitations.', category: 'weather', icon: 'rain' },
  { id: 'health', name: 'Crop Health Follow-up', description: 'Review an uncertain crop observation and request useful follow-up.', category: 'health', icon: 'leaf' },
  { id: 'irrigation', name: 'Irrigation Guidance', description: 'Prepare a review request about soil moisture and documented water access.', category: 'management', icon: 'water' },
  { id: 'inspection', name: 'Field Inspection Request', description: 'Arrange a review, field observation, or clearer crop photograph.', category: 'inspection', icon: 'visit' },
  { id: 'custom', name: 'Custom Campaign', description: 'Compose an officer-authored message for a carefully selected scope.', category: 'general', icon: 'custom' },
]
export function exampleSource(kind: 'weekly' | 'weather' | 'health' | 'missing' = 'weekly'): AdvisorySource {
  return { id: 'SAMPLE-SOURCE-' + kind, kind: kind === 'health' ? 'crop_case' : 'monitoring', mode: 'synthetic', title: kind === 'health' ? 'Illustrated crop-health review case' : kind === 'weather' ? 'Sample rainfall warning · F-001' : kind === 'missing' ? 'Missing agricultural evidence' : 'Demonstration farm-context records', contextId: 'SAMPLE-' + kind, version: 1, farmIds: kind === 'weather' || kind === 'health' ? ['F-001'] : [],
    originalObservation: kind === 'health' ? 'Sample model-style observation: possible leaf disease. Unconfirmed illustration only; no diagnostic tool was executed.' : '', officerAssessment: '',
    evidence: [{ id: 'SAMPLE-EVIDENCE-' + kind, title: kind === 'weather' ? 'Rainfall deficit · illustrative 25% vs seasonal sample reference' : kind === 'health' ? 'Original crop illustration · possible colour difference' : kind === 'missing' ? 'Required soil and observation records unavailable' : 'Crop, irrigation and risk metadata from synthetic records', source: 'AgriLo deterministic demonstration', observedAt: '2026-11-15', capturedAt: '2026-11-16T05:02:00.000Z', availability: kind === 'missing' ? 'unavailable' : 'partial', summary: kind === 'health' ? 'A possible observation for officer correction, never a confirmed diagnosis.' : kind === 'weather' ? 'A fixed sample threshold match for F-001 only. Not a current weather observation.' : kind === 'missing' ? 'No comparable agricultural evidence supplied.' : 'Illustrative context for demonstrating grouping and requests for observation, not prescriptive advice.', limitations: 'Synthetic fixture. No provider call, LLM generation, field measurement or diagnosis.', mode: 'synthetic' }],
    limitations: ['Fixed demonstration only; not current field conditions.', 'Qualified officer review is required. No validated application rates, irrigation quantities or diagnoses.'] }
}
export function officerSource(): AdvisorySource { return { id: 'OFFICER-AUTHORED', kind: 'officer', mode: 'local_context', title: 'Officer-authored message', farmIds: [], evidence: [], limitations: ['No agricultural findings supplied. Compose informational wording and provide supporting evidence before consequential advice.'], originalObservation: '', officerAssessment: '' } }
export function generateGuidance(templateId: CampaignInput['templateId'], source: AdvisorySource): GuidanceDraft {
  const manual = source.kind === 'officer' || source.kind === 'material'
  const bodies: Record<CampaignInput['templateId'], string> = {
    weekly: 'Hello {{farmer_name}}, during your next safe visit to {{farm}}, record field moisture and any new crop symptoms. Share observations with your extension officer before making management changes.',
    weather: 'Hello {{farmer_name}}, please check field moisture at {{farm}} when it is safe and share what you observe. Ask your extension officer to verify local weather and field conditions before changing farm management.',
    health: 'Hello {{farmer_name}}, the cause of the visible concern at {{farm}} is not confirmed. Please provide a clear image of the affected leaves and surrounding plants through an authorized channel, or arrange an officer visit.',
    irrigation: 'Hello {{farmer_name}}, please ask your extension officer to verify crop stage, soil moisture and water availability at {{farm}} before changing irrigation. Record observations during your next safe field check.',
    inspection: 'Hello {{farmer_name}}, please contact your extension officer to arrange a safe visit to {{farm}} or share a clearer crop observation through an authorized channel.',
    custom: '',
  }
  const body = manual ? '' : bodies[templateId], evidenceIds = source.evidence.filter(e => e.availability !== 'unavailable').map(e => e.id)
  const plans = templateId === 'weekly' && !manual ? [
    ['Monday · next safe routine check', 'Inspect field moisture and note unusual dryness.', 'Record observations for officer assessment; do not infer an irrigation amount.'],
    ['Wednesday · when safely accessible', 'Check crop leaves and record new visible symptoms.', 'Observations help decide whether a field examination is needed; they do not confirm a diagnosis.'],
    ['Friday · if an authorized channel is available', 'Share an updated crop photograph or contact the officer.', 'Supply comparable observations for follow-up, with lighting and angle limitations.'],
  ] : []
  const actions: WeeklyAction[] = plans.map(([window, description, reason], i) => ({ id: '20000000-0000-4000-8000-00000000000' + (i + 1), window, description, originalDescription: description, reason, evidenceIds, cautions: 'Illustrative observation request only. Follow-up depends on safe access and an approved submission channel.', reviewStatus: 'draft' }))
  return { origin: manual ? 'officer_authored' : 'deterministic_example', originalText: body, body, subject: templateId === 'custom' ? '' : campaignTemplates.find(t => t.id === templateId)!.name, actions, corrections: source.officerAssessment ? [{ id: crypto.randomUUID(), originalObservation: source.originalObservation, assessment: source.officerAssessment, reason: 'Officer notes transferred from Monitoring for further review.', reviewer: 'Local officer notes · identity unverified', at: new Date().toISOString() }] : [], groupOverrides: [], unsupported: false, unsupportedReason: '' }
}
export function newCampaignInput(templateId: CampaignInput['templateId'] = 'custom'): CampaignInput {
  const t = campaignTemplates.find(t => t.id === templateId)!, source = templateId === 'custom' ? officerSource() : exampleSource(templateId === 'health' ? 'health' : templateId === 'weather' ? 'weather' : 'weekly')
  return { name: templateId === 'custom' ? '' : t.name, description: t.description, category: t.category, templateId, instructions: '', source,
    selection: { mode: 'selected', ids: [], excludedIds: [], filters: { ...emptyRecipientFilters }, scopeFarmIds: source.farmIds, label: 'Selected synthetic farmers' },
    communication: { channel: 'sms', fallback: 'none', language: 'preferred', followUpDate: '' }, guidance: generateGuidance(templateId, source) }
}
export const outreachScenarios = [
  { id: 'weekly', name: 'Weekly plans & groups', detail: 'Different crops, irrigation conditions and evidence gaps.', template: 'weekly' },
  { id: 'weather', name: 'Rainfall follow-up', detail: 'A source-linked threshold example for one sample farm.', template: 'weather' },
  { id: 'health', name: 'Crop observation correction', detail: 'Preserve the original and write an officer assessment.', template: 'health' },
  { id: 'large', name: '2,000 synthetic farmers', detail: 'Page, filter, select and group a large demonstration population.', template: 'weekly' },
  { id: 'missing', name: 'Insufficient evidence', detail: 'Hold unsupported guidance for additional investigation.', template: 'weekly' },
  { id: 'constraints', name: 'Consent & contact limits', detail: 'Inspect opt-outs, missing consent and contact conflicts.', template: 'inspection' },
] as const
