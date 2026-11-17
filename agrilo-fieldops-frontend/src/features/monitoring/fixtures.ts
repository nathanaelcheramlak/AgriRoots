import { demoFarmReferences, newMonitorInput, newRule } from './catalog'
import { combinedOutcome, evaluateRules } from './evaluation'
import type { Evidence, FarmPhotoTimeline, MonitorDefinition, MonitorInput, MonitoringAlert, MonitoringReport, MonitorRun, PhotoSubmission, Severity } from './types'
export const sampleScenarios = [
  { id: 'rainfall', name: 'Rainfall warning', description: 'One threshold warning with a seasonal reference.', template: 'weather' },
  { id: 'photos', name: 'Crop photo review', description: 'Illustrated timelines and an officer feedback draft.', template: 'photos' },
  { id: 'missing', name: 'Missing submission', description: 'A reminder about an expected photo, not crop risk.', template: 'photos' },
  { id: 'partial', name: 'Partial data', description: 'Rainfall context with unavailable satellite observations.', template: 'report' },
] as const
export type SampleScenario = typeof sampleScenarios[number]['id']
export const sampleFarms = [demoFarmReferences[0], demoFarmReferences[4], demoFarmReferences[6]]
export function sampleMonitor(scenario: SampleScenario): MonitorDefinition {
  const item = sampleScenarios.find(s => s.id === scenario)!, input = newMonitorInput(item.template)
  input.name = scenario === 'partial' ? 'Rainfall & vegetation review' : scenario === 'rainfall' ? 'Weekly rainfall watch' : scenario === 'missing' ? 'Weekly photo submission review' : 'Weekly maize photo monitoring'
  input.scope = { type: 'group', groupId: 'demo-adama-maize', label: 'Adama demonstration maize group', farms: sampleFarms }
  input.schedule = { ...input.schedule, frequency: 'weekly', startDate: '2026-11-02' }
  input.rules = [newRule(item.template === 'photos' ? 'missing_photos' : 'rainfall_deficit')]
  if (scenario === 'partial') { input.capabilityIds.push('satellite'); input.rules.push(newRule('vegetation_decline')); input.combination = 'any' }
  input.rules = input.rules.map((r, i) => ({ ...r, id: '00000000-0000-4000-8000-00000000000' + (i + 1) }))
  const index = sampleScenarios.findIndex(s => s.id === scenario) + 1
  return { id: '10000000-0000-4000-8000-00000000000' + index, version: 1, input, configurationStatus: 'draft', createdAt: '2026-11-02T05:00:00.000Z', updatedAt: '2026-11-16T05:00:00.000Z', owner: 'this_device' }
}
export function sampleEvidence(previous = false): Evidence[] {
  return sampleFarms.flatMap((f, i) => {
    const base = { farmId: f.id, source: 'AgriLo deterministic demonstration', observedAt: previous ? '2026-11-08T06:00:00.000Z' : '2026-11-15T06:00:00.000Z', analyzedAt: previous ? '2026-11-09T05:02:00.000Z' : '2026-11-16T05:02:00.000Z', freshness: 'fixed_sample' as const, limitations: 'Synthetic values only. No field measurement, forecast, satellite image or diagnosis. Reference periods are illustrative; comparability is assumed only in this fixture.', checks: 1 }
    return [
      { ...base, id: f.id + '-rain-' + (previous ? 'previous' : 'current'), metric: 'rainfall_deficit' as const, status: i === 2 ? 'unavailable' as const : 'available' as const, value: i === 2 ? undefined : (previous ? [10, 25][i] : [25, 10][i]), unit: '%', reference: 'seasonal_demo' as const },
      { ...base, id: f.id + '-rain-recent', metric: 'rainfall_deficit' as const, status: 'available' as const, value: [15, 7, 12][i], unit: '%', reference: 'recent_demo' as const },
      { ...base, id: f.id + '-vegetation', metric: 'vegetation_decline' as const, status: 'unavailable' as const, unit: '%', reference: 'comparable_demo' as const, freshness: 'unavailable' as const, analyzedAt: null },
      { ...base, id: f.id + '-photos', observedAt: previous ? '2026-11-09T05:00:00.000Z' : '2026-11-16T05:00:00.000Z', metric: 'missing_photos' as const, status: 'available' as const, value: i === 2 && !previous ? 1 : 0, unit: 'submissions', reference: 'weekly_demo' as const },
      { ...base, id: f.id + '-temperature', metric: 'temperature' as const, status: 'available' as const, value: [31, 28, 30][i], unit: '°C', reference: 'comparable_demo' as const },
    ]
  })
}
export function previewRun(input: MonitorInput, monitorId: string, configurationVersion: number, previous = false): MonitorRun {
  const syntheticEvidence = (prior: boolean) => sampleEvidence(prior).filter(e => input.scope.farms.some(f => f.id === e.farmId && f.source === 'synthetic'))
  const evidence = syntheticEvidence(previous), evaluations = evaluateRules(input, evidence), alerts: MonitoringAlert[] = []
  const before = previous ? [] : evaluateRules(input, syntheticEvidence(true))
  for (const farm of input.scope.farms) {
    const rows = evaluations.filter(e => e.farmId === farm.id), outcome = combinedOutcome(rows.map(e => e.outcome), input.combination)
    const old = combinedOutcome(before.filter(e => e.farmId === farm.id).map(e => e.outcome), input.combination)
    if (outcome === 'not_triggered' && old !== 'triggered') continue
    const triggered = rows.filter(e => e.outcome === 'triggered'), priority = { high: 3, warning: 2, info: 1, unknown: 0 }
    const rule = input.rules.filter(r => triggered.some(e => e.ruleId === r.id)).sort((a, b) => priority[b.severity] - priority[a.severity])[0]
    const severity: Severity = outcome === 'unknown' ? 'unknown' : rule?.severity ?? 'info'
    const state = outcome === 'not_triggered' && old === 'triggered' ? 'resolved' : old === 'triggered' ? 'ongoing' : 'new'
    alerts.push({ id: monitorId + '-' + farm.id + '-condition', deduplicationKey: monitorId + ':' + farm.id + ':configured-condition', farmId: farm.id, severity, title: state === 'resolved' ? 'Previous sample condition no longer triggers' : outcome === 'unknown' ? 'Evidence is incomplete' : rule?.metric === 'missing_photos' ? 'Expected photo missing' : 'Configured threshold requires review', detail: outcome === 'unknown' ? 'Missing or incompatible sample data cannot establish that the farm is safe.' : rule?.metric === 'missing_photos' ? 'Operational reminder only. A missing submission is not evidence of crop-health deterioration.' : 'Review the supporting sample evidence and configured threshold before drawing conclusions.', evidenceIds: rows.flatMap(e => e.evidenceIds), state, trigger: 'sample_event' })
  }
  const relevant = evidence.filter(e => input.scope.farms.some(f => f.id === e.farmId) && input.rules.some(r => r.metric === e.metric && r.threshold.reference === e.reference))
  const dataGaps = [...new Set(evaluations.filter(e => e.outcome === 'unknown').map(e => e.farmId + ': comparable evidence unavailable'))]
  if (input.capabilityIds.includes('satellite')) dataGaps.push('Satellite observations unavailable. No vegetation inference.')
  return { id: 'SAMPLE-' + (previous ? '20261109' : '20261116') + '-' + monitorId, monitorId, configurationVersion, category: input.category, startedAt: previous ? '2026-11-09T05:00:00.000Z' : '2026-11-16T05:00:00.000Z', completedAt: previous ? '2026-11-09T05:02:00.000Z' : '2026-11-16T05:02:00.000Z', mode: 'synthetic', status: dataGaps.length ? 'partial' : 'sample_complete', farmIds: input.scope.farms.map(f => f.id), capabilityIds: input.capabilityIds, evidence: relevant, evaluations, alerts, dataGaps, reportIds: ['sample-report-' + monitorId], limitations: 'Explicit on-demand sample preview. No scheduled job or external tool was executed. Sample values are not validated agricultural thresholds.' }
}
export function sampleHistory(input: MonitorInput, id: string, version: number) { return [previewRun(input, id, version), previewRun(input, id, version, true)] }
export function sampleTimelines(): FarmPhotoTimeline[] {
  const expectedDates = ['2026-10-26', '2026-11-02', '2026-11-09', '2026-11-16']
  return sampleFarms.map((farm, farmIndex) => {
    const submissions: PhotoSubmission[] = expectedDates.slice(0, farmIndex === 2 ? 3 : 4).map((date, i) => ({
      id: farm.id + '-sample-photo-' + i, farmId: farm.id, crop: farm.crop, stage: null, submittedAt: date + 'T04:30:00.000Z', expectedDate: date,
      note: i === 3 && farmIndex === 0 ? 'Sample note: please review the color difference in this illustration.' : 'Illustrative weekly crop record. No real farmer submission.',
      quality: 'illustrative', analysis: 'unavailable', kind: 'illustration', imageIndex: i,
      observations: i === 3 && farmIndex === 0 ? [{ id: 'sample-color-observation', evidenceIds: [farm.id + '-sample-photo-' + i], text: 'An illustrated leaf-color difference is marked as an officer-review example.', certainty: 'illustrative_only', status: 'officer_review_example', limitations: 'Not an automated diagnosis or evidence of a crop disease.' }] : [],
      limitations: 'Original schematic sample, not a field photograph. Lighting, viewpoint, distance and plant selection would limit real photo comparison.',
    }))
    return { farm, expectedDates, submissions, missingDates: farmIndex === 2 ? ['2026-11-16'] : [] }
  })
}
export function sampleReport(run: MonitorRun): MonitoringReport {
  const attention = run.alerts.filter(a => a.state !== 'resolved' && a.severity !== 'unknown')
  return { id: run.reportIds[0], runId: run.id, title: 'Demonstration farm intelligence report', mode: 'synthetic', generatedAt: run.completedAt,
    sections: [
      { heading: 'Coverage', text: run.farmIds.length + ' configured farm references in this sample scope. Sample source: AgriLo deterministic demonstration. Observation date: ' + (run.evidence[0]?.observedAt.slice(0, 10) ?? 'unavailable; no compatible sample observations') + '.', evidenceIds: run.evidence.map(e => e.id) },
      { heading: 'Configured conditions', text: attention.length + ' sample farm conditions require officer review. Thresholds are officer-configured and illustrative; these are not validated agronomic standards.', evidenceIds: attention.flatMap(a => a.evidenceIds) },
      { heading: 'Data gaps', text: run.dataGaps.join('. ') || 'No gaps for the narrow set of sample rules. This does not establish field safety.', evidenceIds: run.evidence.filter(e => e.status === 'unavailable').map(e => e.id) },
      { heading: 'Suggested follow-up', text: 'Inspect the source references and missing observations. Prepare feedback as a local draft for officer review; no farmer communication has been sent.', evidenceIds: [] },
    ], limitations: [run.limitations, 'No field observations, authenticated provider calls, or AI crop diagnosis.', 'An unavailable observation is not evidence that risk is absent.'] }
}
