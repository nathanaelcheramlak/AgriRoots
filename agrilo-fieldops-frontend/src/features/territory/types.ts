import { z } from 'zod'
import { boundarySchema } from './geometry'
import type { HomePlot } from '../../api/home-contracts'

const text = (n: number) => z.string().trim().max(n)
export const channels = ['sms', 'voice', 'smartphone', 'email', 'none', 'in-person'] as const
export const crops = ['Unknown', 'Maize', 'Wheat', 'Teff', 'Sorghum', 'Barley', 'Coffee', 'Vegetables', 'Other'] as const
export const territorySchema = z.object({
  id: text(120).min(1), name: text(120).min(1), region: text(100), district: text(100), description: text(600),
  officeId: text(120).optional(), status: z.enum(['local-draft', 'pending-approval', 'assigned', 'inactive']),
  origin: z.enum(['local', 'backend', 'synthetic']), boundary: boundarySchema, createdAt: z.iso.datetime(),
  authorizedPlotIds: z.array(text(120)).max(10000).optional(),
  revision: z.number().int().positive().optional(), area_m2: z.number().positive().optional(),
}).strict().superRefine((v, ctx) => { if (v.status === 'assigned' && v.origin !== 'backend') ctx.addIssue({ code: 'custom', message: 'Only backend assignments are authoritative.' }) })
export type Territory = z.infer<typeof territorySchema>
export const farmerSchema = z.object({
  id: text(120).min(1), reference: text(80).min(1), displayName: text(120).min(1), village: text(100), household: text(100),
  language: text(40), channel: z.enum(channels), availability: z.enum(['unknown', 'available', 'unavailable']),
  consent: z.enum(['unknown', 'granted', 'declined']), verification: z.enum(['unverified', 'verified-demo']),
  phone: text(40), email: text(160), preferences: text(600), notes: text(1000), origin: z.enum(['memory', 'synthetic', 'backend']),
  revision: z.number().int().positive().optional(), synthetic: z.boolean().optional(),
}).strict()
export type FarmerProfile = z.infer<typeof farmerSchema>
export const plotSchema = z.object({
  id: z.string().min(1), territoryId: text(120), name: text(120).min(1), geometry: boundarySchema,
  farmerIds: z.array(text(120)).max(10), status: z.enum(['local-draft', 'registered', 'review-required']), origin: z.enum(['local', 'synthetic', 'backend']),
  location: text(200), notes: text(1000), observation: text(1000), createdAt: z.iso.datetime(),
  revision: z.number().int().positive().optional(),
}).strict().superRefine((v, ctx) => { if (v.origin !== 'backend' && (!v.id.startsWith('local-plot-') || v.status !== 'local-draft')) ctx.addIssue({ code: 'custom', message: 'Local plots cannot claim registration.' }) })
export type FarmPlot = z.infer<typeof plotSchema>
export const seasonSchema = z.object({
  id: text(120), plotId: text(120), crop: z.enum(crops), plantingDate: text(10).refine(v => !v || (/^\d{4}-\d{2}-\d{2}$/.test(v) && !Number.isNaN(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v), 'Choose a valid planting date.'),
  stage: z.enum(['Unknown', 'Land preparation', 'Planted', 'Vegetative', 'Flowering', 'Maturing', 'Harvested']),
  irrigation: z.enum(['unknown', 'none', 'available']), irrigationMethod: z.enum(['Unknown', 'Rainfed', 'Drip', 'Sprinkler', 'Surface', 'Other']), previousCrop: z.enum(crops),
}).strict()
export type CropSeason = z.infer<typeof seasonSchema>
export type MapInteractionMode = 'navigate' | 'draw-territory' | 'edit-territory' | 'draw-farm-plot' | 'edit-farm-plot' | 'select-farm' | 'select-analysis-area'
export type AssignmentState =
  | { status: 'unsupported' | 'unavailable' | 'connection-unavailable'; message: string }
  | { status: 'available'; territories: Territory[] }
export type SelectedFarmContext =
  | { origin: 'local'; plotId: string; territoryId: string; authorized: false }
  | { origin: 'backend'; plot: HomePlot; authorized: true }
export type Panel = 'territory-setup' | 'territory' | 'plot-form' | 'plot-details' | 'farmers' | 'farmer-form' | 'farmer-details' | null

export interface TerritorySubmission { kind: 'proposal'; boundary: Territory['boundary']; name: string; region: string; district: string; expectedOfficeId?: string }
export interface FarmerRegistration { kind: 'farmer-registration'; profile: FarmerProfile; consentRecorded: boolean }
export interface PlotRegistration { kind: 'plot-registration'; territoryId: string; geometry: FarmPlot['geometry']; farmerIds: string[]; season: CropSeason }
export interface MonitoringFarmContext { territoryId: string; plotIds: string[]; seasons: CropSeason[]; observations: { plotId: string; text: string }[]; authority: 'local-preview' | 'backend' }
export interface OutreachFarmContext { territoryId: string; farmerIds: string[]; plotIds: string[]; preferences: Pick<FarmerProfile, 'id' | 'language' | 'channel' | 'consent'>[]; evidenceIds: string[]; authority: 'local-preview' | 'backend' }
