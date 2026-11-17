// Future backend boundary. IDs remain separate even when the UI calls each resource a plugin.
export type ResourceId<K extends string> = string & { readonly resourceKind: K }
export type ConnectionId = ResourceId<'connection'>
export type ToolId = ResourceId<'tool'>
export type PackId = ResourceId<'plugin_pack'>
export type SkillId = ResourceId<'skill'>
export type JobId = ResourceId<'job'>
export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue }
export type SchemaDocument = { [key: string]: JsonValue }
export type BackendResult<T> = { ok: true; data: T } | { ok: false; error: { code: string; message: string; retryable?: boolean } }
export interface BackendIdentity { officeId: string; userId: string; role: string }
export interface IntegrationDefinition { name: string; adapterType: 'rest' | 'mcp' | 'builtin'; baseUrl: string; authentication: { type: 'none' | 'api_key_header' | 'bearer' | 'provider'; headerName?: string }; handlerId?: string }
export interface VersionTarget { connectionId: ConnectionId; connectionRevision: number; toolId: ToolId; version: number; digest: string }
export interface OperationDefinition { name: string; inputSchema: SchemaDocument; outputSchema: SchemaDocument; requestMapping: SchemaDocument; responseMapping: SchemaDocument; capabilities: string[] }
export interface DiagnosticRequest { target: VersionTarget; arguments: SchemaDocument; plotIds: string[]; requestKey: string; authorizeNetwork: boolean }
export interface BackendJob { id: JobId; status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'; result?: JsonValue }
export interface IntegrationView { id: ConnectionId; identity: BackendIdentity; revision: number; health: string; enabled: boolean }
export interface OperationView { id: ToolId; target: VersionTarget; definition: OperationDefinition; approved: boolean; enabled: boolean }
export interface PackView { id: PackId; digest: string; name: string; installed: boolean; enabled: boolean }
export interface SkillView { id: SkillId; name: string; version: number; digest: string; approved: boolean; enabled: boolean }
export interface BackendPluginOperations {
  listIntegrations(): Promise<BackendResult<IntegrationView[]>>
  createIntegration(definition: IntegrationDefinition): Promise<BackendResult<IntegrationView>>
  reviseIntegration(id: ConnectionId, expectedRevision: number, definition: IntegrationDefinition): Promise<BackendResult<IntegrationView>>
  discoverMcpTools(id: ConnectionId, revision: number, requestKey: string, authorizeNetwork: boolean): Promise<BackendResult<BackendJob>>
  listOperations(id: ConnectionId): Promise<BackendResult<OperationView[]>>
  saveOperation(id: ConnectionId, definition: OperationDefinition, expectedTarget?: VersionTarget): Promise<BackendResult<OperationView>>
  previewOperation(request: DiagnosticRequest): Promise<BackendResult<SchemaDocument>>
  testConnection(request: DiagnosticRequest): Promise<BackendResult<BackendJob>>
  getJob(id: JobId): Promise<BackendResult<BackendJob>>
  approveToolVersion(target: VersionTarget): Promise<BackendResult<OperationView>>
  setConnectionEnabled(id: ConnectionId, expectedRevision: number, enabled: boolean): Promise<BackendResult<IntegrationView>>
  setToolEnabled(target: VersionTarget, expectedRevision: number, enabled: boolean): Promise<BackendResult<OperationView>>
  listPacks(): Promise<BackendResult<PackView[]>>
  registerPack(manifest: SchemaDocument): Promise<BackendResult<PackView>>
  installPack(id: PackId, digest: string): Promise<BackendResult<PackView>>
  setPackEnabled(id: PackId, digest: string, enabled: boolean): Promise<BackendResult<PackView>>
  listSkills(): Promise<BackendResult<SkillView[]>>
}
export function unsupportedBackend(): BackendPluginOperations {
  const unavailable = async (): Promise<BackendResult<never>> => ({ ok: false, error: { code: 'BACKEND_REQUIRED', message: 'This action requires a connected AgriLo backend. No request was made.' } })
  return { listIntegrations: unavailable, createIntegration: unavailable, reviseIntegration: unavailable, discoverMcpTools: unavailable, listOperations: unavailable, saveOperation: unavailable, previewOperation: unavailable, testConnection: unavailable, getJob: unavailable, approveToolVersion: unavailable, setConnectionEnabled: unavailable, setToolEnabled: unavailable, listPacks: unavailable, registerPack: unavailable, installPack: unavailable, setPackEnabled: unavailable, listSkills: unavailable }
}
