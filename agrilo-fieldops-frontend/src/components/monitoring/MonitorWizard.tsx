import { useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, Check, LockKeyhole } from 'lucide-react'
import { PluginModal } from '../plugins/PluginModal'
import { capabilities, newMonitorInput, templates } from '../../features/monitoring/catalog'
import { categoryLabels, monitorInputSchema, outputLabels, referenceLabels, ruleSentence, scheduleSentence } from '../../features/monitoring/types'
import type { MonitorDefinition, MonitorInput } from '../../features/monitoring/types'
import { monitoringService, useMonitoring } from '../../features/monitoring/store'
import { ScopeEditor } from './ScopeEditor'
import { RuleEditor } from './RuleEditor'
import { Field, MonitorSymbol } from './MonitoringUi'
const steps = ['Basics', 'Farms', 'Capabilities', 'Frequency', 'Thresholds', 'Outputs', 'Review']
const stepKeys = [['name', 'description', 'instructions', 'category', 'templateId'], ['scope'], ['capabilityIds'], ['schedule'], ['rules', 'combination'], ['outputs']]
export function MonitorWizard({ existing, initial, onClose, onSaved }: { existing?: MonitorDefinition; initial?: MonitorInput; onClose: () => void; onSaved: (monitor: MonitorDefinition) => void }) {
  const state = useMonitoring(), [input, setInput] = useState<MonitorInput>(() => structuredClone(existing?.input ?? initial ?? newMonitorInput()))
  const [step, setStep] = useState(0), [furthest, setFurthest] = useState(existing ? 6 : 0), [errors, setErrors] = useState<string[]>([]), [busy, setBusy] = useState(false)
  const body = useRef<HTMLDivElement>(null)
  const set = <K extends keyof MonitorInput>(key: K, value: MonitorInput[K]) => setInput(previous => ({ ...previous, [key]: value }))
  const move = (next: number) => { setStep(next); setErrors([]); body.current?.scrollIntoView({ block: 'start' }); requestAnimationFrame(() => body.current?.querySelector<HTMLElement>('h3')?.focus()) }
  const next = () => {
    const result = monitorInputSchema.safeParse(input)
    const relevant = result.success ? [] : result.error.issues.filter(i => stepKeys[step]?.includes(String(i.path[0])))
    if (relevant.length) { setErrors([...new Set(relevant.map(i => i.message))]); return }
    setFurthest(Math.max(furthest, step + 1)); move(step + 1)
  }
  const save = async () => {
    const result = monitorInputSchema.safeParse(input)
    if (!result.success) { setErrors([...new Set(result.error.issues.map(i => i.message))]); return }
    setBusy(true)
    try {
      const monitor = await monitoringService.save(result.data, existing ? { id: existing.id, version: existing.version } : undefined)
      await state.refresh(); state.notify('Monitor draft saved locally. No schedule was activated.'); onSaved(monitor)
    } catch (error) { setErrors([error instanceof Error ? error.message : 'Could not save this local draft.']); setBusy(false) }
  }
  return <PluginModal title={existing ? 'Edit monitor draft' : 'Create monitor'} wide onClose={onClose}>
    <div className="monitoring-wizard">
      <nav className="monitor-wizard-steps" aria-label="Monitor setup steps">{steps.map((label, i) => <button type="button" key={label} disabled={i > furthest || busy} aria-current={step === i ? 'step' : undefined} onClick={() => move(i)}><span>{i < step ? <Check size={12} /> : i + 1}</span>{label}</button>)}</nav>
      <div className="monitor-wizard-layout">
        <div className="monitor-wizard-body" ref={body}>
          <div className="monitor-step-title"><small>STEP {step + 1} OF 7</small><h3 tabIndex={-1}>{['Give your monitor a purpose', 'Choose the farms in scope', 'Choose example capabilities', 'Plan a recurring check', 'Define what matters', 'Choose the work to prepare', 'Review your local configuration'][step]}</h3></div>
          {errors.length > 0 && <div className="monitor-errors" role="alert"><strong>Check the configuration</strong><ul>{errors.map(e => <li key={e}>{e}</li>)}</ul></div>}
          <div className="monitor-step-content">
            {step === 0 && <>
              <Field label="Template"><select aria-label="Template" value={input.templateId} onChange={e => { const next = newMonitorInput(e.target.value as MonitorInput['templateId']); setInput({ ...next, scope: input.scope }) }}>{templates.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
              <Field label="Monitor name"><input aria-label="Monitor name" maxLength={100} value={input.name} placeholder="Weekly maize health monitoring" onChange={e => set('name', e.target.value)} /></Field>
              <Field label="Description"><textarea aria-label="Monitor description" rows={2} maxLength={600} value={input.description} onChange={e => set('description', e.target.value)} /></Field>
              <Field label="Monitoring category"><select aria-label="Monitoring category" value={input.category} onChange={e => set('category', e.target.value as MonitorInput['category'])}>{Object.entries(categoryLabels).map(([id, label]) => <option key={id} value={id}>{label}</option>)}</select></Field>
              <Field label="Describe what you want AgriLo to monitor" hint="Optional planning notes only. These words are saved as instructions; no AI workflow is generated."><textarea aria-label="Monitoring instructions" rows={3} maxLength={1200} value={input.instructions} placeholder="Describe your goals, context, or review needs…" onChange={e => set('instructions', e.target.value)} /></Field>
            </>}
            {step === 1 && <ScopeEditor value={input.scope} onChange={v => set('scope', v)} saved={state.monitors} />}
            {step === 2 && <>
              <div className="monitor-info"><LockKeyhole size={17} /><p>Example metadata only · all providers are not connected. Future approved skills and plugin tools will appear here through the backend registry.</p></div>
              <div className="monitor-capability-grid">{capabilities.map(c => <label key={c.id} className={input.capabilityIds.includes(c.id) ? 'selected' : ''}><input type="checkbox" checked={input.capabilityIds.includes(c.id)} onChange={e => set('capabilityIds', e.target.checked ? [...input.capabilityIds, c.id] : input.capabilityIds.filter(id => id !== c.id))} /><span><strong>{c.name}</strong><small>{c.description}</small><em>Example · Not connected</em></span></label>)}</div>
            </>}
            {step === 3 && <>
              <div className="monitor-info"><p>This is a planned recurrence. Background execution requires the future scheduler. Saving a draft will not run checks, including while this browser is closed.</p></div>
              <div className="monitor-form-grid">
                <Field label="Frequency"><select aria-label="Frequency" value={input.schedule.frequency} onChange={e => set('schedule', { ...input.schedule, frequency: e.target.value as MonitorInput['schedule']['frequency'] })}><option value="daily">Daily</option><option value="weekly">Weekly</option><option value="monthly">Monthly</option></select></Field>
                <Field label="Time of day"><input aria-label="Time of day" type="time" value={input.schedule.time} onChange={e => set('schedule', { ...input.schedule, time: e.target.value })} /></Field>
                {input.schedule.frequency === 'weekly' && <Field label="Weekday"><select aria-label="Weekday" value={input.schedule.weekday} onChange={e => set('schedule', { ...input.schedule, weekday: Number(e.target.value) })}>{['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map((d, i) => <option key={d} value={i}>{d}</option>)}</select></Field>}
                {input.schedule.frequency === 'monthly' && <Field label="Day of month" hint="Days 1–28 are supported to avoid missing short months."><input aria-label="Day of month" type="number" min="1" max="28" value={input.schedule.monthDay || ''} onChange={e => set('schedule', { ...input.schedule, monthDay: Number(e.target.value) })} /></Field>}
                <Field label="Timezone"><input aria-label="Timezone" list="monitor-timezones" value={input.schedule.timezone} onChange={e => set('schedule', { ...input.schedule, timezone: e.target.value })} /><datalist id="monitor-timezones"><option value="Africa/Addis_Ababa" /><option value="Africa/Nairobi" /><option value="UTC" /><option value="Europe/London" /><option value="America/New_York" /></datalist></Field>
                <Field label="Start date"><input aria-label="Start date" type="date" value={input.schedule.startDate} onChange={e => set('schedule', { ...input.schedule, startDate: e.target.value })} /></Field>
                <Field label="End date (optional)"><input aria-label="End date" type="date" value={input.schedule.endDate} onChange={e => set('schedule', { ...input.schedule, endDate: e.target.value })} /></Field>
                <Field label="Review date (optional)"><input aria-label="Review date" type="date" value={input.schedule.reviewDate} onChange={e => set('schedule', { ...input.schedule, reviewDate: e.target.value })} /></Field>
              </div>
            </>}
            {step === 4 && <RuleEditor input={input} onChange={setInput} />}
            {step === 5 && <>
              <p className="monitor-muted">Choose one or more outputs. Farmer-facing drafts always require explicit officer review and an authorized future delivery workflow.</p>
              <div className="monitor-output-grid">{Object.entries(outputLabels).map(([id, label]) => <label key={id}><input type="checkbox" checked={input.outputs.includes(id as MonitorInput['outputs'][number])} onChange={e => set('outputs', e.target.checked ? [...input.outputs, id as MonitorInput['outputs'][number]] : input.outputs.filter(o => o !== id))} />{label}</label>)}</div>
            </>}
            {step === 6 && <div className="monitor-review-summary">
              <h4>{input.name}</h4><p>{input.description}</p>
              <dl><div><dt>Farms covered</dt><dd>{input.scope.label} · {input.scope.farms.length} farms</dd></div><div><dt>Planned recurrence</dt><dd>{scheduleSentence(input.schedule)}<small>Starts {input.schedule.startDate}{input.schedule.endDate && ' · Ends ' + input.schedule.endDate}{input.schedule.reviewDate && ' · Review ' + input.schedule.reviewDate}</small></dd></div><div><dt>Capabilities / data dependencies</dt><dd>{input.capabilityIds.map(id => capabilities.find(c => c.id === id)?.name).join(', ')}<small>Examples only · no connected data sources</small></dd></div><div><dt>Thresholds · {input.combination === 'all' ? 'AND' : 'OR'}</dt><dd>{input.rules.length ? input.rules.map(r => <p key={r.id}>{ruleSentence(r)} <small>{referenceLabels[r.threshold.reference]} · {r.scope === 'all' ? 'All scope farms' : r.scope === 'crop' ? r.crop : r.farmIds.join(', ')} · {r.severity} · {r.action.replaceAll('_', ' ')}</small></p>) : 'No threshold rules'}</dd></div><div><dt>Expected outputs</dt><dd>{input.outputs.map(o => outputLabels[o]).join(', ')}</dd></div><div><dt>Review requirements</dt><dd>Officer review is required for farmer-facing feedback or advisory drafts. No delivery channel is connected.</dd></div></dl>
              {input.instructions && <div className="monitor-info"><p>Planning notes: {input.instructions}</p></div>}
              <details><summary>Inspect farm scope</summary><ul>{input.scope.farms.map(f => <li key={f.id}>{f.name} · {f.crop} · {f.source}</li>)}</ul></details>
            </div>}
          </div>
        </div>
        <aside className="monitor-wizard-summary"><MonitorSymbol template={input.templateId} size={29} /><small>YOUR MONITOR DRAFT</small><h4>{input.name || 'Untitled monitor'}</h4><p>{categoryLabels[input.category]}</p><dl><div><dt>Farms</dt><dd>{input.scope.farms.length} selected</dd></div><div><dt>Frequency</dt><dd>{input.schedule.frequency} · {input.schedule.time}</dd></div><div><dt>Capabilities</dt><dd>{input.capabilityIds.length} example sources</dd></div><div><dt>Thresholds</dt><dd>{input.rules.length} rules · {input.combination === 'all' ? 'AND' : 'OR'}</dd></div><div><dt>Outputs</dt><dd>{input.outputs.length} selected</dd></div></dl><span><LockKeyhole size={13} />Local draft · scheduler unavailable</span></aside>
      </div>
      <footer className="monitor-wizard-footer"><button type="button" className="plugin-secondary" onClick={step ? () => move(step - 1) : onClose} disabled={busy}>{step ? <><ArrowLeft size={14} />Back</> : 'Cancel'}</button><span>{input.scope.farms.length} farms · {input.rules.length} rules · {input.schedule.frequency}</span>{step < 6 ? <button type="button" className="monitor-primary" onClick={next}>Continue<ArrowRight size={15} /></button> : <button type="button" className="monitor-primary" disabled={busy} onClick={() => { void save() }}>{busy ? 'Saving…' : 'Save monitor draft'}<Check size={15} /></button>}</footer>
    </div>
  </PluginModal>
}
