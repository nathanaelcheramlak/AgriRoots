import { syntheticFarms } from '../../demo/synthetic-farms'
import type { CampaignInput, CommunicationChannel, Recipient, RecipientEligibility, RecipientFarmAssociation, RecipientFilters, RecipientGroup } from './types'
export const emptyRecipientFilters: RecipientFilters = { search: '', crop: '', location: '', risk: '', stage: '', irrigation: '', monitoring: '', language: '', channel: '' }
const firstFarms = [[0, 4], [1, 5], [2], [3], [6], [7], [8], [9], [10], [11]]
export const syntheticRecipients: Recipient[] = Array.from({ length: 2000 }, (_, i) => {
  const associated: RecipientFarmAssociation[] = i < 10 ? firstFarms[i].map(index => {
    const f = syntheticFarms[index]
    return { farmId: f.id, crop: f.currentCrop, location: 'Adama demo cluster', risk: f.riskLevel, stage: index === 8 ? 'Not recorded' : 'Vegetative (sample)', irrigation: f.irrigationAccess, monitoring: f.riskLevel === 'high' ? 'flagged' : 'not_assessed', evidenceAvailable: f.dataQuality !== 'unknown' }
  }) : [{ farmId: 'DEMO-F' + String(i + 1).padStart(4, '0'), crop: ['Maize', 'Teff', 'Wheat', 'Sorghum', 'Vegetables'][i % 5], location: ['Adama demo cluster', 'Bishoftu demo cluster', 'Batu demo cluster'][i % 3], risk: ['high', 'moderate', 'low', 'unknown'][i % 4], stage: i % 17 === 0 ? 'Not recorded' : 'Vegetative (sample)', irrigation: ['none', 'limited', 'reliable', 'unknown'][Math.floor(i / 5) % 4], monitoring: i % 4 === 0 ? 'flagged' : 'not_assessed', evidenceAvailable: i % 13 !== 0 && i % 4 !== 3 }]
  const available: CommunicationChannel[] = []
  if (i % 11 !== 10) available.push('sms', 'voice')
  if (i % 4 === 0) available.push('email')
  if (i % 3 === 0) available.push('smartphone')
  return { id: 'DEMO-P' + String(i + 1).padStart(4, '0'), displayName: 'Demo farmer ' + String(i + 1).padStart(4, '0'), farms: associated, preference: { language: i < 10 ? 'en' : (['en', 'am', 'om'] as const)[i % 3], preferred: i % 3 === 1 ? 'voice' : 'sms', available, consent: { sms: i % 7 === 6 ? 'missing' : 'granted', voice: i % 7 === 6 ? 'missing' : 'granted', email: i % 7 === 6 ? 'missing' : 'granted', smartphone: i % 7 === 6 ? 'missing' : 'granted' } }, recordState: i % 37 === 36 ? 'conflict' : i % 23 === 22 ? 'needs_review' : 'consistent', optedOut: i % 29 === 28, mode: 'synthetic' }
})
export const recipientById = new Map(syntheticRecipients.map(r => [r.id, r]))
export function filterRecipients(filters: RecipientFilters, records = syntheticRecipients) {
  const q = filters.search.toLowerCase()
  return records.filter(r => (!q || (r.id + ' ' + r.displayName + ' ' + r.farms.map(f => f.farmId).join(' ')).toLowerCase().includes(q)) && (!filters.language || r.preference.language === filters.language) && (!filters.channel || r.preference.available.includes(filters.channel)) && r.farms.some(f => (!filters.crop || f.crop === filters.crop) && (!filters.location || f.location === filters.location) && (!filters.risk || f.risk === filters.risk) && (!filters.stage || f.stage === filters.stage) && (!filters.irrigation || f.irrigation === filters.irrigation) && (!filters.monitoring || f.monitoring === filters.monitoring)))
}
export function eligibility(recipient: Recipient, input: Pick<CampaignInput, 'communication' | 'selection'>): RecipientEligibility {
  let reason: RecipientEligibility['reason'] = 'eligible'
  const channel = input.communication.channel
  if (input.selection.excludedIds.includes(recipient.id)) reason = 'excluded_by_officer'
  else if (recipient.optedOut || recipient.preference.consent[channel] === 'opted_out') reason = 'opted_out'
  else if (recipient.recordState === 'conflict') reason = 'conflicting_record'
  else if (recipient.recordState === 'needs_review') reason = 'needs_review'
  else if (!recipient.preference.available.includes(channel)) reason = 'contact_unavailable'
  else if (recipient.preference.consent[channel] !== 'granted') reason = 'consent_missing'
  else if (input.communication.language !== 'preferred' && input.communication.language !== recipient.preference.language) reason = 'language_mismatch'
  return { eligible: reason === 'eligible', reason }
}
export function scopedFarms(recipient: Recipient, input: Pick<CampaignInput, 'selection'>) {
  return input.selection.scopeFarmIds.length ? recipient.farms.filter(f => input.selection.scopeFarmIds.includes(f.farmId)) : recipient.farms
}
export function resolveRecipients(input: Pick<CampaignInput, 'selection' | 'communication'>) {
  return input.selection.ids.map(id => { const recipient = recipientById.get(id); if (!recipient) throw new Error('Unknown demonstration recipient.'); return { recipient, eligibility: eligibility(recipient, input) } })
}
export function mapFarmRecipients(farmIds: string[], synthetic: boolean) {
  if (!synthetic) return { ids: [], unmapped: farmIds }
  const matches = syntheticRecipients.filter(r => r.farms.some(f => farmIds.includes(f.farmId)))
  return { ids: matches.map(r => r.id), unmapped: farmIds.filter(id => !matches.some(r => r.farms.some(f => f.farmId === id))) }
}
export function groupRecipients(input: Pick<CampaignInput, 'selection' | 'communication' | 'category' | 'source'>): RecipientGroup[] {
  const groups = new Map<string, RecipientGroup>()
  for (const { recipient: r, eligibility: e } of resolveRecipients(input)) {
    if (!e.eligible) continue
    const farms = scopedFarms(r, input), crops = [...new Set(farms.map(f => f.crop))], irrigation = [...new Set(farms.map(f => f.irrigation))], risks = [...new Set(farms.map(f => f.risk))], stages = [...new Set(farms.map(f => f.stage))]
    const crop = crops.join(' / '), water = irrigation.join(' / '), language = r.preference.language
    const holds: string[] = []
    if (!farms.length) holds.push('No farm association in this scope.')
    if (crops.length > 1 || irrigation.length > 1) holds.push('Different farm conditions require individual review.')
    if (input.category !== 'general' && input.category !== 'inspection') {
      if (farms.some(f => !f.evidenceAvailable || f.stage === 'Not recorded')) holds.push('Missing agricultural evidence or crop-stage context.')
      if (input.source.kind !== 'officer' && !input.source.evidence.some(e => e.availability !== 'unavailable')) holds.push('No supporting source evidence is available.')
      if (input.source.farmIds.length && farms.some(f => {
        const linked = input.source.evidence.filter(e => e.farmIds?.includes(f.farmId) || (!e.farmIds && input.source.farmIds.length === 1))
        return !linked.some(e => e.availability !== 'unavailable')
      })) holds.push('Farm-specific source evidence is unavailable or missing.')
    }
    const key = [crop, water, risks.join('/'), stages.join('/'), language, holds.join('|')].join('::')
    const group = groups.get(key) ?? { key, label: crop + ' · ' + (holds.length ? 'Hold for review' : water + ' irrigation'), recipientIds: [], language, crop, irrigation: water, holdReasons: holds }
    group.recipientIds.push(r.id); groups.set(key, group)
  }
  return [...groups.values()].sort((a, b) => a.language.localeCompare(b.language) || a.label.localeCompare(b.label))
}
