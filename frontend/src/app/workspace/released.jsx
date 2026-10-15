import { useEffect, useRef, useState } from "react";
import { Link, Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { workspace, workspaceError } from "@/lib/workspace";
import "./workspace.css";

function ReleasedCard({ version: v }) {
  const [language, setLanguage] = useState(v.language);
  const [audio, setAudio] = useState("");
  const audioUrl = useRef("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => () => { if (audioUrl.current) URL.revokeObjectURL(audioUrl.current); }, []);
  const play = async () => {
    setBusy(true); setError("");
    try {
      const blob = await workspace.audio(v.id, language);
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      audioUrl.current = URL.createObjectURL(blob); setAudio(audioUrl.current);
    } catch { setError("Audio is unavailable. Please read the released text below."); } finally { setBusy(false); }
  };
  const actions = language === v.language ? v.recommendations.map(r => r.action) : v.translations[language];
  return <article><h2>{v.title} · version {v.version}</h2><p>Approved and released by your extension office.</p>
    {v.replaces_advisory_id && <p>This advisory replaces {v.replaces_advisory_id}.</p>}
    <label>Reviewed language<select value={language} onChange={e => { setLanguage(e.target.value); setAudio(""); }}>
      {[v.language, ...Object.keys(v.translations)].map(l => <option key={l} value={l}>{l === "am" ? "አማርኛ" : "English"}</option>)}</select></label>
    <ol lang={language}>{actions.map((action, i) => <li key={i}><p>{action}</p>
      {language === v.language && <p>Uncertainty: {v.recommendations[i].uncertainty}</p>}
      {language === v.language && v.recommendations[i].basis && <p>Why: {v.recommendations[i].basis}</p>}
      <details><summary>Supporting evidence</summary>{v.recommendations[i].evidence_ids.map(id => {
        const e = v.evidence[id];
        return <div key={id}><strong>{e.source_name} · {e.classification}</strong><p>{e.source_reference}</p>
          <p>{e.snapshot}</p><p>Observed: {e.observed_at} · Valid until: {e.valid_until}</p></div>;
      })}</details></li>)}</ol>
    {language === v.language && <p>Missing information: {v.missing_information || "None recorded"}</p>}
    <button disabled={busy} onClick={play}>{busy ? "Preparing audio…" : "Listen to released advice"}</button>
    {audio && <audio key={audio} controls autoPlay src={audio} />}
    {error && <p role="alert">{error}</p>}
  </article>;
}

export default function ReleasedPage() {
  const { isHydrated, isAuthenticated } = useAuth();
  const [versions, setVersions] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    if (!isAuthenticated) return;
    let active = true;
    workspace.released().then(v => { if (active) setVersions(v); }).catch(e => { if (active) setError(workspaceError(e)); });
    return () => { active = false; };
  }, [isAuthenticated]);
  if (!isHydrated) return <p>Loading…</p>;
  if (!isAuthenticated) return <Navigate to="/auth-options" replace />;
  return <main className="workspace"><nav><Link to="/main-page">Chat</Link><Link to="/workspace">Office workspace</Link></nav>
    <h1>My released advisories</h1>
    {error && <p role="alert">{error}</p>}
    {!versions ? <p>Loading released advice…</p> : versions.length ? versions.map(v => <ReleasedCard key={v.id} version={v} />) :
      <p>Your extension office has not released any advisories to your household yet.</p>}
  </main>;
}
