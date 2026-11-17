import type { CampaignInput, CommunicationChannel, EvidenceReference } from './types'
export type BackendResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string } }
export interface AuthorizedRecipientView { id: string; farmerReference: string; farmIds: string[]; displayLabel: string; language: string; channels: { type: CommunicationChannel; contactReference: string; consentEvidenceId: string }[]; membershipEvidenceId: string }
export interface BackendSnapshot { id: string; digest: string; count: number; exclusions: number; officeId: string; membershipRevision: number }
export interface BackendCampaignView { id: string; version: number; digest: string; officeId: string; ownerId: string; snapshotId: string; status: 'draft' | 'awaiting_review' | 'approved_for_dispatch' | 'changes_requested' }
export interface ApprovedCommunicationConnection { id: string; revision: number; channel: CommunicationChannel; healthEvidenceId: string; approvalEvidenceId: string; enabled: boolean }
export type AuthoritativeEvidenceReference = Omit<EvidenceReference, 'mode'> & { mode: 'backend'; digest: string; validationEvidenceId: string }
export type BackendCampaignContent = Pick<CampaignInput, 'name' | 'description' | 'category' | 'templateId' | 'instructions' | 'communication'> & { messageText: string; subject: string; sourceReferences: { id: string; version: number; digest: string }[]; personalizationVariables: string[] }
export interface DispatchRequest { campaignId: string; versionDigest: string; recipientSnapshotDigest: string; approvedConnectionId: string; connectionRevision: number; backendApprovalId: string; idempotencyKey: string; explicitAuthorization: true }
// Proposed HTTP adapter boundary only. No endpoint URLs are assumed or called here.
export interface OutreachBackend {
  discoverRecipients(query: { search: string; filters: Record<string, string>; cursor?: string; limit: number }): Promise<BackendResult<{ records: AuthorizedRecipientView[]; nextCursor?: string; total: number }>>
  createRecipientSnapshot(query: { recipientIds: string[]; excludedIds: string[]; expectedMembershipRevision: number }): Promise<BackendResult<BackendSnapshot>>
  createCampaign(request: { content: BackendCampaignContent; authorizedSnapshotId: string }): Promise<BackendResult<BackendCampaignView>>
  generateGuidance(request: { campaignId: string; version: number; approvedSkillId: string; evidenceIds: string[] }): Promise<BackendResult<{ draftId: string; originalText: string; evidence: AuthoritativeEvidenceReference[]; limitations: string[] }>>
  approveVersion(request: { campaignId: string; versionDigest: string; snapshotDigest: string; channel: CommunicationChannel; groupIds: string[] }): Promise<BackendResult<{ approvalId: string }>>
  listCommunicationConnections(): Promise<BackendResult<ApprovedCommunicationConnection[]>>
  submitApprovedDelivery(request: DispatchRequest): Promise<BackendResult<{ batchId: string; status: 'queued' }>>
  retrieveDelivery(batchId: string): Promise<BackendResult<{ batchId: string; status: 'queued' | 'submitted' | 'delivered' | 'failed' | 'unknown' | 'cancelled'; confirmationEvidenceIds: string[] }>>
  listResponses(query: { campaignId?: string; cursor?: string }): Promise<BackendResult<{ responseIds: string[]; nextCursor?: string }>>
}
export function unsupportedOutreachBackend(): OutreachBackend {
  const unavailable = async (): Promise<BackendResult<never>> => ({ ok: false, error: { code: 'BACKEND_REQUIRED', message: 'An authenticated AgriLo backend, approved connections and exact dispatch approval are required. No request was made.' } })
  return { discoverRecipients: unavailable, createRecipientSnapshot: unavailable, createCampaign: unavailable, generateGuidance: unavailable, approveVersion: unavailable, listCommunicationConnections: unavailable, submitApprovedDelivery: unavailable, retrieveDelivery: unavailable, listResponses: unavailable }
}
