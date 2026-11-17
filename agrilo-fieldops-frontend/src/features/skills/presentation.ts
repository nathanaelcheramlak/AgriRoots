import { skillInputs } from '../../api/home-contracts'
import type { HomeSkill } from '../../api/home-contracts'
import type { Skill } from './service'

export function runtimeSkill(s: Skill): HomeSkill | null {
  const e = s.execution
  return e ? { id: s.id, name: s.name, description: e.manifest.description, version: e.version, available: e.available, blocked_reason: e.blocked_reason, tools: e.tools, missing_optional_capabilities: e.missing_optional_capabilities } : null
}
export const skillTitle = (name: string) => name.replace(/^fieldops_/, '').replaceAll('_', ' ')
export function skillCategory(s: Skill) {
  const caps = (s.execution?.manifest ?? s.manifest).required_capabilities
  if (caps.length > 1) return 'Combined evidence'
  const c = caps[0] ?? ''
  return c.startsWith('weather.') || c.startsWith('rainfall.') || c.startsWith('climate.') ? 'Weather & rainfall' : c.startsWith('soil.') || c.startsWith('water.') ? 'Soil & water' : c.startsWith('vegetation.') || c.startsWith('crop.maize_') ? 'Satellite & suitability' : c.startsWith('pests.') || c.startsWith('crop.diagnosis') ? 'Pests & crop health' : c.startsWith('market.') || c.startsWith('logistics.') ? 'Markets & access' : 'Other capabilities'
}
export function scopeLabel(skill: HomeSkill | null) {
  if (!skill?.tools.length) return 'Scope cannot be determined until approved dependencies resolve.'
  if (skill.tools.some(t => t.capabilities.includes('logistics.route'))) return 'Two distinct authorized farms, with selected route endpoints.'
  if (skill.tools.some(t => t.plot_scoped)) return 'Exactly one authorized farm point. Farm boundaries and bulk runs are unsupported.'
  return 'No farm required by the resolved tools; up to five authorized farm references may provide context.'
}
export function unsupportedInputs(skill: HomeSkill | null) {
  if (!skill) return []
  const supported = new Set(skillInputs(skill).map(f => f.key))
  return [...new Set(skill.tools.flatMap(t => Array.isArray(t.input_schema.required) ? t.input_schema.required.filter((key): key is string => typeof key === 'string' && !supported.has(key)) : []))]
}
export function scientificLimits(s: Skill) {
  const caps = [...(s.execution?.manifest ?? s.manifest).required_capabilities, ...(s.execution?.manifest ?? s.manifest).optional_capabilities].join(' ')
  const limits = ['Source coverage, observation dates, units, uncertainty and missing evidence must be checked in the returned results. Tool approval does not establish agronomic validity.']
  if (/weather|rainfall|climate/.test(caps)) limits.push('Gridded forecasts and rainfall estimates are not field weather-station measurements.')
  if (/soil|water/.test(caps)) limits.push('Mapped soil and water estimates do not replace field sampling, laboratory tests or an irrigation assessment.')
  if (/vegetation|suitability/.test(caps)) limits.push('Satellite vegetation and suitability indicators do not prove crop yield, disease, or cause of stress at a farm.')
  if (/pests|diagnosis/.test(caps)) limits.push('Taxonomy, regional pest reports and photo candidates do not establish an outbreak or confirmed diagnosis on this farm.')
  if (/market|logistics/.test(caps)) limits.push('Recorded prices and estimated road routes do not guarantee buyer offers, current prices, road passability or travel time.')
  limits.push('The result is officer decision support, not a released advisory, pesticide prescription or permission to send farmer messages.')
  return limits
}
