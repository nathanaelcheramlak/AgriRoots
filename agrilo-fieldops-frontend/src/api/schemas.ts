import { z } from 'zod'

export const riskSchema = z.enum(['high', 'moderate', 'low', 'unknown'])
const position = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90)])
export const bboxSchema = z.tuple([z.number().min(-180).max(180), z.number().min(-90).max(90), z.number().min(-180).max(180), z.number().min(-90).max(90)])
  .refine(([w, s, e, n]) => w < e && s < n, 'Bounds must have positive area and cannot cross the antimeridian.')
export const selectionSchema = z.object({
  selection_id: z.string(), selection_type: z.literal('rectangle'), bbox: bboxSchema,
  geometry: z.object({ type: z.literal('Polygon'), coordinates: z.array(z.array(position).length(5)).length(1) }),
  client_context: z.object({ trigger: z.enum(['map_rectangle_selected', 'map_rectangle_edited', 'demo_area', 'manual_area']) }),
}).superRefine((s, ctx) => {
  const [w, south, e, n] = s.bbox
  const expected = [[w, south], [e, south], [e, n], [w, n], [w, south]]
  if (JSON.stringify(s.geometry.coordinates[0]) !== JSON.stringify(expected)) ctx.addIssue({ code: 'custom', message: 'Rectangle ring must be closed, longitude-first, and match the bbox.' })
  const area = (e - w) * (n - south) * 111.32 ** 2 * Math.cos((south + n) / 2 * Math.PI / 180)
  if (area > 2500 || e - w > 2 || n - south > 2) ctx.addIssue({ code: 'custom', message: 'Area is too large. Select a smaller area (maximum 2,500 km² and 2° per side).' })
})
export const candidateSchema = z.object({ crop: z.string(), status: z.enum(['candidate', 'conditional', 'not_recommended']), reasons: z.array(z.string()).min(1), constraints: z.array(z.string()).min(1), evidenceIds: z.array(z.string()).min(1) })
export const evidenceSchema = z.object({
  id: z.string(), provider: z.string(), variable: z.string(), value: z.union([z.number(), z.string()]).optional(), unit: z.string().optional(),
  observedAt: z.string().optional(), retrievedAt: z.string(), spatialScope: z.enum(['regional', 'area', 'farm']),
  sourceType: z.enum(['forecast', 'historical', 'estimated', 'reported', 'synthetic']), status: z.enum(['available', 'unavailable', 'stale', 'partial']), details: z.string(),
})
export const observationSchema = z.object({ id: z.string(), recordedAt: z.string(), note: z.string(), sourceType: z.enum(['synthetic', 'reported']) })
export const farmSchema = z.object({
  id: z.string(), displayName: z.string(), point: z.object({ lat: z.number().min(-90).max(90), lon: z.number().min(-180).max(180) }),
  areaHectares: z.number().positive(), currentCrop: z.string(), plantingDate: z.string(), irrigationAccess: z.enum(['none', 'limited', 'reliable', 'unknown']),
  riskLevel: riskSchema, riskReasons: z.array(z.string()).min(1), dataQuality: z.enum(['observed', 'estimated', 'unknown']), droughtRisk: riskSchema,
  soil: z.object({ texture: z.string(), ph: z.number().optional(), organicCarbon: z.number().optional(), evidenceId: z.string() }),
  rainfall: z.object({ amount: z.number().optional(), unit: z.literal('mm'), period: z.string(), evidenceId: z.string() }),
  candidates: z.array(candidateSchema), evidence: z.array(evidenceSchema), observations: z.array(observationSchema),
})
export const providerSchema = z.object({ id: z.string(), name: z.string(), status: z.enum(['available', 'unavailable', 'partial', 'stale']), detail: z.string() })
export const analysisSchema = z.object({
  id: z.string(), selection_id: z.string(), mode: z.enum(['mock', 'http']), status: z.enum(['completed', 'partial']), checkedAt: z.string(),
  farms: z.array(farmSchema).max(100), providers: z.array(providerSchema), evidence: z.array(evidenceSchema),
})
export const mapCommandSchema = z.discriminatedUnion('type', [
  z.object({ type: z.literal('filter_farms'), risk: riskSchema.optional(), crop: z.string().optional(), candidateCrop: z.string().optional() }).strict(),
  z.object({ type: z.literal('select_farm'), farmId: z.string() }).strict(),
  z.object({ type: z.literal('zoom_to_farms'), farmIds: z.array(z.string()).max(100) }).strict(),
  z.object({ type: z.literal('set_layer_visibility'), layerId: z.enum(['farms', 'selection', 'soil', 'rainfall', 'satellite', 'pests']), visible: z.boolean() }).strict(),
  z.object({ type: z.literal('clear_filters') }).strict(), z.object({ type: z.literal('fit_to_selection') }).strict(),
])
export const assistantResponseSchema = z.object({ text: z.string(), commands: z.array(mapCommandSchema) })
export const draftSchema = z.object({
  id: z.string(), farmId: z.string(), createdAt: z.string(), category: z.literal('Crop candidate review'), mode: z.literal('mock'),
  text: z.string(), evidence: z.array(evidenceSchema), missingData: z.array(z.string()),
  status: z.enum(['draft', 'pending_review', 'approved', 'rejected']),
  audit: z.array(z.object({ status: z.enum(['draft', 'pending_review', 'approved', 'rejected']), reviewer: z.string(), at: z.string() })),
})
