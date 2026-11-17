import { webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { campaignInputSchema, documentSchema } from '../src/features/outreach/types'
import { exampleSource, generateGuidance, newCampaignInput } from '../src/features/outreach/catalog'
import { emptyRecipientFilters, filterRecipients, groupRecipients, mapFarmRecipients, recipientById, resolveRecipients, scopedFarms, syntheticRecipients } from '../src/features/outreach/recipients'
import { renderMessage, reviewWarnings, smsEstimate } from '../src/features/outreach/messages'
import { campaignStatus, latestVersion, LocalOutreachService, OUTREACH_STORAGE_KEY } from '../src/features/outreach/service'
import { createOutreachStore } from '../src/features/outreach/store'
import { openOutreachFromSource, outreachTransferStore } from '../src/features/outreach/transfer'
function input() { const v = newCampaignInput('weather'); v.selection.ids = ['DEMO-P0001']; return v }
beforeEach(() => vi.stubGlobal('crypto', webcrypto))
afterEach(() => { vi.unstubAllGlobals(); outreachTransferStore.setState({ pending: null }); window.location.hash = '' })
describe('recipient scope, grouping and content', () => {
  it('handles 2,000 distinct synthetic people without contact addresses and pages at most 50 records', () => {
    expect(syntheticRecipients).toHaveLength(2000); expect(new Set(syntheticRecipients.map(r => r.id)).size).toBe(2000)
    expect(JSON.stringify(syntheticRecipients)).not.toMatch(/@|\+\d{7}|phoneNumber|emailAddress/)
    const service = new LocalOutreachService(), page = service.discoverDemoRecipients(emptyRecipientFilters, 0)
    expect(page.records).toHaveLength(20); expect(page.total).toBe(2000)
    expect(service.discoverDemoRecipients(emptyRecipientFilters, 1).records[0].id).toBe('DEMO-P0021')
    expect(service.discoverDemoRecipients(emptyRecipientFilters, 0, 2000).records).toHaveLength(50)
  })
  it('deduplicates multiple farms for a person and restricts personalization to the imported farm scope', () => {
    expect(mapFarmRecipients(['F-001', 'F-005'], true).ids).toEqual(['DEMO-P0001'])
    const v = input(), r = recipientById.get('DEMO-P0001')!
    expect(scopedFarms(r, v).map(f => f.farmId)).toEqual(['F-001'])
    expect(renderMessage('{{farmer_name}} · {{farm}}', r, v).text).toBe('Demo farmer 0001 · F-001')
    expect(mapFarmRecipients(['F-001'], false)).toEqual({ ids: [], unmapped: ['F-001'] })
  })
  it('filters agricultural context on the same farm and retains explicit selected IDs independently of filters', () => {
    const filters = { ...emptyRecipientFilters, crop: 'Maize', irrigation: 'reliable', language: 'en' as const }
    const matches = filterRecipients(filters)
    expect(matches.length).toBeGreaterThan(0); expect(matches.every(r => r.farms.some(f => f.crop === 'Maize' && f.irrigation === 'reliable'))).toBe(true)
    const v = newCampaignInput('weekly'); v.selection.ids = matches.map(r => r.id); const selected = [...v.selection.ids]
    v.selection.filters.search = 'No matching farmer'; expect(filterRecipients(v.selection.filters)).toHaveLength(0); expect(v.selection.ids).toEqual(selected)
  })
  it('excludes opt-outs, unavailable contacts, missing consent, conflicts and officer exclusions', () => {
    const v = newCampaignInput('weekly'); v.selection.ids = ['DEMO-P0003', 'DEMO-P0011', 'DEMO-P0007', 'DEMO-P0029', 'DEMO-P0037', 'DEMO-P0023']; v.selection.excludedIds = ['DEMO-P0003']
    expect(new Set(resolveRecipients(v).map(r => r.eligibility.reason))).toEqual(new Set(['excluded_by_officer', 'contact_unavailable', 'consent_missing', 'opted_out', 'conflicting_record', 'needs_review']))
    expect(groupRecipients(v)).toHaveLength(0)
  })
  it('holds missing evidence, mixed farm contexts and untranslated language groups', () => {
    const v = newCampaignInput('weekly'); v.selection.ids = ['DEMO-P0001']
    expect(groupRecipients(v)[0].holdReasons.join(' ')).toContain('individual review')
    v.selection.ids = ['DEMO-P0003']; v.source = exampleSource('missing'); v.guidance = generateGuidance('weekly', v.source)
    expect(reviewWarnings(groupRecipients(v)[0], v).join(' ')).toContain('No supporting source evidence')
    v.source = exampleSource('weekly'); v.selection.ids = ['DEMO-P0026']; const group = groupRecipients(v)[0]
    expect(group.language).toBe('am'); expect(reviewWarnings(group, v).join(' ')).toContain('Amharic')
    v.guidance.groupOverrides = [{ groupKey: group.key, body: 'እባክዎ ግልጽ ምልከታ ያቅርቡ።', subject: '', language: 'am', languageReviewed: true }]
    expect(reviewWarnings(group, v)).toEqual([])
  })
  it('allows only approved variables and detects malformed, missing and inherited object placeholders', () => {
    const v = input(), r = recipientById.get('DEMO-P0001')!
    expect(renderMessage('{{follow_up_date}} {{bad}} {{__proto__}} {oops}', r, v).unresolved).toEqual(expect.arrayContaining(['follow_up_date', 'bad', '__proto__', 'malformed placeholder']))
    expect(renderMessage('<b>{{crop}}</b>', r, v).text).toBe('<b>Maize</b>')
    expect(v.guidance.originalText).not.toMatch(/\b\d+\s*(kg|ml|litres?|l\/ha)/i)
  })
  it('estimates GSM extension and Unicode segments without splitting escape units or surrogate pairs', () => {
    expect(smsEstimate('a'.repeat(160))).toMatchObject({ segments: 1, units: 160, encoding: 'GSM-7' })
    expect(smsEstimate('a'.repeat(161)).segments).toBe(2)
    expect(smsEstimate('^'.repeat(80))).toMatchObject({ units: 160, segments: 1 })
    expect(smsEstimate('a'.repeat(152) + '^' + 'a'.repeat(152)).segments).toBe(3)
    expect(smsEstimate('ሀ'.repeat(70))).toMatchObject({ segments: 1, units: 70 })
    expect(smsEstimate('🙂'.repeat(36))).toMatchObject({ segments: 2, units: 72, characters: 36 })
    expect(smsEstimate('')).toMatchObject({ segments: 0, units: 0 })
  })
})
describe('local campaign lifecycle and exact demo reviews', () => {
  it('creates, reloads, edits, duplicates, archives and deletes without runtime delivery state', async () => {
    const service = new LocalOutreachService(), campaign = await service.create(input()), first = latestVersion(campaign)
    expect((await service.read()).campaigns[0]).toEqual(campaign)
    const edited = await service.update(campaign.id, 1, { ...first.input, description: 'Updated purpose' }, 'Clarified purpose', 'Demo officer')
    expect(edited.versions).toHaveLength(2); expect(edited.versions[0]).toEqual(first)
    await expect(service.update(campaign.id, 1, input(), 'Stale', 'Demo officer')).rejects.toThrow('changed')
    const copy = await service.duplicate(campaign.id); expect(copy.id).not.toBe(campaign.id); expect(copy.decisions).toEqual([])
    await service.setArchived(copy.id, true); expect(campaignStatus((await service.read()).campaigns.find(c => c.id === copy.id)!)).toBe('archived')
    await service.remove(copy.id); expect((await service.read()).campaigns).toHaveLength(1)
    expect(localStorage.getItem(OUTREACH_STORAGE_KEY)).not.toMatch(/"delivered"|"queued"|"active"|phoneNumber|emailAddress|data:image|blob:/)
  })
  it('binds demo decisions to exact content and scope, and invalidates them after any saved material change', async () => {
    const service = new LocalOutreachService(), campaign = await service.create(input()), v = latestVersion(campaign)
    await expect(service.review(campaign.id, v.digest, '*', 'approve_demo', 'Demo officer', 'Reviewed', false)).rejects.toThrow('explicitly review')
    const reviewed = await service.review(campaign.id, v.digest, '*', 'approve_demo', 'Demo officer', 'Reviewed scope, evidence and wording', true)
    expect(campaignStatus(reviewed)).toBe('demo_reviewed'); expect(reviewed.decisions[0].authority).toBe('local_demo')
    const changed = structuredClone(v.input); changed.guidance.body += ' Please record observations.'; changed.guidance.originalText = 'Attempt to overwrite the original'
    const edited = await service.update(campaign.id, 1, changed, 'Improved wording', 'Demo officer')
    expect(campaignStatus(edited)).toBe('draft'); expect(latestVersion(edited).input.guidance.originalText).toBe(v.input.guidance.originalText)
    expect(edited.decisions[0].versionDigest).not.toBe(latestVersion(edited).digest)
    await expect(service.review(campaign.id, v.digest, '*', 'approve_demo', 'Demo officer', 'Old target', true)).rejects.toThrow('current')
  })
  it('rejects duplicate or out-of-source recipients, credentials and unsupported review targets', async () => {
    const service = new LocalOutreachService(), v = input()
    expect(campaignInputSchema.safeParse({ ...v, selection: { ...v.selection, ids: ['DEMO-P0001', 'DEMO-P0001'] } }).success).toBe(false)
    await expect(service.create({ ...v, selection: { ...v.selection, ids: ['DEMO-P0003'] } })).rejects.toThrow('outside')
    for (const body of ['token=do-not-store', 'Contact farmer@example.invalid', '+000 000 000 000', 'data:image/png;base64,private', 'blob:private-sample', 'https://fields.example/path?auth=private', 'https://name:pass@localhost/path']) expect(campaignInputSchema.safeParse({ ...v, guidance: { ...v.guidance, body } }).success).toBe(false)
    await expect(service.create({ ...v, source: { ...v.source, mode: 'local_context' } })).rejects.toThrow('authorized')
    const c = await service.create(v)
    await expect(service.review(c.id, latestVersion(c).digest, 'some-other-group', 'approve_demo', 'Demo officer', 'Wrong group', true)).rejects.toThrow('outside')
  })
  it('preserves original crop observations and rejects a review until an officer records a separate correction', async () => {
    const service = new LocalOutreachService(), v = newCampaignInput('health'); v.selection.ids = ['DEMO-P0001']; const c = await service.create(v)
    await expect(service.review(c.id, latestVersion(c).digest, '*', 'approve_demo', 'Demo officer', 'Check', true)).rejects.toThrow('Resolve group warnings')
    const changed = structuredClone(v); changed.guidance.corrections.push({ id: crypto.randomUUID(), originalObservation: v.source.originalObservation, assessment: 'Cause not confirmed; request a clearer photograph and field examination.', reason: 'The illustration cannot establish a diagnosis.', reviewer: 'Demo officer', at: new Date().toISOString() })
    const edited = await service.update(c.id, 1, changed, 'Recorded assessment', 'Demo officer')
    expect(latestVersion(edited).input.source.originalObservation).toBe(v.source.originalObservation)
    expect((await service.review(c.id, latestVersion(edited).digest, '*', 'approve_demo', 'Demo officer', 'Reviewed uncertain observation', true)).decisions[0].recipientIds).toEqual(['DEMO-P0001'])
  })
  it('rejects corrupted, tampered, forged live states and altered review scopes on restore', async () => {
    const service = new LocalOutreachService(), c = await service.create(input()), v = latestVersion(c)
    const reviewed = await service.review(c.id, v.digest, '*', 'approve_demo', 'Demo officer', 'Reviewed', true)
    const forged = { ...reviewed, status: 'delivered' }; expect(documentSchema.safeParse({ version: 1, campaigns: [forged], followUps: [] }).success).toBe(false)
    const raw = JSON.parse(localStorage.getItem(OUTREACH_STORAGE_KEY)!); raw.campaigns[0].decisions[0].recipientIds.push('DEMO-P0029')
    localStorage.setItem(OUTREACH_STORAGE_KEY, JSON.stringify(raw)); expect((await service.read()).campaigns).toEqual([])
    raw.campaigns[0].decisions = []; raw.campaigns[0].versions[0].input.guidance.body = 'Tampered content'
    localStorage.setItem(OUTREACH_STORAGE_KEY, JSON.stringify(raw)); expect((await service.read()).warning).toBeTruthy()
  })
  it('serializes writes and handles blocked browser storage without claiming a save', async () => {
    const service = new LocalOutreachService(); await Promise.all([service.create(input()), service.create(input())]); expect((await service.read()).campaigns).toHaveLength(2)
    const blocked = new LocalOutreachService(() => { throw new Error('Blocked') }), store = createOutreachStore(blocked); await store.getState().load()
    expect(store.getState().warning).toBeTruthy(); await expect(blocked.create(input())).rejects.toThrow('Could not save')
    expect(store.getState().campaigns).toEqual([])
  })
  it('persists local response drafts but never returns a successful delivery or AI operation', async () => {
    const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const service = new LocalOutreachService()
    const follow = await service.saveFollowUp({ responseId: 'SAMPLE-RESPONSE-1', kind: 'needs_inspection', note: 'Unconfirmed concern; request officer inspection.', reviewer: 'Demo officer' })
    expect((await service.read()).followUps[0]).toEqual(follow)
    const replies = await Promise.all([service.backend.discoverRecipients({ search: '', filters: {}, limit: 20 }), service.backend.generateGuidance({ campaignId: 'future', version: 1, approvedSkillId: 'future', evidenceIds: [] }), service.backend.submitApprovedDelivery({ campaignId: 'future', versionDigest: 'local', recipientSnapshotDigest: 'local', approvedConnectionId: 'none', connectionRevision: 1, backendApprovalId: 'none', idempotencyKey: 'test', explicitAuthorization: true })])
    expect(replies.every(r => !r.ok && r.error.code === 'BACKEND_REQUIRED')).toBe(true); expect(fetch).not.toHaveBeenCalled()
  })
  it('transfers source context only in memory and does not fabricate farmer mappings for real Home IDs', async () => {
    const source = { ...exampleSource('weather'), mode: 'local_context' as const }
    await openOutreachFromSource(source, 'weather', false, 'Home')
    expect(outreachTransferStore.getState().pending?.input.selection.ids).toEqual([])
    expect(outreachTransferStore.getState().pending?.unmappedFarmIds).toEqual(['F-001'])
    expect(localStorage.getItem(OUTREACH_STORAGE_KEY)).toBeNull()
  })
})
