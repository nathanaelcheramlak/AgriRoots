import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { workspace, workspaceError } from "@/lib/workspace";
import "./workspace.css";
import RunPanel from "./RunPanel";

const FIELD_SETS = {
  cluster: ["name", "assigned_officer_id", "synthetic"],
  household: ["name", "farmer_user_id", "cluster_id", "assigned_officer_id", "synthetic"],
  plot: ["name", "household_id", "latitude", "longitude", "area", "area_unit", "agroclimatic_zone"],
  season: ["plot_id", "crop", "stage", "planting_date", "harvest_date", "previous_yield", "yield_unit"],
  guidance: ["crop", "agroclimatic_zone", "text", "source", "reviewed_on", "supported_actions", "planting_rule"],
  calendar: ["crop", "agroclimatic_zone", "text", "source", "reviewed_on", "supported_actions", "planting_rule", "planting_start", "planting_end", "harvest_start", "harvest_end"],
  evidence: ["source_name", "source_reference", "observed_at", "retrieved_at", "valid_from", "valid_until", "location", "crop", "units", "observation", "snapshot", "classification", "plot_id"],
};
const LABELS = { synthetic: "Synthetic demonstration data", previous_yield: "Previous yield (blank means unknown)",
  source_reference: "Source URL or internal record reference", snapshot: "Supporting extract or snapshot",
  observation: "Observed values", text: "Locally reviewed guidance", reviewed_on: "Local review date" };
const ENUMS = { stage: ["planned", "growing"], supported_actions: ["inspect_drainage", "inspect_crop", "monitor_heat", "request_field_visit", "plant_crop", "hold_planting"], area_unit: ["ha", "m2"], yield_unit: ["kg", "kg/ha", "t/ha"], classification: ["live", "historical", "synthetic", "officer-entered"] };
const RULE_FIELDS = { rain_days: "Forecast window (days, 1–3)", minimum_rain_mm: "Minimum rain (mm)", maximum_rain_mm: "Maximum rain (mm)", maximum_temperature_c: "Maximum temperature (°C)", maximum_wind_kph: "Maximum wind (km/h)" };
const NUMBER_FIELDS = new Set(["latitude", "longitude", "area", "previous_yield"]);
const OPTIONAL = new Set(["previous_yield", "yield_unit", "harvest_date"]);
const LONG_FIELDS = new Set(["text", "snapshot", "observation"]);
const nameOf = row => row.data.name || row.data.source_name || row.data.crop || row.id;
const labelOf = key => LABELS[key] || key.replaceAll("_", " ").replace(/\bid\b/g, "account");

function RecordForm({ officeId, members, records, onSaved, act }) {
  const [kind, setKind] = useState("household");
  const [editing, setEditing] = useState(null);
  const [data, setData] = useState({});
  const change = (key, value) => setData(d => ({ ...d, [key]: value }));
  const optionsFor = key => {
    if (key === "assigned_officer_id" || key === "farmer_user_id") {
      return members.filter(m => key === "farmer_user_id" ? m.role === "farmer" : m.role !== "farmer")
        .map(m => ({ value: m.user_id, label: `${m.name || m.user_id} (${m.role})` }));
    }
    const related = { cluster_id: "cluster", household_id: "household", plot_id: "plot" }[key];
    if (related) return records.filter(r => r.kind === related).map(r => ({ value: r.id, label: nameOf(r) }));
    return ENUMS[key]?.map(value => ({ value, label: value.replaceAll("_", " ") }));
  };
  const submit = e => {
    e.preventDefault();
    act(async () => {
      const payload = {};
      for (const key of FIELD_SETS[kind]) {
        if (key === "planting_rule") {
          const entries = Object.entries(data.planting_rule || {}).filter(([, v]) => v !== "");
          payload[key] = entries.length ? Object.fromEntries(entries.map(([k, v]) => [k, Number(v)])) : null;
          continue;
        }
        if (key === "supported_actions") { payload[key] = data[key] || []; continue; }
        if (key === "observation") { payload.values = { observation: data.observation }; continue; }
        const value = data[key];
        if (key === "synthetic") payload[key] = Boolean(value);
        else if (value === "" || value == null) {
          if (OPTIONAL.has(key) || (kind === "evidence" && key === "plot_id")) payload[key] = null;
        } else if (NUMBER_FIELDS.has(key)) payload[key] = Number(value);
        else if (["observed_at", "retrieved_at", "valid_from", "valid_until"].includes(key)) payload[key] = new Date(value).toISOString();
        else payload[key] = value;
      }
      await workspace.saveRecord(officeId, { kind, data: payload }, editing);
      setData({}); setEditing(null); await onSaved();
    });
  };
  return <section><h2>Households, plots and sources</h2>
    <label>Record type<select value={kind} onChange={e => { setKind(e.target.value); setData({}); setEditing(null); }}>
      {Object.keys(FIELD_SETS).map(k => <option key={k}>{k}</option>)}
    </select></label>
    <form onSubmit={submit} className="workspace-fields">
      {FIELD_SETS[kind].map(key => {
        if (key === "planting_rule") return <fieldset key={key}><legend>Officer-reviewed planting rule</legend>
          <p>Required for planting / hold actions. Enter thresholds from the cited local guidance; no agronomic defaults are supplied.</p>
          {Object.entries(RULE_FIELDS).map(([field, label]) => <label key={field}>{label}<input type="number" step={field === "rain_days" ? "1" : "any"}
            value={data.planting_rule?.[field] ?? ""} onChange={e => change("planting_rule", { ...data.planting_rule, [field]: e.target.value })} /></label>)}
        </fieldset>;
        const options = optionsFor(key);
        const required = !OPTIONAL.has(key) && !(kind === "evidence" && key === "plot_id");
        const isTime = ["observed_at", "retrieved_at", "valid_from", "valid_until"].includes(key);
        return <label key={key}>{labelOf(key)}{key === "synthetic" ?
          <input type="checkbox" checked={Boolean(data[key])} onChange={e => change(key, e.target.checked)} /> : options ?
          <select multiple={key === "supported_actions"} required={required && key !== "supported_actions"} value={data[key] || (key === "supported_actions" ? [] : "")} onChange={e => change(key, key === "supported_actions" ? Array.from(e.target.selectedOptions, o => o.value) : e.target.value)}>
            <option value="">Select…</option>{options.map(o => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select> : LONG_FIELDS.has(key) ?
          <textarea required={required} value={data[key] || ""} onChange={e => change(key, e.target.value)} /> :
          <input required={required} type={NUMBER_FIELDS.has(key) ? "number" : isTime ? "datetime-local" : /date|_on|_start|_end/.test(key) ? "date" : "text"}
            step={NUMBER_FIELDS.has(key) ? "any" : undefined} value={data[key] ?? ""} onChange={e => change(key, e.target.value)} />}</label>;
      })}
      <button type="submit">{editing ? "Save record changes" : "Add record"}</button>
      {editing && <button type="button" onClick={() => { setEditing(null); setData({}); }}>Cancel edit</button>}
    </form>
    <ul>{records.filter(r => r.kind === kind).map(r => <li key={r.id}>
      <strong>{nameOf(r)}</strong>{r.data.synthetic ? " · Synthetic" : ""}
      <details><summary>View record</summary><dl>{Object.entries(r.data).map(([k, v]) =>
        <div key={k}><dt>{labelOf(k)}</dt><dd>{typeof v === "object" ? JSON.stringify(v) : String(v ?? "Unknown")}</dd></div>)}</dl></details>
      {!["evidence", "calendar", "guidance"].includes(kind) && <button type="button" onClick={() => { setEditing(r); setData(r.data); }}>Edit</button>}
    </li>)}</ul>
    {kind === "evidence" || kind === "calendar" || kind === "guidance" ? <p>Sources are preserved. Add a new record to correct a source.</p> : null}
  </section>;
}

const blankRecommendation = () => ({ action: "", uncertainty: "", evidence_ids: [], proposed_date: null });
function AdvisoryForm({ officeId, me, members, records, editing, onSaved, act }) {
  const [draft, setDraft] = useState(() => editing?.content || { title: "", household_ids: [], plot_ids: [],
    assigned_officer_id: me.user_id, language: "en", recommendations: [blankRecommendation()], missing_information: "",
    translations: {}, replaces_advisory_id: null });
  const [cluster, setCluster] = useState("");
  const set = (key, value) => setDraft(d => ({ ...d, [key]: value }));
  const updateRecommendation = (index, key, value) => set("recommendations", draft.recommendations.map((r, i) => i === index ? { ...r, [key]: value } : r));
  const households = records.filter(r => r.kind === "household" && (!cluster || r.data.cluster_id === cluster));
  const plots = records.filter(r => r.kind === "plot" && draft.household_ids.includes(r.data.household_id));
  const evidence = records.filter(r => r.kind === "evidence");
  const selectMany = e => Array.from(e.target.selectedOptions, o => o.value);
  return <section><h2>{editing ? `Revise version ${editing.version}` : "Draft a sourced advisory"}</h2>
    {editing && <p>Saving creates a new draft version requiring review and approval. Released history remains available.</p>}
    <form onSubmit={e => { e.preventDefault(); act(async () => { await workspace.saveAdvisory(officeId, draft, editing); await onSaved(); }); }}>
      <div className="workspace-fields">
        <label>Title<input required value={draft.title} onChange={e => set("title", e.target.value)} /></label>
        <label>Cluster filter<select value={cluster} onChange={e => { setCluster(e.target.value); set("household_ids", []); set("plot_ids", []); }}><option value="">All clusters</option>
          {records.filter(r => r.kind === "cluster").map(r => <option key={r.id} value={r.id}>{nameOf(r)}</option>)}</select></label>
        <label>Target households<select multiple required value={draft.household_ids} onChange={e => {
          set("household_ids", selectMany(e)); set("plot_ids", []);
        }}>{households.map(r => <option key={r.id} value={r.id}>{nameOf(r)}{r.data.synthetic ? " · Synthetic" : ""}</option>)}</select></label>
        <label>Target plots<select multiple value={draft.plot_ids} onChange={e => set("plot_ids", selectMany(e))}>
          {plots.map(r => <option key={r.id} value={r.id}>{nameOf(r)}</option>)}</select></label>
        <label>Assigned officer<select required value={draft.assigned_officer_id} onChange={e => set("assigned_officer_id", e.target.value)}>
          {members.filter(m => m.role !== "farmer").map(m => <option key={m.user_id} value={m.user_id}>{m.name || m.user_id}</option>)}</select></label>
        <label>Reviewed language<select value={draft.language} onChange={e => { set("language", e.target.value); set("translations", {}); }}>
          <option value="en">English</option><option value="am">Amharic</option></select></label>
      </div>
      <p>Use Ctrl / Command to select several households, plots or evidence records.</p>
      {draft.recommendations.map((r, i) => <fieldset key={i}><legend>Recommendation {i + 1}</legend>
        <label>Proposed action<textarea required value={r.action} onChange={e => updateRecommendation(i, "action", e.target.value)} /></label>
        <label>Specific supporting evidence<select multiple value={r.evidence_ids} onChange={e => updateRecommendation(i, "evidence_ids", selectMany(e))}>
          {evidence.map(v => <option key={v.id} value={v.id}>{nameOf(v)} · {v.data.classification} · {v.data.crop}</option>)}</select></label>
        <label>Uncertainty and limits<textarea required value={r.uncertainty} onChange={e => updateRecommendation(i, "uncertainty", e.target.value)} /></label>
        <label>Reason for this recommendation<textarea value={r.basis || ""} onChange={e => updateRecommendation(i, "basis", e.target.value)} /></label>
        <label>Proposed date<input type="date" value={r.proposed_date || ""} onChange={e => updateRecommendation(i, "proposed_date", e.target.value || null)} /></label>
      </fieldset>)}
      <button type="button" onClick={() => set("recommendations", [...draft.recommendations, blankRecommendation()])}>Add recommendation</button>
      <label>Missing information<textarea value={draft.missing_information} onChange={e => set("missing_information", e.target.value)} /></label>
      <label>Replacement advisory (optional)<input value={draft.replaces_advisory_id || ""} onChange={e => set("replaces_advisory_id", e.target.value || null)} /></label>
      <details><summary>Include a reviewed translation</summary><p>Include the reason, uncertainty and missing information in each translated action. This text will also be used for audio.</p>
        {draft.recommendations.map((r, i) => {
          const lang = draft.language === "en" ? "am" : "en";
          return <label key={i}>{lang === "am" ? "Amharic" : "English"} action {i + 1}
            <textarea value={draft.translations[lang]?.[i] || ""} onChange={e => {
              const values = draft.recommendations.map((_, j) => j === i ? e.target.value : draft.translations[lang]?.[j] || "");
              set("translations", values.every(v => !v) ? {} : { [lang]: values });
            }} /></label>;
        })}</details>
      <button type="submit">Save draft version</button>
    </form>
  </section>;
}

function ReviewCard({ version: v, current, records, onEdit, onTransition, onHistory }) {
  const [reason, setReason] = useState("");
  const c = v.content;
  return <article><h3>{c.title} · v{v.version} · {v.status.replaceAll("_", " ")}</h3>
    <p>Language: {c.language} · Households: {c.household_ids.map(id => records.find(r => r.id === id)?.data.name || id).join(", ")}</p>
    <p>Advisory reference: {v.advisory_id}</p>
    <ol>{c.recommendations.map((r, i) => <li key={i}><p>{r.action}</p><p>Uncertainty: {r.uncertainty}</p>
      {r.basis && <p>Why: {r.basis}</p>}
      {r.proposed_date && <p>Proposed date: {r.proposed_date}</p>}
      {r.evidence_ids.map(id => <details key={id}><summary>Evidence: {v.evidence_snapshots[id]?.source_name || id}</summary>
        <EvidenceView evidence={v.evidence_snapshots[id]} /></details>)}</li>)}</ol>
    <p>Missing information: {c.missing_information || "None recorded"}</p>
    {Object.entries(c.translations).map(([language, actions]) => <div key={language}><strong>Reviewed translation: {language}</strong>{actions.map((text, i) => <p key={i}>{text}</p>)}</div>)}
    <button onClick={() => onHistory(v.advisory_id)}>View audit history</button>
    {current ? <div className="workspace-actions"><button onClick={() => onEdit(v)}>Edit into new draft</button>
      {["draft", "rejected"].includes(v.status) && <button onClick={() => onTransition(v, "submit", "")}>Submit for review</button>}
      {v.status === "pending_review" && <><button onClick={() => onTransition(v, "approve", "")}>Approve exact version</button>
        <button disabled={!reason.trim()} onClick={() => onTransition(v, "reject", reason)}>Reject</button></>}
      {v.status === "approved" && <button className="release" onClick={() => onTransition(v, "release", "")}>Release approved version to farmers</button>}
      {!["released", "cancelled"].includes(v.status) && <><label>Rejection / cancellation reason<input value={reason} onChange={e => setReason(e.target.value)} /></label>
        <button disabled={!reason.trim()} onClick={() => onTransition(v, "cancel", reason)}>Cancel version</button></>}
    </div> : <p>Historical version</p>}
  </article>;
}

function EvidenceView({ evidence: e }) {
  if (!e) return <p>Evidence is missing.</p>;
  return <dl>{Object.entries(e).map(([key, value]) => <div key={key}><dt>{labelOf(key)}</dt>
    <dd>{typeof value === "object" ? JSON.stringify(value) : String(value ?? "Unspecified")}</dd></div>)}</dl>;
}

function Administration({ me, onSaved, act }) {
  const [officeName, setOfficeName] = useState("");
  const [officeId, setOfficeId] = useState(me.memberships[0]?.office_id || "");
  const [account, setAccount] = useState("");
  const [role, setRole] = useState("farmer");
  const [offices, setOffices] = useState([]);
  useEffect(() => {
    if (me.global_administrator) workspace.offices().then(setOffices).catch(() => {});
  }, [me]);
  return <section><h2>Office administration</h2>
    {me.global_administrator && <form onSubmit={e => { e.preventDefault(); act(async () => {
      const office = await workspace.createOffice(officeName); setOfficeId(office.id); setOfficeName("");
      setOffices(await workspace.offices()); await onSaved();
    }); }}><label>New office name<input required value={officeName} onChange={e => setOfficeName(e.target.value)} /></label><button>Create office</button></form>}
    <form onSubmit={e => { e.preventDefault(); act(async () => {
      await workspace.enroll(officeId, { user_id: account, role }); setAccount(""); await onSaved();
    }); }}>
      <label>Office<select required value={officeId} onChange={e => setOfficeId(e.target.value)}><option value="">Select office</option>
        {(me.global_administrator ? offices : me.memberships.map(m => ({ id: m.office_id, name: m.office_name }))).map(o => <option key={o.id} value={o.id}>{o.name}</option>)}</select></label>
      <label>Registered account UUID<input required value={account} onChange={e => setAccount(e.target.value)} /></label>
      <label>Role<select value={role} onChange={e => setRole(e.target.value)}>{["farmer", "officer", "administrator"].map(r => <option key={r}>{r}</option>)}</select></label>
      <button>Enroll account</button><p>Each account belongs to one office. Farmers register through the existing OTP flow before enrollment.</p>
    </form>
  </section>;
}

export default function WorkspacePage() {
  const { isHydrated, isAuthenticated } = useAuth();
  const [me, setMe] = useState(null);
  const [records, setRecords] = useState([]);
  const [members, setMembers] = useState([]);
  const [versions, setVersions] = useState([]);
  const [editing, setEditing] = useState(null);
  const [events, setEvents] = useState(null);
  const [queue, setQueue] = useState("current");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const officeId = me?.memberships.find(m => m.role !== "farmer")?.office_id;
  const refreshMe = async () => setMe(await workspace.me());
  const refresh = async () => {
    const [r, m, v] = await Promise.all([workspace.records(officeId), workspace.members(officeId), workspace.advisories(officeId)]);
    setRecords(r); setMembers(m); setVersions(v);
  };
  const act = async fn => {
    setBusy(true); setError(""); setNotice("");
    try { await fn(); setNotice("Saved successfully."); } catch (e) { setError(workspaceError(e)); } finally { setBusy(false); }
  };
  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    workspace.me().then(value => { if (active) setMe(value); }).catch(e => { if (active) setError(workspaceError(e)); });
    return () => { active = false; };
  }, [isAuthenticated]);
  useEffect(() => {
    if (!officeId) return;
    let active = true;
    Promise.all([workspace.records(officeId), workspace.members(officeId), workspace.advisories(officeId)])
      .then(([r, m, v]) => { if (active) { setRecords(r); setMembers(m); setVersions(v); } })
      .catch(e => { if (active) setError(workspaceError(e)); });
    return () => { active = false; };
  }, [officeId]);
  if (!isHydrated) return <p>Loading…</p>;
  if (!isAuthenticated) return <Navigate to="/auth-options" replace />;
  const latest = new Map();
  for (const v of versions) latest.set(v.advisory_id, Math.max(v.version, latest.get(v.advisory_id) || 0));
  return <main className="workspace"><nav><Link to="/main-page">Chat</Link><Link to="/advisories">My released advisories</Link></nav>
    <h1>Extension office workspace</h1>
    {error && <p role="alert" className="workspace-error">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {!me ? <p>Loading permissions…</p> : <>
      <p>Your account: {me.user_id}</p>
      <fieldset disabled={busy} className="workspace-body">
        {(me.global_administrator || me.memberships.some(m => m.role === "administrator")) && <Administration me={me} onSaved={async () => { await refreshMe(); if (officeId) await refresh(); }} act={act} />}
        {officeId ? <><h2>{me.memberships.find(m => m.office_id === officeId)?.office_name}</h2>
          <RecordForm officeId={officeId} members={members} records={records} onSaved={refresh} act={act} />
          <section><h2>Farmer requests</h2>{records.filter(r => r.kind === "request").map(r => <article key={r.id}>
            <p>{r.data.message}</p><p>From: {records.find(h => h.kind === "household" && h.data.farmer_user_id === r.data.farmer_user_id)?.data.name || r.data.farmer_user_id}</p>
            {r.data.has_image && <p>Image review requested. Contact the farmer to inspect the image.</p>}
          </article>)}</section>
          <RunPanel officeId={officeId} records={records} onReview={refresh} />
          <AdvisoryForm key={editing?.id || "new"} officeId={officeId} me={me} members={members} records={records} editing={editing}
            act={act} onSaved={async () => { setEditing(null); await refresh(); }} />
          {editing && <button onClick={() => setEditing(null)}>Start a separate advisory</button>}
          <section id="review-and-release"><h2>Review and release</h2><label>Show<select value={queue} onChange={e => setQueue(e.target.value)}>
            <option value="current">Current versions</option><option value="pending_review">Review queue</option><option value="approved">Awaiting release</option><option value="all">All history</option></select></label>
            {versions.filter(v => queue === "all" || (latest.get(v.advisory_id) === v.version && (queue === "current" || v.status === queue))).map(v =>
              <ReviewCard key={v.id} version={v} current={latest.get(v.advisory_id) === v.version} records={records} onEdit={setEditing}
                onTransition={(version, action, reason) => act(async () => { await workspace.transition(officeId, version, action, reason); await refresh(); })}
                onHistory={id => act(async () => setEvents(await workspace.events(officeId, id)))} />)}
            {!versions.length && <p>No advisories yet. Add a cluster, household and evidence to draft one.</p>}
          </section>
          {events && <section><h2>Audit history</h2><ol>{events.map(e => <li key={e.id}>{e.created_at} · {e.action} · officer {e.actor_id} · version {e.details.version}{e.details.reason ? ` · ${e.details.reason}` : ""}</li>)}</ol></section>}
        </> : <p>An office administrator must enroll your account before you can manage records. Farmers can read released advice through the link above.</p>}
      </fieldset>
    </>}
  </main>;
}
