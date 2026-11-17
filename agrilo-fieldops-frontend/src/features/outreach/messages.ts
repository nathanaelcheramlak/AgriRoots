import type { CampaignInput, Recipient, RecipientGroup } from './types'
import { languageLabels } from './types'
import { recipientById, scopedFarms } from './recipients'
export const personalizationVariables = ['farmer_name', 'crop', 'farm', 'location', 'follow_up_date'] as const
export function renderMessage(template: string, recipient: Recipient, input: CampaignInput) {
  const farms = scopedFarms(recipient, input)
  const variables: Record<string, string> = { farmer_name: recipient.displayName, crop: [...new Set(farms.map(f => f.crop))].join(' / '), farm: farms.map(f => f.farmId).join(', '), location: [...new Set(farms.map(f => f.location))].join(' / '), follow_up_date: input.communication.followUpDate }
  const unresolved: string[] = []
  const text = template.replace(/\{\{\s*([^{}]+?)\s*\}\}/g, (literal, variable: string) => { const value = Object.hasOwn(variables, variable) && personalizationVariables.includes(variable as typeof personalizationVariables[number]) ? variables[variable] : ''; if (!value) { unresolved.push(variable); return literal } return value })
  if (/[{}]/.test(text.replace(/\{\{[^{}]*\}\}/g, ''))) unresolved.push('malformed placeholder')
  return { text, unresolved: [...new Set(unresolved)] }
}
export function groupMessage(group: RecipientGroup, input: CampaignInput) {
  const override = input.guidance.groupOverrides.find(o => o.groupKey === group.key)
  return { body: override?.body ?? input.guidance.body, subject: override?.subject ?? input.guidance.subject, language: override?.language ?? 'en', languageReviewed: override?.languageReviewed ?? group.language === 'en' }
}
export function reviewWarnings(group: RecipientGroup, input: CampaignInput) {
  const warnings = [...group.holdReasons], message = groupMessage(group, input)
  if (!message.body.trim()) warnings.push('Write the farmer-facing message.')
  if (input.communication.channel === 'email' && !message.subject.trim()) warnings.push('Email subject is required.')
  if (message.language !== group.language || !message.languageReviewed) warnings.push('Provide and review wording in ' + languageLabels[group.language] + '. Language selection does not translate text.')
  if (input.guidance.unsupported) warnings.push('Unsupported recommendation flagged: ' + input.guidance.unsupportedReason)
  if (input.source.kind === 'crop_case' && !input.guidance.corrections.length) warnings.push('Record an officer assessment of the uncertain crop observation.')
  if (input.guidance.corrections.some(c => c.originalObservation !== input.source.originalObservation)) warnings.push('A correction does not match the preserved source observation.')
  for (const id of group.recipientIds) {
    const recipient = recipientById.get(id)
    if (!recipient) { warnings.push('Recipient record unavailable.'); continue }
    const rendered = renderMessage(message.body, recipient, input), subject = renderMessage(message.subject, recipient, input)
    if (rendered.unresolved.length || subject.unresolved.length) { warnings.push('Unresolved placeholders: ' + [...new Set([...rendered.unresolved, ...subject.unresolved])].join(', ')); break }
  }
  return [...new Set(warnings)]
}
const basic = new Set(Array.from('@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !"#¤%&\'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà'))
const extended = new Set(Array.from('\f^{}\\[~]|€'))
export function smsEstimate(text: string) {
  const characters = Array.from(text), gsm = characters.every(c => basic.has(c) || extended.has(c))
  const lengths = characters.map(c => gsm ? extended.has(c) ? 2 : 1 : c.length), units = lengths.reduce((a, b) => a + b, 0)
  const single = gsm ? 160 : 70, capacity = gsm ? 153 : 67
  let segments = units ? 1 : 0
  if (units > single) { segments = 1; let used = 0; for (const length of lengths) { if (used + length > capacity) { segments++; used = 0 } used += length } }
  return { characters: characters.length, units, encoding: gsm ? 'GSM-7' : 'Unicode / UCS-2', segments }
}
