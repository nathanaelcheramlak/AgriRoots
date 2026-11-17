import { pluginCatalog } from './catalog'
import { customInputSchema, draftDocumentSchema, draftSchema } from './types'
import type { CatalogItem, CustomInput, PluginDraft } from './types'
import { unsupportedBackend } from './backend-contract'
import type { BackendPluginOperations } from './backend-contract'

export const PLUGIN_STORAGE_KEY = 'agrilo-fieldops:plugins:v1'
export interface PluginService {
  readonly capabilities: { storage: 'device' | 'backend'; discovery: boolean; testing: boolean; approval: boolean; enablement: boolean; skills: boolean }
  readonly backend: BackendPluginOperations
  listCatalog(): Promise<CatalogItem[]>
  listDrafts(): Promise<{ drafts: PluginDraft[]; warning: string | null }>
  addCatalog(catalogId: string): Promise<PluginDraft>
  saveCustom(input: CustomInput, existingId?: string): Promise<PluginDraft>
  removeDraft(id: string): Promise<void>
}
export class LocalPluginService implements PluginService {
  private pendingWrite: Promise<void> = Promise.resolve()
  readonly capabilities = { storage: 'device' as const, discovery: false as const, testing: false as const, approval: false as const, enablement: false as const, skills: false as const }
  readonly backend = unsupportedBackend()
  constructor(private readonly storage: () => Storage = () => window.localStorage) {}
  async listCatalog() { return pluginCatalog.map(item => ({ ...item })) }
  async listDrafts() {
    try {
      const raw = this.storage().getItem(PLUGIN_STORAGE_KEY)
      if (!raw) return { drafts: [], warning: null }
      const document = draftDocumentSchema.parse(JSON.parse(raw))
      const catalogIds = document.drafts.filter(d => d.type === 'catalog').map(d => d.catalogId)
      if (new Set(document.drafts.map(d => d.id)).size !== document.drafts.length || new Set(catalogIds).size !== catalogIds.length || document.drafts.some(d => d.type === 'catalog' && !pluginCatalog.some(c => c.id === d.catalogId))) throw new Error('Invalid draft references')
      return { drafts: document.drafts, warning: null }
    } catch { return { drafts: [], warning: 'Local plugin drafts could not be read. No connection, approval, or active status was restored. You can save a new draft or remove invalid saved data in your browser.' } }
  }
  private write(drafts: PluginDraft[]) {
    const document = draftDocumentSchema.parse({ version: 1, drafts })
    try { this.storage().setItem(PLUGIN_STORAGE_KEY, JSON.stringify(document)) }
    catch { throw new Error('Could not save on this device. Check browser storage permissions and try again. Your changes have not been saved.') }
  }
  private serialize<T>(operation: () => Promise<T>): Promise<T> {
    const next = this.pendingWrite.then(operation)
    this.pendingWrite = next.then(() => {}, () => {})
    return next
  }
  async addCatalog(catalogId: string) {
    return this.serialize(async () => {
    const item = pluginCatalog.find(c => c.id === catalogId)
    if (!item || item.availability === 'unavailable') throw new Error('Setup is unavailable for this catalog entry. Read its requirements in the details.')
    const { drafts } = await this.listDrafts(), existing = drafts.find(d => d.type === 'catalog' && d.catalogId === catalogId)
    if (existing) return existing
    const now = new Date().toISOString(), draft = draftSchema.parse({ id: crypto.randomUUID(), type: 'catalog', catalogId, owner: 'this_device', createdAt: now, updatedAt: now })
    this.write([...drafts, draft]); return draft
    })
  }
  async saveCustom(input: CustomInput, existingId?: string) {
    return this.serialize(async () => {
    const configuration = customInputSchema.parse(input), { drafts } = await this.listDrafts()
    const existing = drafts.find(d => d.id === existingId)
    if (existingId && (!existing || existing.type !== 'custom')) throw new Error('This local configuration no longer exists. Close the form and reopen it.')
    const now = new Date().toISOString(), draft = draftSchema.parse({ id: existing?.id ?? crypto.randomUUID(), type: 'custom', configuration, owner: 'this_device', createdAt: existing?.createdAt ?? now, updatedAt: now })
    this.write(existing ? drafts.map(d => d.id === draft.id ? draft : d) : [...drafts, draft]); return draft
    })
  }
  async removeDraft(id: string) { return this.serialize(async () => { const { drafts } = await this.listDrafts(); this.write(drafts.filter(d => d.id !== id)) }) }
}
