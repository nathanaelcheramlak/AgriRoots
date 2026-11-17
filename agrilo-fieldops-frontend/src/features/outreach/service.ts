import { campaignInputSchema, campaignSchema, documentSchema, followUpSchema, reviewSchema } from './types'
import type { CampaignInput, CampaignStatus, OutreachCampaign, OutreachFollowUp, RecipientFilters, ReviewDecision } from './types'
import type { OutreachBackend } from './backend-contract'
import { unsupportedOutreachBackend } from './backend-contract'
import { campaignTemplates, generateGuidance } from './catalog'
import { demonstrationAttempts, demonstrationResponses } from './fixtures'
import { filterRecipients, groupRecipients, resolveRecipients, scopedFarms } from './recipients'
import { renderMessage, reviewWarnings } from './messages'
export const OUTREACH_STORAGE_KEY = 'agrilo-fieldops:outreach:v1'
export async function localDigest(value: unknown): Promise<string> {
  if (!globalThis.crypto?.subtle) throw new Error('Local content fingerprinting is unavailable. Open this app on localhost or HTTPS.')
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(value)))
  return [...new Uint8Array(bytes)].map(b => b.toString(16).padStart(2, '0')).join('')
}
export const latestVersion = (campaign: OutreachCampaign) => campaign.versions[campaign.versions.length - 1]
export function groupDecision(campaign: OutreachCampaign, key: string) { const v = latestVersion(campaign); return campaign.decisions.filter(d => d.versionDigest === v.digest && (d.groupKey === '*' || d.groupKey === key) && d.action !== 'submit_review').at(-1) }
export function campaignStatus(campaign: OutreachCampaign): CampaignStatus {
  if (campaign.archived) return 'archived'
  const version = latestVersion(campaign), decisions = campaign.decisions.filter(d => d.versionDigest === version.digest), groups = groupRecipients(version.input), last = decisions.at(-1)
  if (!last || last.action === 'return_draft') return 'draft'
  if (groups.length && groups.every(g => !reviewWarnings(g, version.input).length && groupDecision(campaign, g.key)?.action === 'approve_demo')) return 'demo_reviewed'
  if (last.action === 'request_evidence') return 'changes_requested'
  if (last.action === 'reject') return 'rejected'
  return 'awaiting_review'
}
function validateScope(input: CampaignInput) {
  resolveRecipients(input)
  const scoped = input.selection.scopeFarmIds
  if (input.source.farmIds.length) {
    if (input.source.mode !== 'synthetic' && input.source.recipientContext !== 'synthetic') throw new Error('An authorized farmer/contact mapping is required for this Home context. Demonstration contacts cannot stand in for real farmers.')
    if (!scoped.length || scoped.some(id => !input.source.farmIds.includes(id))) throw new Error('Farm scope must remain within the imported source selection.')
    if (resolveRecipients(input).some(({ recipient }) => !scopedFarms(recipient, input).length)) throw new Error('A recipient is outside the selected source farms.')
  }
  const groups = groupRecipients(input)
  if (input.guidance.groupOverrides.some(o => !groups.some(g => g.key === o.groupKey))) throw new Error('A group changed. Reset obsolete group edits before saving the new scope.')
}
async function makeSnapshot(input: CampaignInput, at = new Date().toISOString(), id: string = crypto.randomUUID()) {
  const records = resolveRecipients(input), data = { datasetVersion: 'outreach-demo-v1' as const, memberIds: input.selection.ids, eligibleIds: records.filter(r => r.eligibility.eligible).map(r => r.recipient.id), excluded: records.filter(r => !r.eligibility.eligible).map(r => ({ recipientId: r.recipient.id, reason: r.eligibility.reason })) }
  return { id, ...data, capturedAt: at, digest: await localDigest(data) }
}
export interface OutreachService {
  readonly backend: OutreachBackend
  listTemplates(): typeof campaignTemplates
  discoverDemoRecipients(filters: RecipientFilters, page: number, pageSize?: number): { records: ReturnType<typeof filterRecipients>; total: number }
  resolveEligibility: typeof resolveRecipients
  groupRecipients: typeof groupRecipients
  renderTemplate: typeof renderMessage
  generateGuidance: typeof generateGuidance
  read(): Promise<{ campaigns: OutreachCampaign[]; followUps: OutreachFollowUp[]; warning: string | null }>
  create(input: CampaignInput): Promise<OutreachCampaign>
  update(id: string, expectedVersion: number, input: CampaignInput, reason: string, editor: string): Promise<OutreachCampaign>
  duplicate(id: string): Promise<OutreachCampaign>
  remove(id: string): Promise<void>
  setArchived(id: string, archived: boolean): Promise<void>
  review(id: string, versionDigest: string, groupKey: string, action: ReviewDecision['action'], reviewer: string, reason: string, acknowledged: boolean): Promise<OutreachCampaign>
  saveFollowUp(input: Pick<OutreachFollowUp, 'responseId' | 'kind' | 'note' | 'reviewer'>): Promise<OutreachFollowUp>
  demonstrationHistory(): typeof demonstrationAttempts
  demonstrationResponses(): typeof demonstrationResponses
}
export class LocalOutreachService implements OutreachService {
  readonly backend = unsupportedOutreachBackend()
  readonly resolveEligibility = resolveRecipients
  readonly groupRecipients = groupRecipients
  readonly renderTemplate = renderMessage
  readonly generateGuidance = generateGuidance
  private queue: Promise<void> = Promise.resolve()
  constructor(private readonly storage: () => Storage = () => window.localStorage) {}
  listTemplates() { return campaignTemplates }
  discoverDemoRecipients(filters: RecipientFilters, page: number, pageSize = 20) { const records = filterRecipients(filters), limit = Math.min(50, Math.max(1, pageSize)); return { records: records.slice(Math.max(0, page) * limit, (Math.max(0, page) + 1) * limit), total: records.length } }
  demonstrationHistory() { return demonstrationAttempts }
  demonstrationResponses() { return demonstrationResponses }
  async read() {
    try {
      const raw = this.storage().getItem(OUTREACH_STORAGE_KEY)
      if (!raw) return { campaigns: [], followUps: [], warning: null }
      const document = documentSchema.parse(JSON.parse(raw))
      if (new Set(document.campaigns.map(c => c.id)).size !== document.campaigns.length) throw new Error('Duplicate campaigns')
      for (const campaign of document.campaigns) {
        let previous = ''
        for (const [index, version] of campaign.versions.entries()) {
          validateScope(version.input)
          if (version.number !== index + 1 || version.previousDigest !== previous) throw new Error('Invalid revision history')
          const snapshot = await makeSnapshot(version.input, version.snapshot.capturedAt, version.snapshot.id)
          if (JSON.stringify(snapshot) !== JSON.stringify(version.snapshot) || version.digest !== await localDigest({ number: version.number, input: version.input, snapshotDigest: snapshot.digest, previousDigest: previous })) throw new Error('Changed local snapshot')
          previous = version.digest
        }
        for (const decision of campaign.decisions) {
          const target = campaign.versions.find(v => v.number === decision.version && v.digest === decision.versionDigest && v.snapshot.digest === decision.snapshotDigest && v.input.communication.channel === decision.channel)
          if (!target) throw new Error('Invalid review target')
          const groups = groupRecipients(target.input).filter(g => decision.groupKey === '*' || decision.groupKey === g.key)
          if (decision.groupKey !== '*' && !groups.length) throw new Error('Invalid review group')
          if (JSON.stringify(groups.flatMap(g => g.recipientIds).sort()) !== JSON.stringify(decision.recipientIds)) throw new Error('Changed review scope')
          if (decision.action === 'approve_demo' && (!groups.length || groups.some(g => reviewWarnings(g, target.input).length))) throw new Error('Invalid demo approval')
        }
      }
      if (new Set(document.followUps.map(f => f.responseId)).size !== document.followUps.length) throw new Error('Duplicate response follow-ups')
      return { campaigns: document.campaigns, followUps: document.followUps, warning: null }
    } catch { return { campaigns: [], followUps: [], warning: 'Local Outreach drafts could not be read. No approval or delivery state was restored. Save a new draft to replace invalid local data.' } }
  }
  private async write(campaigns: OutreachCampaign[], followUps: OutreachFollowUp[]) {
    const document = documentSchema.parse({ version: 1, campaigns, followUps })
    try { this.storage().setItem(OUTREACH_STORAGE_KEY, JSON.stringify(document)) }
    catch { throw new Error('Could not save on this device. Browser storage may be unavailable or full. Your changes have not been saved.') }
  }
  private serialize<T>(operation: () => Promise<T>) { const result = this.queue.then(operation); this.queue = result.then(() => {}, () => {}); return result }
  private async revision(input: CampaignInput, number: number, previousDigest: string, reason: string, editor: string) {
    const parsed = campaignInputSchema.parse(input)
    parsed.selection.ids.sort(); parsed.selection.excludedIds.sort(); validateScope(parsed)
    const snapshot = await makeSnapshot(parsed), at = new Date().toISOString()
    return { number, at, input: parsed, snapshot, previousDigest, reason, editor, digest: await localDigest({ number, input: parsed, snapshotDigest: snapshot.digest, previousDigest }) }
  }
  async create(input: CampaignInput) {
    return this.serialize(async () => {
      const d = await this.read(), version = await this.revision(input, 1, '', 'Created local campaign draft', 'Local officer · identity unverified')
      const campaign = campaignSchema.parse({ id: crypto.randomUUID(), createdAt: version.at, owner: 'this_device', archived: false, versions: [version], decisions: [] })
      await this.write([...d.campaigns, campaign], d.followUps); return campaign
    })
  }
  async update(id: string, expectedVersion: number, input: CampaignInput, reason: string, editor: string) {
    return this.serialize(async () => {
      const d = await this.read(), old = d.campaigns.find(c => c.id === id)
      if (!old || latestVersion(old).number !== expectedVersion) throw new Error('This campaign changed. Reopen its current version.')
      if (old.versions.length >= 20) throw new Error('Local revision history is full. Duplicate the campaign or use a future backend for longer history.')
      const current = latestVersion(old), next = structuredClone(input)
      if (JSON.stringify(next.source) === JSON.stringify(current.input.source) && next.templateId === current.input.templateId) next.guidance.originalText = current.input.guidance.originalText
      const campaign = campaignSchema.parse({ ...old, versions: [...old.versions, await this.revision(next, expectedVersion + 1, current.digest, reason, editor)] })
      await this.write(d.campaigns.map(c => c.id === id ? campaign : c), d.followUps); return campaign
    })
  }
  async duplicate(id: string) { const old = (await this.read()).campaigns.find(c => c.id === id); if (!old) throw new Error('Campaign not found.'); const input = structuredClone(latestVersion(old).input); input.name = input.name.slice(0, 111) + ' (copy)'; return this.create(input) }
  async remove(id: string) { return this.serialize(async () => { const d = await this.read(); await this.write(d.campaigns.filter(c => c.id !== id), d.followUps) }) }
  async setArchived(id: string, archived: boolean) { return this.serialize(async () => { const d = await this.read(); await this.write(d.campaigns.map(c => c.id === id ? { ...c, archived } : c), d.followUps) }) }
  async review(id: string, versionDigest: string, groupKey: string, action: ReviewDecision['action'], reviewer: string, reason: string, acknowledged: boolean) {
    return this.serialize(async () => {
      const d = await this.read(), old = d.campaigns.find(c => c.id === id)
      if (!old || old.archived || latestVersion(old).digest !== versionDigest) throw new Error('Open the current, unarchived campaign before reviewing.')
      const v = latestVersion(old), groups = groupRecipients(v.input), scope = groupKey === '*' ? groups : groups.filter(g => g.key === groupKey)
      if (groupKey !== '*' && !scope.length) throw new Error('This group is outside the current recipient snapshot.')
      if (action === 'approve_demo' && (!acknowledged || !scope.length || scope.some(g => reviewWarnings(g, v.input).length))) throw new Error('Resolve group warnings and explicitly review the exact scope, evidence and message before recording a demo approval.')
      const decision = reviewSchema.parse({ id: crypto.randomUUID(), version: v.number, versionDigest, snapshotDigest: v.snapshot.digest, groupKey, recipientIds: scope.flatMap(g => g.recipientIds).sort(), channel: v.input.communication.channel, action, reviewer, reason, at: new Date().toISOString(), authority: 'local_demo' })
      const campaign = campaignSchema.parse({ ...old, decisions: [...old.decisions, decision] }); await this.write(d.campaigns.map(c => c.id === id ? campaign : c), d.followUps); return campaign
    })
  }
  async saveFollowUp(input: Pick<OutreachFollowUp, 'responseId' | 'kind' | 'note' | 'reviewer'>) {
    return this.serialize(async () => { const d = await this.read(), old = d.followUps.find(f => f.responseId === input.responseId), followUp = followUpSchema.parse({ ...input, id: old?.id ?? crypto.randomUUID(), version: (old?.version ?? 0) + 1, updatedAt: new Date().toISOString(), mode: 'local_demo' }); await this.write(d.campaigns, [...d.followUps.filter(f => f.id !== followUp.id), followUp]); return followUp })
  }
}
