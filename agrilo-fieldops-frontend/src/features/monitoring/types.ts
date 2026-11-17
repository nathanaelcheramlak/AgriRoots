import { z } from 'zod'
import { selectionSchema } from '../../api/schemas'

const text = (max: number) => z.string().trim().max(max).refine(v => !/(?:api[_ -]?key|(?:access|refresh|id)[_ -]?token|token|password|secret)\s*[:=]\s*\S+|\bBearer\s+\S{8,}|\bsk-[\w-]{12,}|\beyJ[\w-]{12,}\.[\w-]+\.|-----BEGIN .*PRIVATE KEY/i.test(v), 'Remove credentials or tokens before saving.')
const required = (max: number) => text(max).pipe(z.string().min(1, 'This field is required.'))
export const categorySchema = z.enum(['environment', 'crop_health', 'report'])
export const capabilityIds = ['weather', 'rainfall', 'soil', 'satellite', 'crop_health', 'pests', 'crop_calendar', 'markets'] as const
export const metricIds = ['rainfall_deficit', 'vegetation_decline', 'temperature', 'missing_photos', 'reported_symptoms', 'health_change'] as const
export const outputIds = ['summary', 'report', 'trends', 'priority_list', 'alert', 'farmer_feedback', 'advisory', 'inspection'] as const
export const severitySchema = z.enum(['info', 'warning', 'high', 'unknown'])
export const farmReferenceSchema = z.object({ id: required(100), name: required(120), crop: required(80), source: z.enum(['synthetic', 'home']) }).strict()
export const monitorScopeSchema = z.object({
  type: z.enum(['home_selection', 'specific', 'saved_area', 'group']), label: required(120),
  farms: z.array(farmReferenceSchema).min(1, 'Choose at least one farm.').max(100),
  selection: selectionSchema.optional(), groupId: text(100).optional(),
}).strict().superRefine((v, ctx) => {
  if (new Set(v.farms.map(f => f.id)).size !== v.farms.length) ctx.addIssue({ code: 'custom', path: ['farms'], message: 'Choose each farm only once.' })
  if ((v.type === 'home_selection' || v.type === 'saved_area') && !v.selection) ctx.addIssue({ code: 'custom', path: ['selection'], message: 'A geographic selection is required.' })
  if (v.type === 'group' && !v.groupId) ctx.addIssue({ code: 'custom', path: ['groupId'], message: 'Choose a named farm group.' })
})
const date = z.string().regex(/^\d{4}-\d{2}-\d{2}$/, 'Choose a date.').refine(v => { const d = new Date(v + 'T00:00:00Z'); return !Number.isNaN(d.valueOf()) && d.toISOString().slice(0, 10) === v }, 'Choose a valid date.')
export const monitorScheduleSchema = z.object({
  frequency: z.enum(['daily', 'weekly', 'monthly']), time: z.string().regex(/^([01]\d|2[0-3]):[0-5]\d$/, 'Choose a valid time.'),
  weekday: z.number().int().min(0).max(6), monthDay: z.number().int().min(1).max(28),
  timezone: z.string().max(80).refine(v => { try { new Intl.DateTimeFormat('en', { timeZone: v }); return true } catch { return false } }, 'Enter a valid IANA timezone, for example Africa/Addis_Ababa.'),
  startDate: date, endDate: z.union([z.literal(''), date]), reviewDate: z.union([z.literal(''), date]),
}).strict().superRefine((v, ctx) => {
  if (v.endDate && v.endDate < v.startDate) ctx.addIssue({ code: 'custom', path: ['endDate'], message: 'End date must be on or after the start date.' })
  if (v.reviewDate && (v.reviewDate < v.startDate || (v.endDate && v.reviewDate > v.endDate))) ctx.addIssue({ code: 'custom', path: ['reviewDate'], message: 'Review date must fall within the configured dates.' })
})
export const thresholdSchema = z.object({ value: z.number().finite(), unit: z.enum(['%', '°C', 'submissions', 'reports']), reference: z.enum(['seasonal_demo', 'recent_demo', 'weekly_demo', 'comparable_demo', 'custom']), referenceNote: text(240) }).strict()
export const ruleSchema = z.object({
  id: z.string().uuid(), metric: z.enum(metricIds), operator: z.enum(['gte', 'gt', 'lte', 'lt', 'eq']), threshold: thresholdSchema,
  scope: z.enum(['all', 'crop', 'farms']), crop: text(80), farmIds: z.array(required(100)).max(100),
  consecutiveChecks: z.number().int().min(1).max(30), severity: severitySchema,
  action: z.enum(['flag_report', 'officer_review', 'inspection']),
}).strict().superRefine((r, ctx) => {
  const spec = metricSpecs[r.metric]
  if (r.threshold.unit !== spec.unit || r.threshold.value < spec.min || r.threshold.value > spec.max || (spec.integer && !Number.isInteger(r.threshold.value))) ctx.addIssue({ code: 'custom', path: ['threshold', 'value'], message: 'Use ' + spec.min + '–' + spec.max + ' ' + spec.unit + (spec.integer ? ' in whole numbers.' : '.') })
  if (r.scope === 'crop' && !r.crop) ctx.addIssue({ code: 'custom', path: ['crop'], message: 'Choose a crop.' })
  if (r.scope === 'farms' && !r.farmIds.length) ctx.addIssue({ code: 'custom', path: ['farmIds'], message: 'Choose at least one farm for this rule.' })
  if (r.threshold.reference === 'custom' && !r.threshold.referenceNote) ctx.addIssue({ code: 'custom', path: ['threshold', 'referenceNote'], message: 'Describe the reference period or baseline.' })
})
export const monitorInputSchema = z.object({
  name: required(100), description: text(600), instructions: text(1200), category: categorySchema,
  templateId: z.enum(['weather', 'report', 'photos', 'satellite', 'custom']), scope: monitorScopeSchema,
  capabilityIds: z.array(z.enum(capabilityIds)).min(1, 'Choose at least one example capability.').max(8),
  schedule: monitorScheduleSchema, combination: z.enum(['all', 'any']), rules: z.array(ruleSchema).max(12),
  outputs: z.array(z.enum(outputIds)).min(1, 'Choose at least one output.').max(8),
}).strict().superRefine((v, ctx) => {
  if (new Set(v.capabilityIds).size !== v.capabilityIds.length || new Set(v.outputs).size !== v.outputs.length) ctx.addIssue({ code: 'custom', message: 'Choose each capability and output only once.' })
  if (new Set(v.rules.map(r => r.id)).size !== v.rules.length) ctx.addIssue({ code: 'custom', path: ['rules'], message: 'Rule IDs must be unique.' })
  for (const [i, r] of v.rules.entries()) {
    if (!v.capabilityIds.includes(metricSpecs[r.metric].capability)) ctx.addIssue({ code: 'custom', path: ['rules', i], message: 'Select the ' + metricSpecs[r.metric].capability + ' capability for this rule.' })
    if (r.farmIds.some(id => !v.scope.farms.some(f => f.id === id))) ctx.addIssue({ code: 'custom', path: ['rules', i], message: 'A rule refers to a farm outside this monitor.' })
    if (r.scope === 'crop' && !v.scope.farms.some(f => f.crop === r.crop)) ctx.addIssue({ code: 'custom', path: ['rules', i], message: 'Choose a crop that exists in the monitor scope.' })
  }
})
export const monitorDefinitionSchema = z.object({
  id: z.string().uuid(), version: z.number().int().positive(), input: monitorInputSchema,
  configurationStatus: z.enum(['draft', 'paused']), createdAt: z.iso.datetime(), updatedAt: z.iso.datetime(), owner: z.literal('this_device'),
}).strict()
export const decisionSchema = z.object({
  id: z.string().uuid(), feedbackVersion: z.number().int().positive(), action: z.enum(['save_later', 'approve_demo', 'reject', 'inspection']),
  reviewer: required(80), at: z.iso.datetime(), authority: z.literal('local_demo'),
}).strict()
export const feedbackSchema = z.object({
  id: z.string().uuid(), monitorId: required(100), farmId: required(100), version: z.number().int().positive(),
  text: required(2000), reason: required(400), evidenceIds: z.array(required(100)).max(30),
  origin: z.enum(['synthetic', 'session_sample', 'local_draft']), updatedAt: z.iso.datetime(), decisions: z.array(decisionSchema).max(100),
}).strict().superRefine((v, ctx) => { if (v.decisions.some(d => d.feedbackVersion > v.version)) ctx.addIssue({ code: 'custom', message: 'Review version is invalid.' }) })
export const monitoringDocumentSchema = z.object({ version: z.literal(1), monitors: z.array(monitorDefinitionSchema).max(100), feedback: z.array(feedbackSchema).max(200) }).strict()
export type MonitorScope = z.infer<typeof monitorScopeSchema>
export type MonitorSchedule = z.infer<typeof monitorScheduleSchema>
export type MonitoringThreshold = z.infer<typeof thresholdSchema>
export type MonitoringRule = z.infer<typeof ruleSchema>
export type MonitorInput = z.infer<typeof monitorInputSchema>
export type MonitorDefinition = z.infer<typeof monitorDefinitionSchema>
export type FeedbackDraft = z.infer<typeof feedbackSchema>
export type OfficerReviewDecision = z.infer<typeof decisionSchema>
export type FarmReference = z.infer<typeof farmReferenceSchema>
export type Severity = z.infer<typeof severitySchema>
export type MetricId = typeof metricIds[number]
export type CapabilityId = typeof capabilityIds[number]
export type OutputId = typeof outputIds[number]
export interface MonitoringCapability { id: CapabilityId; name: string; description: string; source: 'example'; connection: 'not_connected'; futureReference?: { kind: 'skill' | 'tool'; id: string; version: number; digest: string } }
export interface Evidence { id: string; source: string; observedAt: string; analyzedAt: string | null; freshness: 'fixed_sample' | 'unavailable'; status: 'available' | 'unavailable'; value?: number; unit: string; reference: MonitoringThreshold['reference']; farmId: string; metric: MetricId; checks: number; limitations: string }
export interface ThresholdEvaluation { ruleId: string; farmId: string; outcome: 'triggered' | 'not_triggered' | 'unknown'; evidenceIds: string[]; explanation: string }
export interface MonitoringAlert { id: string; deduplicationKey: string; farmId: string; severity: Severity; title: string; detail: string; evidenceIds: string[]; state: 'new' | 'ongoing' | 'resolved'; trigger: 'sample_event' }
export interface MonitorRun { id: string; monitorId: string; configurationVersion: number; category: MonitorInput['category']; startedAt: string; completedAt: string; mode: 'synthetic'; status: 'partial' | 'sample_complete'; farmIds: string[]; capabilityIds: CapabilityId[]; evidence: Evidence[]; evaluations: ThresholdEvaluation[]; alerts: MonitoringAlert[]; dataGaps: string[]; reportIds: string[]; limitations: string }
export interface PhotoObservation { id: string; evidenceIds: string[]; text: string; certainty: 'illustrative_only'; limitations: string; status: 'officer_review_example' }
export interface PhotoSubmission { id: string; farmId: string; crop: string; stage: string | null; submittedAt: string; expectedDate: string; note: string; quality: 'illustrative' | 'unassessed'; analysis: 'not_analyzed' | 'unavailable' | 'pending' | 'possible_issue' | 'no_specific_issue' | 'field_inspection'; kind: 'illustration' | 'session_sample'; imageIndex?: number; objectUrl?: string; observations: PhotoObservation[]; limitations: string }
export interface FarmPhotoTimeline { farm: FarmReference; expectedDates: string[]; submissions: PhotoSubmission[]; missingDates: string[] }
export interface MonitoringReport { id: string; runId: string; title: string; mode: 'synthetic'; generatedAt: string; sections: { heading: string; text: string; evidenceIds: string[] }[]; limitations: string[] }
export const categoryLabels = { environment: 'Environmental', crop_health: 'Crop health', report: 'Reports' }
export const severityLabels: Record<Severity, string> = { info: 'Informational', warning: 'Warning', high: 'High priority', unknown: 'Insufficient evidence' }
export const outputLabels: Record<OutputId, string> = { summary: 'Monitoring summary', report: 'Detailed report', trends: 'Charts & trends', priority_list: 'Farm-priority list', alert: 'Dashboard alert', farmer_feedback: 'Draft farmer feedback', advisory: 'Draft advisory', inspection: 'Inspection suggestion' }
export const metricSpecs: Record<MetricId, { label: string; unit: MonitoringThreshold['unit']; min: number; max: number; integer?: boolean; capability: CapabilityId }> = {
  rainfall_deficit: { label: 'Rainfall deficit', unit: '%', min: 0, max: 100, capability: 'rainfall' },
  vegetation_decline: { label: 'Vegetation decline', unit: '%', min: 0, max: 100, capability: 'satellite' },
  temperature: { label: 'Forecast temperature', unit: '°C', min: -50, max: 65, capability: 'weather' },
  missing_photos: { label: 'Missing photo submissions', unit: 'submissions', min: 0, max: 52, integer: true, capability: 'crop_health' },
  reported_symptoms: { label: 'Reported symptoms', unit: 'reports', min: 0, max: 100, integer: true, capability: 'pests' },
  health_change: { label: 'Change in diagnostic output', unit: '%', min: 0, max: 100, capability: 'crop_health' },
}
export const operatorLabels = { gte: 'at least', gt: 'greater than', lte: 'at most', lt: 'less than', eq: 'equal to' }
export const referenceLabels = { seasonal_demo: 'Same seasonal week · sample baseline', recent_demo: 'Previous four weeks · sample mean', weekly_demo: 'Expected weekly submissions · sample', comparable_demo: 'Previous compatible observation · sample', custom: 'Custom reference · evaluation unavailable' }
export function ruleSentence(r: MonitoringRule) { return metricSpecs[r.metric].label + ' is ' + operatorLabels[r.operator] + ' ' + r.threshold.value + r.threshold.unit + ', for ' + r.consecutiveChecks + ' consecutive check' + (r.consecutiveChecks === 1 ? '' : 's') + '.' }
export function scheduleSentence(s: MonitorSchedule) { return (s.frequency === 'weekly' ? 'Every ' + ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][s.weekday] : s.frequency === 'monthly' ? 'Day ' + s.monthDay + ' of each month' : 'Daily') + ' at ' + s.time + ' · ' + s.timezone }
