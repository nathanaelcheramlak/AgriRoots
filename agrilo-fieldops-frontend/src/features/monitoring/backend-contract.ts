import type { Evidence, MonitorInput, MonitorRun, MonitoringAlert, MonitoringReport, PhotoObservation, PhotoSubmission, ThresholdEvaluation } from './types'
export type BackendResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } }
// Future HTTP adapters implement this boundary only after actual endpoint contracts are supplied.
export interface AuthoritativeMonitorView {
  id: string; version: number; revision: number; input: BackendMonitorInput
  owner: { officeId: string; userId: string }
  scheduleState: 'disabled' | 'enabled' | 'suspended'
  validationEvidenceId: string
}
export interface ApprovedCapabilityView {
  id: string; kind: 'skill' | 'plugin_tool'; version: number; digest: string
  approvalEvidenceId: string; connectionEvidenceId: string; enabled: boolean
}
export interface CapabilityReference { id: string; kind: 'builtin' | 'skill' | 'plugin_tool'; version: number; digest: string }
export type BackendMonitorInput = Omit<MonitorInput, 'capabilityIds'> & { capabilityReferences: CapabilityReference[] }
export type BackendEvidence = Omit<Evidence, 'freshness'> & { freshness: 'current' | 'stale' | 'unavailable'; retrievedAt: string }
export type BackendAlert = Omit<MonitoringAlert, 'trigger'> & { trigger: 'scheduled_check' | 'event'; runId: string }
export type BackendRun = Omit<MonitorRun, 'mode' | 'status' | 'evidence' | 'alerts' | 'capabilityIds'> & { mode: 'backend'; status: 'completed' | 'partial' | 'failed' | 'cancelled'; evidence: BackendEvidence[]; alerts: BackendAlert[]; capabilityReferences: CapabilityReference[] }
export type BackendPhotoObservation = Omit<PhotoObservation, 'certainty' | 'status'> & { certainty: 'unconfirmed'; status: 'needs_review' | 'reviewed'; analysisEvidenceId: string }
export type BackendPhotoSubmission = Omit<PhotoSubmission, 'kind' | 'objectUrl' | 'observations' | 'quality'> & { kind: 'authorized_submission'; assetId: string; quality: 'unassessed' | 'usable' | 'unusable'; observations: BackendPhotoObservation[] }
export type BackendReport = Omit<MonitoringReport, 'mode'> & { mode: 'backend'; evidenceDigest: string }
export interface MonitoringBackend {
  createValidatedMonitor(input: BackendMonitorInput): Promise<BackendResult<AuthoritativeMonitorView>>
  setScheduleState(id: string, expectedVersion: number, state: 'activate' | 'suspend'): Promise<BackendResult<AuthoritativeMonitorView>>
  listApprovedCapabilities(): Promise<BackendResult<ApprovedCapabilityView[]>>
  requestRun(id: string, version: number): Promise<BackendResult<{ jobId: string }>>
  listRuns(id: string, cursor?: string): Promise<BackendResult<{ runs: BackendRun[]; nextCursor?: string }>>
  listAlerts(id: string): Promise<BackendResult<BackendAlert[]>>
  evaluateRunRules(runId: string, configurationVersion: number): Promise<BackendResult<ThresholdEvaluation[]>>
  listPhotoSubmissions(monitorId: string, farmId: string): Promise<BackendResult<BackendPhotoSubmission[]>>
  ingestPhoto(request: { monitorId: string; farmId: string; content: Blob; consentReference: string }): Promise<BackendResult<BackendPhotoSubmission>>
  analyzePhoto(id: string, approvedCapabilityId: string): Promise<BackendResult<BackendPhotoObservation[]>>
  generateReport(runId: string): Promise<BackendResult<BackendReport>>
  submitReview(request: { feedbackId: string; expectedVersion: number; action: 'approve' | 'reject' | 'request_inspection'; reviewerNote: string }): Promise<BackendResult<{ reviewId: string }>>
  handoffCommunication(request: { reviewId: string; approvedConnectorId: string; recipientIds: string[]; explicitAuthorization: true }): Promise<BackendResult<{ handoffId: string }>>
}
export function unavailableMonitoringBackend(): MonitoringBackend {
  const unavailable = async (): Promise<BackendResult<never>> => ({ ok: false, error: { code: 'BACKEND_REQUIRED', message: 'A real AgriLo backend and authorized workflow are required. No request was made.' } })
  return { createValidatedMonitor: unavailable, setScheduleState: unavailable, listApprovedCapabilities: unavailable, requestRun: unavailable, listRuns: unavailable, listAlerts: unavailable, evaluateRunRules: unavailable, listPhotoSubmissions: unavailable, ingestPhoto: unavailable, analyzePhoto: unavailable, generateReport: unavailable, submitReview: unavailable, handoffCommunication: unavailable }
}
