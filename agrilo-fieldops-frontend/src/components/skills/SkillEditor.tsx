import { useState } from 'react'
import { PluginModal } from '../plugins/PluginModal'
import { parsePublicJson } from '../../features/plugins/managed-api'
import { skillsApi, useSkills } from '../../features/skills/runtime'
import type { Skill } from '../../features/skills/service'

const starter = { name: 'office_evidence_review', description: 'Explain approved agricultural evidence for the selected farm.', instructions: 'Use the explicitly required approved tools. Cite actual evidence IDs, dates and limitations. Do not invent observations or prescribe pesticide doses.', required_capabilities: ['weather.forecast'], optional_capabilities: [], allowed_internal_actions: [], max_followup_rounds: 2, triggers: ['explicit_chat_request'] }
export function SkillEditor({ skill, onClose }: { skill?: Skill; onClose(): void }) {
  const s = useSkills(), [text, setText] = useState(JSON.stringify(skill?.manifest ?? starter, null, 2)), [error, setError] = useState<string | null>(null)
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setError(null)
    let value: unknown
    try { value = parsePublicJson(text) } catch { setError('Enter a valid credential-free skill manifest JSON object.'); return }
    const ok = await s.action(async signal => { await skillsApi.save(value, signal, skill) })
    if (ok) onClose()
  }
  return <PluginModal title={skill ? 'Create skill revision' : 'Create backend skill draft'} wide onClose={onClose}><form className="plugin-config-form" onSubmit={e => void save(e)}><p>Administrator authoring uses the existing versioned registry. Saving does not approve or enable the skill, invoke a provider, or turn a plugin tool into a new skill automatically.</p><label>Skill manifest (JSON)<textarea aria-label="Skill manifest (JSON)" className="managed-json-editor" rows={18} spellCheck={false} value={text} onChange={e => setText(e.target.value)} /></label><p>Required and optional capabilities must be explicit. Instructions are authored workflow data, not permission to bypass tools, farm authorization or approval. Stable names are immutable after registration.</p>{skill && <p>Current version {skill.version} · expected record revision {skill.revision}. An existing enabled version remains separate from the new draft.</p>}{(error || s.error) && <p role="alert" className="plugin-field-error">{error ?? s.error}</p>}<footer className="plugin-form-actions"><button type="button" className="plugin-secondary" onClick={onClose}>Cancel</button><button className="plugin-primary" disabled={s.busy}>Save backend draft</button></footer></form></PluginModal>
}
