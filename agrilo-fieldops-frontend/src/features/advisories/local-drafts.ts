import { z } from 'zod'
import { draftSchema } from '../../api/schemas'
import type { DraftAdvisory, Farm } from '../../api/types'
export const DRAFT_KEY = 'agrilo-fieldops:isolated-demo-drafts:v1'
export function readDrafts(): DraftAdvisory[] { try { return z.array(draftSchema).max(100).parse(JSON.parse(localStorage.getItem(DRAFT_KEY) ?? '[]')) } catch { return [] } }
export function saveDrafts(drafts: DraftAdvisory[]): boolean { try { localStorage.setItem(DRAFT_KEY, JSON.stringify(drafts)); return true } catch { return false } }
export function makeDraft(farm: Farm): DraftAdvisory {
  const now = new Date().toISOString()
  return draftSchema.parse({ id: `D-${crypto.randomUUID().slice(0, 8).toUpperCase()}`, farmId: farm.id, createdAt: now, category: 'Crop candidate review', mode: 'mock', status: 'draft',
    text: farm.candidates.length ? `Review ${farm.candidates.map(c => c.crop).join(' and ')} as illustrative candidates for ${farm.displayName}. ${farm.riskReasons.join(' ')} Confirm water availability, soil conditions, seed suitability, and planting window in the field. These candidates are unvalidated and require agronomic review.` : `Arrange a field inspection for ${farm.displayName}. Evidence is insufficient for crop candidates. Collect missing soil and rainfall context before making a recommendation.`,
    evidence: farm.evidence, missingData: ['Satellite and pest integrations not connected.', ...farm.evidence.filter(e => e.status !== 'available').map(e => `${e.variable}: ${e.status}`)], audit: [{ status: 'draft', reviewer: 'Demo officer (creator)', at: now }],
  })
}
