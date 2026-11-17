import { useHome } from '../../state/useHome'
import { jobLabel } from '../../api/home-contracts'
import { EvidencePanel } from './EvidencePanel'

export function InvestigationResults() {
  const s = useHome()
  return <section className="live-conversation" aria-label="Agricultural investigations">
    <h2>Investigate selected farms</h2><p className="tiny">Conversation stays here during navigation. Each submission is a separate durable investigation; earlier messages are not silently sent as server conversation context.</p>
    {!s.investigations.length && <p>Select an authorized farm and ask about weather, mapped soil, rainfall or another available capability. Combined investigations use the tools supplied by the backend registry.</p>}
    {s.investigations.map(run => <article key={run.id} className="live-run"><h3>You asked</h3><p>{run.question}</p><small>{run.skillName} · farms: {run.plotIds.join(', ') || 'not farm-specific'}</small><p role="status">{run.job ? jobLabel(run.job) + ' · job ' + run.job.id : run.error ? 'Submission not confirmed' : 'Preparing request'}</p>
      {run.job?.progress?.calls.map(call => <p className="live-call" key={call.id}>{call.name} · {call.status}{call.finished_at ? ' · finished ' + call.finished_at : ''}</p>)}
      {run.error && <p role="alert">{run.error}</p>}
      {run.result && <><h3>Agricultural findings{run.result.status === 'partial' ? ' — partial evidence' : ''}</h3><p className="live-answer">{run.result.answer}</p><p>Skill version {run.result.skill_version} · model: {String(run.result.model.model ?? run.result.model.provider ?? 'recorded in result')}</p>{run.result.outcomes.map((outcome, i) => <div key={i} className={outcome.execution_outcome === 'SUCCESS' ? 'live-outcome' : 'live-outcome error'}><strong>{outcome.source?.provider ?? 'Recorded operation'}</strong>: {outcome.execution_outcome} / {outcome.data_outcome} · {outcome.classification ?? 'classification unavailable'}{outcome.cache_hit ? ' · reused scoped evidence' : ''}{outcome.error && <p>{outcome.error.message}</p>}{outcome.limitations?.map((line, j) => <p className="tiny" key={j}>{line}</p>)}</div>)}{run.result.evidence_ids.length > 0 && <p>Evidence references: {run.result.evidence_ids.join(', ')}</p>}</>}
      {run.evidence.map(evidence => <EvidencePanel key={evidence.id} evidence={evidence} />)}
      {run.job && ['queued', 'running'].includes(run.job.status) && <button onClick={() => void s.cancel(run.id)}>Cancel investigation</button>}
      {(run.error || (run.job && ['queued', 'running'].includes(run.job.status) && s.activeId !== run.id)) && <button disabled={!!s.activeId} onClick={() => void s.resume(run.id)}>{run.job ? 'Refresh / resume this job' : 'Recover the same submission'}</button>}
    </article>)}
  </section>
}
