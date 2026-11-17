import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import type { AreaAnalysis, Farm } from '../../api/types'
import type { MonitorDefinition, MonitorRun, PhotoSubmission } from '../monitoring/types'
import type { AdvisorySource, CampaignInput, EvidenceReference } from './types'
export interface OutreachTransfer { id: string; input: CampaignInput; origin: string; unmappedFarmIds: string[] }
export const outreachTransferStore = createStore<{ pending: OutreachTransfer | null }>(() => ({ pending: null }))
export const useOutreachTransfer = () => useStore(outreachTransferStore)
export async function openOutreachFromSource(source: AdvisorySource, template: CampaignInput['templateId'], syntheticFarmMapping: boolean, origin: string) {
  const [{ newCampaignInput, generateGuidance }, { mapFarmRecipients }, { sourceSchema }] = await Promise.all([import('./catalog'), import('./recipients'), import('./types')])
  const safeSource = sourceSchema.parse({ ...source, recipientContext: syntheticFarmMapping ? 'synthetic' : 'unresolved' }), input = newCampaignInput(template), mapping = mapFarmRecipients(safeSource.farmIds, syntheticFarmMapping)
  input.source = safeSource; input.name = safeSource.title.slice(0, 120); input.guidance = generateGuidance(template, safeSource)
  input.selection = { ...input.selection, mode: 'map', ids: mapping.ids, scopeFarmIds: safeSource.farmIds, label: origin + ' · imported farm snapshot' }
  outreachTransferStore.setState({ pending: { id: crypto.randomUUID(), input, origin, unmappedFarmIds: mapping.unmapped } })
  window.location.hash = 'outreach/new'
}
export async function prepareHomeOutreach(farms: Farm[], analysis: AreaAnalysis, synthetic: boolean) {
  const records = [...new Map([...farms.flatMap(f => f.evidence), ...analysis.evidence].map(e => [e.id, e])).values()].slice(0, 100)
  const evidence: EvidenceReference[] = records.map(e => ({ id: e.id, title: e.variable.slice(0, 180), source: e.provider.slice(0, 160), observedAt: (e.observedAt ?? '').slice(0, 40), capturedAt: new Date().toISOString(), availability: e.status === 'available' ? 'available' : e.status === 'unavailable' ? 'unavailable' : 'partial', summary: (String(e.value ?? 'Unavailable') + ' ' + (e.unit ?? '')).slice(0, 600), limitations: e.details.slice(0, 600), mode: synthetic ? 'synthetic' : 'local_context', farmIds: farms.filter(f => f.evidence.some(v => v.id === e.id)).map(f => f.id) }))
  await openOutreachFromSource({ id: 'HOME-' + analysis.id, kind: 'home', mode: synthetic ? 'synthetic' : 'local_context', title: 'Guidance from Home · ' + farms.length + ' farm' + (farms.length === 1 ? '' : 's'), contextId: analysis.id, farmIds: farms.map(f => f.id), evidence, limitations: ['Home source snapshot; review source coverage and dates before preparing guidance.', synthetic ? 'Synthetic agricultural fixtures; not current conditions.' : 'No authorized farmer/contact mapping is connected in this prototype.'], originalObservation: '', officerAssessment: '' }, 'weekly', synthetic, 'Home')
}
export async function prepareMonitoringOutreach(monitor: MonitorDefinition, run: MonitorRun, template: CampaignInput['templateId'] = 'weather') {
  const affected = run.alerts.filter(a => a.state !== 'resolved').map(a => a.farmId), farmIds = affected.length ? run.farmIds.filter(id => affected.includes(id)) : run.farmIds
  const evidence: EvidenceReference[] = run.evidence.filter(e => farmIds.includes(e.farmId)).slice(0, 100).map(e => ({ id: e.id, title: e.farmId + ' · ' + e.metric.replaceAll('_', ' '), source: e.source, observedAt: e.observedAt, capturedAt: run.completedAt, availability: e.status, summary: (e.value === undefined ? 'Unavailable' : e.value + e.unit) + ' · reference: ' + e.reference, limitations: e.limitations, mode: 'synthetic', farmIds: [e.farmId] }))
  await openOutreachFromSource({ id: run.id, kind: 'monitoring', mode: 'synthetic', title: monitor.input.name + ' · outreach', contextId: monitor.id, version: monitor.version, farmIds, evidence, limitations: [run.limitations, ...run.dataGaps].slice(0, 20), originalObservation: '', officerAssessment: '' }, template, monitor.input.scope.farms.every(f => f.source === 'synthetic'), 'Monitoring')
}
export async function preparePhotoOutreach(monitor: MonitorDefinition, photo: PhotoSubmission, officerNotes: string) {
  if (!officerNotes.trim()) throw new Error('Add officer notes before preparing feedback.')
  const synthetic = photo.kind === 'illustration', original = photo.observations.map(o => o.text).join(' ') || 'No diagnostic observation supplied. Image has not been analyzed.'
  await openOutreachFromSource({ id: photo.id, kind: 'crop_case', mode: synthetic ? 'synthetic' : 'local_context', title: 'Crop follow-up · ' + photo.farmId, contextId: monitor.id, version: monitor.version, farmIds: [photo.farmId], originalObservation: original.slice(0, 1200), officerAssessment: officerNotes.slice(0, 1200), evidence: [{ id: photo.id, title: photo.farmId + ' · crop observation reference', source: synthetic ? 'AgriLo crop illustration' : 'Explicitly selected session sample', observedAt: photo.submittedAt, capturedAt: new Date().toISOString(), availability: 'partial', summary: original.slice(0, 600), limitations: photo.limitations, mode: synthetic ? 'synthetic' : 'local_context' }], limitations: [photo.limitations, 'No image bytes are transferred or retained. A session image is unavailable after leaving its photo view.', 'Officer notes are a local assessment, not an authenticated diagnosis.'] }, 'health', monitor.input.scope.farms.find(f => f.id === photo.farmId)?.source === 'synthetic', 'Crop photo review')
}
