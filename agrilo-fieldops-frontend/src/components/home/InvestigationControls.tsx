import { useHome } from '../../state/useHome'
import { investigationBlock } from '../../state/home-store'
import { skillInputs } from '../../api/home-contracts'

export function InvestigationControls() {
  const s = useHome(), skill = s.context?.skills.find(k => k.id === s.skillId), block = investigationBlock(s)
  return <section className="live-controls" aria-label="Investigation controls">
    <label>Agricultural skill<select aria-label="Agricultural skill" value={s.skillId} disabled={!!s.activeId} onChange={e => s.chooseSkill(e.target.value)}><option value="">Choose an available skill</option>{s.context?.skills.map(k => <option key={k.id} value={k.id} disabled={!k.available}>{k.name.replace(/^fieldops_/, '').replaceAll('_', ' ')}{!k.available ? ' — unavailable' : ''}</option>)}</select></label>
    {skill && <><p>{skill.description} · version {skill.version ?? 'unavailable'}</p>{!skill.available && <p role="alert">{skill.blocked_reason}</p>}{skill.missing_optional_capabilities.length > 0 && <p>Missing optional capabilities: {skill.missing_optional_capabilities.join(', ')}</p>}
      <div className="live-inputs">{skillInputs(skill).map(field => <label key={field.key}>{field.key.replaceAll('_', ' ')}{field.required ? ' *' : ' (optional)'}{field.key.endsWith('_plot_id') ? <select value={s.parameters[field.key] ?? ''} onChange={e => s.setParameter(field.key, e.target.value)}><option value="">Choose selected farm</option>{s.plots.filter(p => s.selectedIds.includes(p.id)).map(p => <option key={p.id} value={p.id}>{p.name}</option>)}</select> : <input aria-label={field.key.replaceAll('_', ' ')} type={field.type} maxLength={100} value={s.parameters[field.key] ?? ''} onChange={e => s.setParameter(field.key, e.target.value)} />}</label>)}</div>
      {skill.tools.some(t => t.requires_image) && <div><label>Crop image (JPEG/PNG, up to 10 MB)<input type="file" accept="image/jpeg,image/png" disabled={!skill.available || !!s.activeId} onChange={e => { const file = e.target.files?.[0]; if (file) void s.upload(file); e.target.value = '' }} /></label>{s.imageName && <p>Private asset uploaded: {s.imageName}</p>}<label><input type="checkbox" checked={s.authorizations.credit} onChange={e => s.authorize('credit', e.target.checked)} />Authorize one credit-consuming diagnosis. An uncertain submission will not be repeated automatically.</label></div>}
    </>}
    <div className="live-consent"><label><input type="checkbox" checked={s.authorizations.network} onChange={e => s.authorize('network', e.target.checked)} />Authorize the selected skill's provider requests.</label><label><input type="checkbox" checked={s.authorizations.model} onChange={e => s.authorize('model', e.target.checked)} />Authorize the backend-configured model for this investigation.</label></div>
    {block && <p className="live-blocked" role="status">{block}</p>}
    <details><summary>Unavailable backend capabilities</summary>{s.context?.skills.filter(k => !k.available).map(k => <p key={k.id}>{k.name}: {k.blocked_reason ?? 'Not currently executable'}</p>)}</details>
  </section>
}
