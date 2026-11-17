import type { Evidence, MonitorInput, MonitoringRule, ThresholdEvaluation } from './types'
export function evaluateRule(rule: MonitoringRule, farmId: string, evidence: Evidence[]): ThresholdEvaluation {
  const record = evidence.find(e => e.farmId === farmId && e.metric === rule.metric && e.unit === rule.threshold.unit && e.reference === rule.threshold.reference)
  const base = { ruleId: rule.id, farmId, evidenceIds: record ? [record.id] : [] }
  if (!record || record.status !== 'available' || record.value === undefined || !Number.isFinite(record.value) || record.checks < rule.consecutiveChecks || rule.threshold.reference === 'custom') return { ...base, outcome: 'unknown', explanation: 'Comparable evidence or consecutive checks are unavailable. This does not establish low risk.' }
  const v = record.value, threshold = rule.threshold.value
  const triggered = ({ gte: v >= threshold, gt: v > threshold, lte: v <= threshold, lt: v < threshold, eq: v === threshold })[rule.operator]
  return { ...base, outcome: triggered ? 'triggered' : 'not_triggered', explanation: 'Synthetic value ' + v + record.unit + ' compared with ' + threshold + rule.threshold.unit + '. This is an illustrative evaluation, not an agronomic standard.' }
}
export function evaluateRules(input: MonitorInput, evidence: Evidence[]): ThresholdEvaluation[] {
  return input.scope.farms.flatMap(f => input.rules.filter(r => r.scope === 'all' || (r.scope === 'crop' ? f.crop === r.crop : r.farmIds.includes(f.id))).map(r => evaluateRule(r, f.id, evidence)))
}
export function combinedOutcome(outcomes: ThresholdEvaluation['outcome'][], combination: 'all' | 'any'): ThresholdEvaluation['outcome'] {
  if (!outcomes.length) return 'unknown'
  if (combination === 'all') return outcomes.includes('not_triggered') ? 'not_triggered' : outcomes.includes('unknown') ? 'unknown' : 'triggered'
  return outcomes.includes('triggered') ? 'triggered' : outcomes.includes('unknown') ? 'unknown' : 'not_triggered'
}
