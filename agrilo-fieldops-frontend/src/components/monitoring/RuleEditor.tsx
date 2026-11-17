import { Plus, Trash2 } from 'lucide-react'
import { newRule } from '../../features/monitoring/catalog'
import { metricIds, metricSpecs, operatorLabels, referenceLabels, ruleSentence, severityLabels } from '../../features/monitoring/types'
import type { MonitorInput, MonitoringRule, MetricId } from '../../features/monitoring/types'
import { Field } from './MonitoringUi'
export function RuleEditor({ input, onChange }: { input: MonitorInput; onChange: (input: MonitorInput) => void }) {
  const choices = metricIds.filter(m => input.capabilityIds.includes(metricSpecs[m].capability))
  const update = (index: number, value: MonitoringRule) => onChange({ ...input, rules: input.rules.map((r, i) => i === index ? value : r) })
  return <div className="monitor-rule-builder">
    <div className="monitor-info"><p>Choose thresholds for your use case. Prefilled values are illustrative, not validated agronomic standards. Real evaluation requires compatible units, baselines and sufficient observations.</p></div>
    <Field label="Combine conditions"><select aria-label="Combine conditions" value={input.combination} onChange={e => onChange({ ...input, combination: e.target.value as 'all' | 'any' })}><option value="all">ALL conditions must match (AND)</option><option value="any">ANY condition can match (OR)</option></select></Field>
    {!input.rules.length && <p className="monitor-muted">No thresholds yet. A monitor can prepare a summary without threshold rules.</p>}
    {input.rules.map((r, index) => <fieldset className="monitor-rule" key={r.id}><legend>Rule {index + 1}</legend><button type="button" className="monitor-rule-remove" aria-label={'Remove rule ' + (index + 1)} onClick={() => onChange({ ...input, rules: input.rules.filter(v => v.id !== r.id) })}><Trash2 size={15} /></button>
      <div className="monitor-form-grid">
        <Field label="Metric"><select aria-label={'Metric ' + (index + 1)} value={r.metric} onChange={e => { const metric = e.target.value as MetricId; update(index, { ...newRule(metric), id: r.id }) }}>{metricIds.map(m => <option key={m} value={m} disabled={!choices.includes(m)}>{metricSpecs[m].label}</option>)}</select></Field>
        <Field label="Comparison"><select aria-label={'Comparison ' + (index + 1)} value={r.operator} onChange={e => update(index, { ...r, operator: e.target.value as MonitoringRule['operator'] })}>{Object.entries(operatorLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <Field label={'Threshold (' + r.threshold.unit + ')'}><input type="number" aria-label={'Threshold ' + (index + 1)} value={Number.isFinite(r.threshold.value) ? r.threshold.value : ''} min={metricSpecs[r.metric].min} max={metricSpecs[r.metric].max} step={metricSpecs[r.metric].integer ? 1 : 'any'} onChange={e => update(index, { ...r, threshold: { ...r.threshold, value: e.target.value === '' ? NaN : Number(e.target.value) } })} /></Field>
        <Field label="Unit"><select aria-label={'Unit ' + (index + 1)} value={r.threshold.unit} onChange={() => {}}><option>{metricSpecs[r.metric].unit}</option></select></Field>
        <Field label="Reference period / baseline"><select aria-label={'Reference ' + (index + 1)} value={r.threshold.reference} onChange={e => update(index, { ...r, threshold: { ...r.threshold, reference: e.target.value as MonitoringRule['threshold']['reference'] } })}>{Object.entries(referenceLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <Field label="Consecutive checks"><input aria-label={'Consecutive checks ' + (index + 1)} type="number" min="1" max="30" value={r.consecutiveChecks || ''} onChange={e => update(index, { ...r, consecutiveChecks: e.target.value === '' ? NaN : Number(e.target.value) })} /></Field>
        <Field label="Severity"><select aria-label={'Severity ' + (index + 1)} value={r.severity} onChange={e => update(index, { ...r, severity: e.target.value as MonitoringRule['severity'] })}>{Object.entries(severityLabels).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></Field>
        <Field label="When triggered"><select aria-label={'Action ' + (index + 1)} value={r.action} onChange={e => update(index, { ...r, action: e.target.value as MonitoringRule['action'] })}><option value="flag_report">Flag farms & prepare officer report</option><option value="officer_review">Prepare draft for officer review</option><option value="inspection">Suggest field inspection</option></select></Field>
        <Field label="Rule scope"><select aria-label={'Rule scope ' + (index + 1)} value={r.scope} onChange={e => update(index, { ...r, scope: e.target.value as MonitoringRule['scope'], farmIds: [], crop: '' })}><option value="all">All monitor farms</option><option value="crop">One crop</option><option value="farms">Specific farms</option></select></Field>
        {r.scope === 'crop' && <Field label="Crop"><select aria-label={'Crop scope ' + (index + 1)} value={r.crop} onChange={e => update(index, { ...r, crop: e.target.value })}><option value="">Choose crop</option>{[...new Set(input.scope.farms.map(f => f.crop))].map(c => <option key={c}>{c}</option>)}</select></Field>}
      </div>
      {r.threshold.reference === 'custom' && <Field label="Custom baseline description"><input aria-label={'Custom reference ' + (index + 1)} maxLength={240} value={r.threshold.referenceNote} onChange={e => update(index, { ...r, threshold: { ...r.threshold, referenceNote: e.target.value } })} /></Field>}
      {r.scope === 'farms' && <div className="monitor-rule-farms">{input.scope.farms.map(f => <label key={f.id}><input type="checkbox" checked={r.farmIds.includes(f.id)} onChange={e => update(index, { ...r, farmIds: e.target.checked ? [...r.farmIds, f.id] : r.farmIds.filter(id => id !== f.id) })} />{f.name}</label>)}</div>}
      <p className="monitor-rule-sentence">{ruleSentence(r)}</p>
    </fieldset>)}
    <button className="plugin-secondary" type="button" disabled={!choices.length || input.rules.length >= 12} onClick={() => onChange({ ...input, rules: [...input.rules, newRule(choices[0])] })}><Plus size={15} />Add threshold rule</button>
    {!choices.length && <p className="monitor-muted">The selected example capabilities have no supported threshold metrics yet.</p>}
  </div>
}
