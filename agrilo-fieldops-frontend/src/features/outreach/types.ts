import { z } from 'zod'
function localTextIsSafe(value: string) {
  if (/(?:api[_ -]?key|(?:access|refresh|id)[_ -]?token|token|password|secret)\s*[:=]\s*\S+|\bBearer\s+\S{8,}|\bsk-[\w-]{12,}|\beyJ[\w-]{12,}\.[\w-]+\.|-----BEGIN .*PRIVATE KEY|\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|\+\d[\d ()-]{7,}\d|\b(?:09|07)\d{8}\b|data\s*:\s*image\/|blob:/i.test(value)) return false
  return (value.match(/https?:\/\/[^\s<>"']+/gi) ?? []).every(candidate => { try { const url = new URL(candidate); return !url.username && !url.password && !url.search && !url.hash } catch { return false } })
}
export const safeText = (max: number) => z.string().trim().max(max).refine(localTextIsSafe, 'Remove credentials, contacts, image data and URL queries or fragments before saving.')
const required = (max: number) => safeText(max).pipe(z.string().min(1, 'This field is required.'))
const id = required(120), uuid = z.string().uuid(), digest = z.string().regex(/^[a-f0-9]{64}$/)
export const channelSchema = z.enum(['sms', 'voice', 'email', 'smartphone'])
export const languageSchema = z.enum(['en', 'am', 'om'])
export const templateSchema = z.enum(['weekly', 'weather', 'health', 'irrigation', 'inspection', 'custom'])
export const categorySchema = z.enum(['weekly', 'weather', 'health', 'management', 'inspection', 'general'])
export const evidenceSchema = z.object({ id, title: required(180), source: required(160), observedAt: safeText(40), capturedAt: z.iso.datetime(), availability: z.enum(['available', 'partial', 'unavailable']), summary: safeText(600), limitations: safeText(600), mode: z.enum(['synthetic', 'local_context']), farmIds: z.array(id).max(100).optional() }).strict()
export const sourceSchema = z.object({
  id, kind: z.enum(['home', 'monitoring', 'crop_case', 'advisory', 'officer', 'material']), mode: z.enum(['synthetic', 'local_context']),
  recipientContext: z.enum(['synthetic', 'unresolved']).optional(),
  title: required(160), contextId: id.optional(), version: z.number().int().positive().optional(), farmIds: z.array(id).max(100),
  evidence: z.array(evidenceSchema).max(100), limitations: z.array(safeText(500)).max(20),
  originalObservation: safeText(1200), officerAssessment: safeText(1200),
}).strict()
export const filterSchema = z.object({ search: safeText(100), crop: safeText(60), location: safeText(80), risk: safeText(30), stage: safeText(60), irrigation: safeText(30), monitoring: safeText(40), language: z.enum(['', 'en', 'am', 'om']), channel: z.enum(['', 'sms', 'voice', 'email', 'smartphone']) }).strict()
const recipientId = z.string().regex(/^DEMO-P\d{4}$/, 'Choose a known demonstration recipient.')
export const selectionSchema = z.object({
  mode: z.enum(['individual', 'selected', 'map', 'filtered', 'all_demo']), ids: z.array(recipientId).min(1, 'Select at least one farmer.').max(2000),
  excludedIds: z.array(recipientId).max(2000), filters: filterSchema, scopeFarmIds: z.array(id).max(100), label: required(160),
}).strict().superRefine((v, ctx) => {
  if (new Set(v.ids).size !== v.ids.length || new Set(v.excludedIds).size !== v.excludedIds.length || v.excludedIds.some(id => !v.ids.includes(id))) ctx.addIssue({ code: 'custom', message: 'Recipient scope contains duplicates or invalid exclusions.' })
  if (!v.ids.some(id => !v.excludedIds.includes(id))) ctx.addIssue({ code: 'custom', message: 'At least one selected farmer must remain in scope.' })
  if (v.mode === 'individual' && v.ids.length !== 1) ctx.addIssue({ code: 'custom', message: 'Individual mode requires exactly one farmer.' })
  if (v.mode === 'map' && !v.scopeFarmIds.length) ctx.addIssue({ code: 'custom', message: 'Import a farm selection from Home or Monitoring.' })
})
export const channelConfigSchema = z.object({ channel: channelSchema, fallback: z.enum(['none', 'manual_review']), language: z.enum(['preferred', 'en', 'am', 'om']), followUpDate: z.string().max(10).refine(v => !v || (/^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v), 'Choose a valid follow-up date.') }).strict()
export const actionSchema = z.object({ id: uuid, window: required(160), description: required(500), originalDescription: safeText(500), reason: required(500), evidenceIds: z.array(id).max(100), cautions: safeText(600), reviewStatus: z.enum(['draft', 'officer_edited']) }).strict()
export const correctionSchema = z.object({ id: uuid, originalObservation: safeText(1200), assessment: required(1200), reason: required(500), reviewer: required(80), at: z.iso.datetime() }).strict()
export const overrideSchema = z.object({ groupKey: required(240), body: required(4000), subject: safeText(160), language: languageSchema, languageReviewed: z.boolean() }).strict()
export const guidanceSchema = z.object({
  origin: z.enum(['deterministic_example', 'officer_authored']), originalText: safeText(4000), body: safeText(4000), subject: safeText(160),
  actions: z.array(actionSchema).max(7), corrections: z.array(correctionSchema).max(20), groupOverrides: z.array(overrideSchema).max(100),
  unsupported: z.boolean(), unsupportedReason: safeText(500),
}).strict()
export const campaignInputSchema = z.object({
  name: required(120), description: safeText(600), category: categorySchema, templateId: templateSchema, instructions: safeText(1200),
  source: sourceSchema, selection: selectionSchema, communication: channelConfigSchema, guidance: guidanceSchema,
}).strict().superRefine((v, ctx) => {
  if (v.guidance.unsupported && !v.guidance.unsupportedReason) ctx.addIssue({ code: 'custom', path: ['guidance'], message: 'Describe the unsupported recommendation.' })
  if (new Set(v.guidance.groupOverrides.map(g => g.groupKey)).size !== v.guidance.groupOverrides.length) ctx.addIssue({ code: 'custom', path: ['guidance'], message: 'Each group can have only one message override.' })
  const evidenceIds = v.source.evidence.map(e => e.id)
  if (v.guidance.actions.some(a => a.evidenceIds.some(id => !evidenceIds.includes(id)))) ctx.addIssue({ code: 'custom', path: ['guidance'], message: 'An action refers to evidence outside this source snapshot.' })
})
export const eligibilityReasons = ['eligible', 'opted_out', 'contact_unavailable', 'consent_missing', 'needs_review', 'conflicting_record', 'language_mismatch', 'excluded_by_officer'] as const
export const snapshotSchema = z.object({ id: uuid, datasetVersion: z.literal('outreach-demo-v1'), memberIds: z.array(recipientId).max(2000), eligibleIds: z.array(recipientId).max(2000), excluded: z.array(z.object({ recipientId, reason: z.enum(eligibilityReasons) }).strict()).max(2000), capturedAt: z.iso.datetime(), digest }).strict()
export const versionSchema = z.object({ number: z.number().int().positive(), at: z.iso.datetime(), input: campaignInputSchema, snapshot: snapshotSchema, digest, previousDigest: z.union([z.literal(''), digest]), reason: required(500), editor: required(80) }).strict()
export const reviewSchema = z.object({ id: uuid, version: z.number().int().positive(), versionDigest: digest, snapshotDigest: digest, groupKey: required(240), recipientIds: z.array(recipientId).max(2000), channel: channelSchema, action: z.enum(['submit_review', 'approve_demo', 'reject', 'request_evidence', 'return_draft']), reviewer: required(80), reason: required(600), at: z.iso.datetime(), authority: z.literal('local_demo') }).strict()
export const campaignSchema = z.object({ id: uuid, createdAt: z.iso.datetime(), archived: z.boolean(), owner: z.literal('this_device'), versions: z.array(versionSchema).min(1).max(20), decisions: z.array(reviewSchema).max(200) }).strict()
export const followUpSchema = z.object({ id: uuid, responseId: z.enum(['SAMPLE-RESPONSE-1', 'SAMPLE-RESPONSE-2', 'SAMPLE-RESPONSE-3']), version: z.number().int().positive(), kind: z.enum(['draft_response', 'request_information', 'needs_inspection', 'crop_case']), note: required(1600), reviewer: required(80), updatedAt: z.iso.datetime(), mode: z.literal('local_demo') }).strict()
export const documentSchema = z.object({ version: z.literal(1), campaigns: z.array(campaignSchema).max(25), followUps: z.array(followUpSchema).max(100) }).strict()
export type CommunicationChannel = z.infer<typeof channelSchema>
export type Language = z.infer<typeof languageSchema>
export type EvidenceReference = z.infer<typeof evidenceSchema>
export type AdvisorySource = z.infer<typeof sourceSchema>
export type RecipientFilters = z.infer<typeof filterSchema>
export type RecipientSelection = z.infer<typeof selectionSchema>
export type CommunicationPreference = { language: Language; preferred: CommunicationChannel; available: CommunicationChannel[]; consent: Record<CommunicationChannel, 'granted' | 'missing' | 'opted_out'> }
export interface RecipientFarmAssociation { farmId: string; crop: string; location: string; risk: string; stage: string; irrigation: string; monitoring: 'flagged' | 'not_assessed'; evidenceAvailable: boolean }
export interface Recipient { id: string; displayName: string; farms: RecipientFarmAssociation[]; preference: CommunicationPreference; recordState: 'consistent' | 'needs_review' | 'conflict'; optedOut: boolean; mode: 'synthetic' }
export type RecipientEligibility = { eligible: boolean; reason: typeof eligibilityReasons[number] }
export type RecipientSnapshot = z.infer<typeof snapshotSchema>
export interface RecipientGroup { key: string; label: string; recipientIds: string[]; language: Language; crop: string; irrigation: string; holdReasons: string[] }
export type WeeklyAction = z.infer<typeof actionSchema>
export type OfficerCorrection = z.infer<typeof correctionSchema>
export type GuidanceDraft = z.infer<typeof guidanceSchema>
export type MessageTemplate = Pick<GuidanceDraft, 'body' | 'subject'>
export type PersonalizationRule = { variable: 'farmer_name' | 'crop' | 'farm' | 'location' | 'follow_up_date'; source: 'recipient_snapshot' | 'officer_date' }
export type CampaignInput = z.infer<typeof campaignInputSchema>
export type CampaignVersion = z.infer<typeof versionSchema>
export type ReviewDecision = z.infer<typeof reviewSchema>
export type OutreachCampaign = z.infer<typeof campaignSchema>
export type CampaignStatus = 'draft' | 'awaiting_review' | 'demo_reviewed' | 'changes_requested' | 'rejected' | 'archived'
export type OutreachFollowUp = z.infer<typeof followUpSchema>
export interface DeliveryBatch { id: string; mode: 'synthetic'; campaign: string; channel: CommunicationChannel; version: number; snapshotId: string; intendedIds: string[] }
export interface DeliveryAttempt { id: string; batchId: string; recipientId: string; at: string; status: 'queued' | 'submitted' | 'delivered' | 'failed' | 'unknown' | 'cancelled'; detail: string; mode: 'synthetic' }
export interface FarmerResponse { id: OutreachFollowUp['responseId']; recipientId: string; farmId: string; campaignLabel: string; channel: CommunicationChannel; at: string; text: string; attachment: string | null; caseId: string; assignedOfficer: string | null; mode: 'synthetic' }
export const channelLabels = { sms: 'SMS', voice: 'Voice', email: 'Email', smartphone: 'Smartphone messaging' }
export const languageLabels = { en: 'English', am: 'Amharic', om: 'Afaan Oromoo' }
export const categoryLabels = { weekly: 'Weekly guidance', weather: 'Weather advisory', health: 'Crop health', management: 'Farm management', inspection: 'Follow-up inspection', general: 'General information' }
export const statusLabels: Record<CampaignStatus, string> = { draft: 'Draft', awaiting_review: 'Awaiting demo review', demo_reviewed: 'Demo review recorded', changes_requested: 'More evidence requested', rejected: 'Rejected locally', archived: 'Archived locally' }
export const eligibilityLabels: Record<RecipientEligibility['reason'], string> = { eligible: 'Eligible in demo', opted_out: 'Opted out', contact_unavailable: 'Contact unavailable', consent_missing: 'Consent missing', needs_review: 'Record needs review', conflicting_record: 'Conflicting contact record', language_mismatch: 'Language preference mismatch', excluded_by_officer: 'Excluded by officer' }
