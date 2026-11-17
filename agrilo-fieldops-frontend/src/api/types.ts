import type { z } from 'zod'
import type { analysisSchema, assistantResponseSchema, candidateSchema, draftSchema, evidenceSchema, farmSchema, mapCommandSchema, observationSchema, providerSchema, selectionSchema } from './schemas'
export type Selection = z.infer<typeof selectionSchema>
export type Farm = z.infer<typeof farmSchema>
export type CropCandidate = z.infer<typeof candidateSchema>
export type EvidenceRecord = z.infer<typeof evidenceSchema>
export type ProviderStatus = z.infer<typeof providerSchema>
export type AreaAnalysis = z.infer<typeof analysisSchema>
export type MapCommand = z.infer<typeof mapCommandSchema>
export type DraftAdvisory = z.infer<typeof draftSchema>
export type FieldObservation = z.infer<typeof observationSchema>
export type AssistantResponse = z.infer<typeof assistantResponseSchema>
export type AnalysisPhase = 'idle' | 'selecting' | 'loading_farms' | 'screening' | 'preparing_candidates' | 'completed' | 'partial' | 'failed'
export type Filters = { risk: string; crop: string; candidateCrop: string; drought: string; search: string }
export type LayerVisibility = { farms: boolean; selection: boolean; soil: boolean; rainfall: boolean; satellite: boolean; pests: boolean }
export type AssistantMessage = { id: string; role: 'user' | 'assistant'; text: string; at: string }
export type AssistantContext = { selection: Selection | null; farms: Farm[]; selectedFarmId: string | null; providers: ProviderStatus[] }
export type MapFocus = { serial: number; type: 'selection' | 'farms' | 'farm' | 'reset'; farmIds?: string[] }
export type AnalysisJob = { job_id: string; status: 'queued' | 'running' | 'completed' | 'partial' | 'failed'; stage?: AnalysisPhase; updatedAt: string; result?: AreaAnalysis; error?: string }
