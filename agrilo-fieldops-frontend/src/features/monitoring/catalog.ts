import type { MonitoringCapability, MonitorInput, MonitoringRule, MetricId } from './types'
import { metricSpecs } from './types'
import { syntheticFarms } from '../../demo/synthetic-farms'
import type { Farm } from '../../api/types'
export const capabilities: MonitoringCapability[] = [
  { id: 'weather', name: 'Weather forecast', description: 'Forecast context and temperature thresholds.', source: 'example', connection: 'not_connected' },
  { id: 'rainfall', name: 'Rainfall history', description: 'Compare rainfall with a configured baseline.', source: 'example', connection: 'not_connected' },
  { id: 'soil', name: 'Soil context', description: 'Soil properties with coverage and uncertainty.', source: 'example', connection: 'not_connected' },
  { id: 'satellite', name: 'Satellite vegetation', description: 'Compatible observations and vegetation changes.', source: 'example', connection: 'not_connected' },
  { id: 'crop_health', name: 'Crop photos & health', description: 'Submission records and reviewed diagnostic outputs.', source: 'example', connection: 'not_connected' },
  { id: 'pests', name: 'Pest surveillance', description: 'Reported symptoms and regional pest context.', source: 'example', connection: 'not_connected' },
  { id: 'crop_calendar', name: 'Crop calendar', description: 'Crop-stage and seasonal reference context.', source: 'example', connection: 'not_connected' },
  { id: 'markets', name: 'Market information', description: 'Agricultural market observations.', source: 'example', connection: 'not_connected' },
]
export const templates: { id: MonitorInput['templateId']; name: string; description: string; frequency: MonitorInput['schedule']['frequency']; category: MonitorInput['category']; capabilityIds: MonitorInput['capabilityIds']; outputs: MonitorInput['outputs']; metric?: MetricId }[] = [
  { id: 'weather', name: 'Daily Weather & Rainfall Watch', description: 'Monitor forecasts and rainfall conditions for selected farms and highlight potential risks.', frequency: 'daily', category: 'environment', capabilityIds: ['weather', 'rainfall'], outputs: ['summary', 'alert'], metric: 'rainfall_deficit' },
  { id: 'report', name: 'Weekly Farm Intelligence Report', description: 'Summarize agricultural conditions, emerging concerns, and changes across the farms you manage.', frequency: 'weekly', category: 'report', capabilityIds: ['weather', 'rainfall', 'soil', 'crop_calendar'], outputs: ['report', 'trends', 'priority_list'], metric: 'rainfall_deficit' },
  { id: 'photos', name: 'Weekly Crop Photo Monitoring', description: 'Track submitted crop photographs, identify possible concerns, and prepare follow-up feedback.', frequency: 'weekly', category: 'crop_health', capabilityIds: ['crop_health'], outputs: ['summary', 'farmer_feedback', 'inspection'], metric: 'missing_photos' },
  { id: 'satellite', name: 'Satellite Vegetation Watch', description: 'Monitor changes in available vegetation observations and flag unusual trends.', frequency: 'weekly', category: 'environment', capabilityIds: ['satellite'], outputs: ['trends', 'alert'], metric: 'vegetation_decline' },
  { id: 'custom', name: 'Custom Agricultural Monitor', description: 'Create your own monitoring task using selected farms, example capabilities, and thresholds.', frequency: 'weekly', category: 'environment', capabilityIds: [], outputs: ['summary'] },
]
export function farmReference(farm: Farm, source: 'synthetic' | 'home' = 'synthetic') { return { id: farm.id, name: source === 'synthetic' ? farm.displayName : 'Farm ' + farm.id, crop: farm.currentCrop, source } }
export const demoFarmReferences = syntheticFarms.slice(0, 7).map(f => farmReference(f))
export function newRule(metric: MetricId = 'rainfall_deficit'): MonitoringRule {
  return { id: crypto.randomUUID(), metric, operator: 'gte', threshold: { value: metric === 'missing_photos' ? 1 : metric === 'temperature' ? 32 : 20, unit: metricSpecs[metric].unit, reference: metric === 'missing_photos' ? 'weekly_demo' : metric === 'rainfall_deficit' ? 'seasonal_demo' : 'comparable_demo', referenceNote: '' }, scope: 'all', crop: '', farmIds: [], consecutiveChecks: 1, severity: 'warning', action: 'flag_report' }
}
export function newMonitorInput(templateId: MonitorInput['templateId'] = 'custom'): MonitorInput {
  const t = templates.find(t => t.id === templateId)!
  return { name: templateId === 'custom' ? '' : t.name, description: t.description, instructions: '', category: t.category, templateId,
    scope: { type: 'specific', label: 'Selected demonstration farms', farms: [] }, capabilityIds: [...t.capabilityIds],
    schedule: { frequency: t.frequency, time: '08:00', weekday: 1, monthDay: 1, timezone: 'Africa/Addis_Ababa', startDate: new Date().toLocaleDateString('en-CA', { timeZone: 'Africa/Addis_Ababa' }), endDate: '', reviewDate: '' },
    combination: 'all', rules: t.metric ? [newRule(t.metric)] : [], outputs: [...t.outputs] }
}
