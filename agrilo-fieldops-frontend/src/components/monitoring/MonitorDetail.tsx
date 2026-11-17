import { useEffect, useMemo, useState } from 'react'
import { ArrowLeft, Copy, History, Pause, Pencil, Play, Trash2 } from 'lucide-react'
import type { MonitorDefinition } from '../../features/monitoring/types'
import { categoryLabels, outputLabels, scheduleSentence } from '../../features/monitoring/types'
import { capabilities } from '../../features/monitoring/catalog'
import { monitoringService, useMonitoring } from '../../features/monitoring/store'
import type { SampleScenario } from '../../features/monitoring/fixtures'
import { PluginModal } from '../plugins/PluginModal'
import { PhotoWorkspace } from './PhotoWorkspace'
import type { FeedbackSeed } from './PhotoWorkspace'
import { FeedbackReview } from './FeedbackReview'
import { MonitoringOverview, MonitoringReports, RulePreview } from './MonitoringResults'
import { MonitoringHistory } from './MonitoringHistory'
import { formatDate, MonitorSymbol } from './MonitoringUi'
import { prepareMonitoringOutreach, preparePhotoOutreach } from '../../features/outreach/transfer'
const monitorViewPreferences = new Map<string, { tab: string; preview: boolean }>()
const tabs = [{ id: 'overview', name: 'Overview' }, { id: 'configuration', name: 'Configuration' }, { id: 'rules', name: 'Thresholds & evidence' }, { id: 'photos', name: 'Photos' }, { id: 'reports', name: 'Reports' }, { id: 'history', name: 'History' }, { id: 'feedback', name: 'Feedback' }]
export function MonitorDetail({ monitor, scenario, onEdit }: { monitor: MonitorDefinition; scenario?: SampleScenario; onEdit: (monitor: MonitorDefinition, copy?: boolean) => void }) {
  const state = useMonitoring(), [tab, setTab] = useState(() => monitorViewPreferences.get(monitor.id)?.tab ?? (scenario === 'photos' || scenario === 'missing' ? 'photos' : 'overview')), [preview, setPreview] = useState(() => monitorViewPreferences.get(monitor.id)?.preview ?? !!scenario)
  useEffect(() => { monitorViewPreferences.set(monitor.id, { tab, preview }) }, [monitor.id, tab, preview])
  const [busy, setBusy] = useState(false), [error, setError] = useState<string | null>(null), [deleting, setDeleting] = useState(false), [seed, setSeed] = useState<FeedbackSeed>()
  const run = useMemo(() => preview ? monitoringService.preview(monitor.input, monitor.id, monitor.version) : undefined, [preview, monitor])
  const histories = useMemo(() => preview ? monitoringService.history(monitor.input, monitor.id, monitor.version) : [], [preview, monitor])
  const timelines = useMemo(() => monitoringService.photoTimelines().filter(t => monitor.input.scope.farms.some(f => f.id === t.farm.id && f.source === 'synthetic')), [monitor])
  const change = async (action: 'duplicate' | 'pause' | 'delete') => {
    setError(null); setBusy(true)
    try {
      if (action === 'duplicate') { const copy = await monitoringService.duplicate(monitor.id); await state.refresh(); window.location.hash = 'monitoring/' + copy.id; state.notify('Configuration duplicated locally. No scheduler was activated.') }
      if (action === 'pause') { await monitoringService.setPaused(monitor.id, monitor.version, monitor.configurationStatus !== 'paused'); await state.refresh(); state.notify('Local configuration status updated. No backend schedule was changed.') }
      if (action === 'delete') { await monitoringService.remove(monitor.id); await state.refresh(); setDeleting(false); window.location.hash = 'monitoring'; state.notify('Local monitor and associated feedback drafts deleted.') }
    } catch (e) { setError(e instanceof Error ? e.message : 'This local change could not be saved.') }
    finally { setBusy(false) }
  }
  return <div className="monitor-detail">
    <a className="monitor-back-link" href="#monitoring"><ArrowLeft size={14} />All monitors</a>
    <header className="monitor-detail-header"><span className="monitor-detail-symbol"><MonitorSymbol template={monitor.input.templateId} size={25} /></span><div><div className="monitor-kicker">{categoryLabels[monitor.input.category]} · CONFIGURATION V{monitor.version}</div><h1>{monitor.input.name}</h1><p>{monitor.input.description}</p><div className="monitor-detail-badges"><span className="monitor-draft-badge">{scenario ? 'Sample configuration' : monitor.configurationStatus === 'paused' ? 'Paused locally' : 'Draft · Saved locally'}</span><span>Not scheduled</span><span>No connected capabilities</span></div></div></header>
    <div className="monitor-detail-toolbar"><div className="monitor-detail-actions">{scenario ? <button className="plugin-secondary" onClick={() => onEdit(monitor, true)}><Copy size={14} />Save a local copy</button> : <><button className="plugin-secondary" onClick={() => onEdit(monitor)}><Pencil size={14} />Edit</button><button className="plugin-secondary" disabled={busy} onClick={() => { void change('duplicate') }}><Copy size={14} />Duplicate</button><button className="plugin-secondary" disabled={busy} onClick={() => { void change('pause') }}>{monitor.configurationStatus === 'paused' ? <Play size={14} /> : <Pause size={14} />}{monitor.configurationStatus === 'paused' ? 'Return to draft' : 'Pause configuration'}</button><button className="monitor-text-action danger" disabled={busy} onClick={() => setDeleting(true)}><Trash2 size={15} />Delete</button></>}<button className="monitor-text-action" onClick={() => setTab('history')}><History size={14} />View history</button></div>{!scenario && <button className={'monitor-preview-button ' + (preview ? 'selected' : '')} aria-pressed={preview} onClick={() => setPreview(!preview)}>{preview ? 'Hide sample data' : 'Preview synthetic data'}</button>}</div>
    {error && !deleting && <div className="monitor-errors" role="alert">{error}</div>}
    <div className="monitor-outreach-action"><button className="plugin-secondary" disabled={!run} onClick={() => { if (run) void prepareMonitoringOutreach(monitor, run, monitor.input.templateId === 'report' ? 'weekly' : 'weather').catch(() => state.notify('The source could not be prepared. Check the evidence metadata and try again.')) }}>Prepare Outreach</button><span>{run ? 'Carry this sample evidence and farm scope into a local campaign.' : 'Preview a result before preparing evidence-backed outreach.'}</span></div>
    <div className="monitor-detail-tabs" role="tablist" aria-label="Monitor detail views">{tabs.map(t => <button key={t.id} role="tab" aria-selected={tab === t.id} id={'monitor-tab-' + t.id} aria-controls={'monitor-panel-' + t.id} onClick={() => setTab(t.id)}>{t.name}</button>)}</div>
    <div className="monitor-detail-panel" role="tabpanel" id={'monitor-panel-' + tab} aria-labelledby={'monitor-tab-' + tab}>
      {tab === 'overview' && <MonitoringOverview monitor={monitor} run={run} onTab={setTab} />}
      {tab === 'configuration' && <section className="monitor-config-view"><div className="monitor-section-heading"><div><h2>Local configuration</h2><p>Ownership: this device · no office or authenticated user assigned</p></div></div><dl><div><dt>Scope</dt><dd>{monitor.input.scope.label} · {monitor.input.scope.farms.length} farms</dd></div><div><dt>Planned recurrence</dt><dd>{scheduleSentence(monitor.input.schedule)} · not active</dd></div><div><dt>Dates</dt><dd>Starts {monitor.input.schedule.startDate}{monitor.input.schedule.endDate && ' · Ends ' + monitor.input.schedule.endDate}{monitor.input.schedule.reviewDate && ' · Review ' + monitor.input.schedule.reviewDate}</dd></div><div><dt>Expected outputs</dt><dd>{monitor.input.outputs.map(o => outputLabels[o]).join(', ')}</dd></div><div><dt>Instructions</dt><dd>{monitor.input.instructions || 'No planning notes'}<small>Saved text only · not an executable AI workflow</small></dd></div><div><dt>Updated</dt><dd>{formatDate(monitor.updatedAt)}</dd></div></dl><h3>Data dependencies</h3><div className="monitor-capability-chips">{monitor.input.capabilityIds.map(id => <span key={id}>{capabilities.find(c => c.id === id)?.name} <small>Example · Not connected</small></span>)}</div><h3>Farms in scope</h3><div className="monitor-table-wrap"><table><thead><tr><th>Farm</th><th>Crop</th><th>Origin</th></tr></thead><tbody>{monitor.input.scope.farms.map(f => <tr key={f.id}><td>{f.name}</td><td>{f.crop}</td><td>{f.source === 'synthetic' ? 'Synthetic fixture' : 'Home snapshot'}</td></tr>)}</tbody></table></div><div className="monitor-info"><p>Provider access, farm membership, unit comparability and review authority require backend validation before any monitoring can execute.</p></div></section>}
      {tab === 'rules' && <RulePreview monitor={monitor} run={run} />}
      {tab === 'photos' && <PhotoWorkspace timelines={timelines} farms={monitor.input.scope.farms} sample={preview} onFeedback={next => { setSeed(next); setTab('feedback') }} onOutreach={(photo, notes) => { void preparePhotoOutreach(monitor, photo, notes).catch(() => state.notify('The crop context could not be prepared. Check the officer notes and try again.')) }} />}
      {tab === 'reports' && <MonitoringReports run={run} onPrepare={() => { if (run) void prepareMonitoringOutreach(monitor, run, 'weekly').catch(() => state.notify('This report context could not be prepared for Outreach.')) }} />}
      {tab === 'history' && <MonitoringHistory runs={histories} decisions={state.feedback.filter(f => f.monitorId === monitor.id).flatMap(f => f.decisions.map(d => ({ label: f.farmId + ' · ' + d.action.replaceAll('_', ' ') + ' · feedback v' + d.feedbackVersion, at: d.at })))} />}
      {tab === 'feedback' && <FeedbackReview monitor={monitor} sample={preview} seed={seed} />}
    </div>
    {deleting && <PluginModal title="Delete local monitor?" onClose={() => setDeleting(false)}><div className="monitor-delete-content"><p>Remove <strong>{monitor.input.name}</strong> and its saved feedback drafts from this device?</p><small>No backend schedule or farmer communication is involved.</small>{error && <p role="alert" className="monitor-error-text">{error}</p>}<footer><button className="plugin-secondary" onClick={() => setDeleting(false)}>Cancel</button><button className="plugin-danger" disabled={busy} onClick={() => { void change('delete') }}>Delete local monitor</button></footer></div></PluginModal>}
  </div>
}
