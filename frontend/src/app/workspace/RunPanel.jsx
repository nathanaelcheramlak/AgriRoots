import { useEffect, useRef, useState } from "react";
import { workspace, workspaceError } from "@/lib/workspace";

export default function RunPanel({ officeId, records, onReview }) {
  const [cluster, setCluster] = useState("");
  const [task, setTask] = useState("Inspect current crop conditions and identify observations needed for officer review.");
  const [runs, setRuns] = useState([]);
  const [selected, setSelected] = useState(null);
  const [detail, setDetail] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(null);
  useEffect(() => {
    let active = true;
    const refresh = () => workspace.runs(officeId).then(v => { if (active) setRuns(v); })
      .catch(e => { if (active) setError(workspaceError(e)); });
    refresh(); const timer = setInterval(refresh, 4000);
    return () => { active = false; clearInterval(timer); };
  }, [officeId]);
  useEffect(() => {
    if (!selected) return;
    let active = true;
    const refresh = () => workspace.run(officeId, selected).then(v => { if (active) setDetail(v); })
      .catch(e => { if (active) setError(workspaceError(e)); });
    refresh(); const timer = setInterval(refresh, 3000);
    return () => { active = false; clearInterval(timer); };
  }, [officeId, selected]);
  const start = async e => {
    e.preventDefault(); setBusy(true); setError("");
    if (!request.current || request.current.cluster !== cluster || request.current.task !== task)
      request.current = { key: crypto.randomUUID(), cluster, task };
    try {
      const run = await workspace.createRun(officeId, { cluster_id: cluster, task, request_key: request.current.key });
      setSelected(run.id); setRuns(await workspace.runs(officeId)); request.current = null;
    } catch (err) { setError(workspaceError(err)); } finally { setBusy(false); }
  };
  const retry = async () => {
    setBusy(true); setError("");
    try { await workspace.retryRun(officeId, selected); setDetail(await workspace.run(officeId, selected)); }
    catch (err) { setError(workspaceError(err)); } finally { setBusy(false); }
  };
  return <section><h2>Agent advisory runs</h2>
    <p>Select a cluster with current crop seasons, reviewed calendars and local guidance. Planned crops use your reviewed planting rules to draft a planting or hold decision; growing crops receive inspection advice. The agent stops before approval and release.</p>
    <form onSubmit={start}><label>Household cluster<select required value={cluster} onChange={e => setCluster(e.target.value)}>
      <option value="">Select cluster</option>{records.filter(r => r.kind === "cluster").map(r => <option key={r.id} value={r.id}>{r.data.name}{r.data.synthetic ? " · Synthetic" : ""}</option>)}</select></label>
      <label>Requested task<textarea required minLength={5} maxLength={2000} value={task} onChange={e => setTask(e.target.value)} /></label>
      <button disabled={busy}>Start advisory run</button>
    </form>
    {error && <p role="alert" className="workspace-error">{error}</p>}
    <label>Inspect a run<select value={selected || ""} onChange={e => { setSelected(e.target.value); setDetail(null); }}>
      <option value="">Select run</option>{runs.map(r => <option key={r.id} value={r.id}>{r.created_at} · {r.status.replaceAll("_", " ")} · {r.task.slice(0, 60)}</option>)}</select></label>
    {detail && <article aria-live="polite"><h3>{detail.status.replaceAll("_", " ")}</h3>
      <p>Cluster: {records.find(r => r.id === detail.cluster_id)?.data.name || detail.cluster_id}</p>
      <p>{detail.task}</p><p>Progress: {detail.stage.replaceAll("_", " ")} · Attempt {detail.attempt} · Tool calls {detail.tool_calls}</p>
      {detail.status === "queued" && <p>Waiting for the advisory worker.</p>}
      {detail.error && <p role="alert">{detail.error.message}</p>}
      {detail.warnings.map((w, i) => <p key={i}>{w.message || String(w)}</p>)}
      {["failed", "needs_information", "running"].includes(detail.status) && <button disabled={busy || detail.attempt >= 3} onClick={retry}>Retry after resolving missing data or an interrupted run</button>}
      {detail.advisory_id && <p><a href="#review-and-release" onClick={onReview}>Open the saved draft in the review queue</a></p>}
      <h3>Model and tool activity</h3>
      {detail.model_config.model && <p>Local model: {detail.model_config.model} · revision {detail.model_config.revision}</p>}
      <p>{detail.model_config.cost_status === "estimated" ? `Compute estimate uses $${detail.model_config.compute_cost_per_hour_usd}/hour. Provider fees and idle time are excluded.` : "Compute cost is unpriced. Configure an hourly host rate to estimate inference cost; zero is not a claim of free hosting."}</p>
      <ol>{detail.calls.map(call => <li key={call.id}><strong>{call.tool_name}</strong> · attempt {call.attempt} · {call.duration_ms ?? "running"} ms
        {call.error ? <p>{call.error.message}</p> : null}
        <details><summary>Inspect inputs, evidence and result</summary>
          <pre className="run-json">{JSON.stringify({ inputs: call.inputs, output: call.output, error: call.error, usage: call.usage, estimated_cost_usd: call.estimated_cost_usd }, null, 2)}</pre>
        </details></li>)}</ol>
    </article>}
  </section>;
}
