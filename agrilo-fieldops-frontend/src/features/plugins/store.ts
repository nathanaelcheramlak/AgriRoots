import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import { LocalPluginService } from './service'
import type { PluginService } from './service'
import type { CatalogItem, CustomInput, PluginDraft, PluginEntry } from './types'

interface PluginState {
  catalog: CatalogItem[]; drafts: PluginDraft[]; loading: boolean; loaded: boolean; warning: string | null; notice: string | null
  load(): Promise<void>; addCatalog(id: string): Promise<PluginDraft>; saveCustom(input: CustomInput, existingId?: string): Promise<PluginDraft>; removeDraft(id: string): Promise<void>; dismissNotice(): void
}
export function entriesFor(catalog: CatalogItem[], drafts: PluginDraft[]): PluginEntry[] {
  return [...catalog.map(c => ({ ...c, catalog: c, draft: drafts.find(d => d.type === 'catalog' && d.catalogId === c.id) })), ...drafts.filter((d): d is Extract<PluginDraft, { type: 'custom' }> => d.type === 'custom').map(d => ({ id: d.id, name: d.configuration.name, description: d.configuration.description || (d.configuration.kind === 'mcp' ? 'Your custom MCP server configuration.' : 'Your custom REST API configuration.'), category: 'custom' as const, source: 'custom' as const, availability: 'setup_required' as const, requirement: 'Saved on this device. A connected backend is required for authentication, testing and approval.', draft: d }))]
}
export function createPluginStore(service: PluginService = new LocalPluginService()) {
  return createStore<PluginState>((set, get) => ({
    catalog: [], drafts: [], loading: false, loaded: false, warning: null, notice: null,
    load: async () => {
      if (get().loaded || get().loading) return
      set({ loading: true })
      try { const [catalog, { drafts, warning }] = await Promise.all([service.listCatalog(), service.listDrafts()]); set({ catalog, drafts, warning, loaded: true, loading: false }) }
      catch { set({ loading: false, warning: 'The local plugin catalog could not be loaded. Reload the page to try again.' }) }
    },
    addCatalog: async id => { const draft = await service.addCatalog(id); set({ drafts: [...get().drafts.filter(d => d.id !== draft.id), draft], warning: null, notice: 'Draft saved locally. No service was connected.' }); return draft },
    saveCustom: async (input, existingId) => { const draft = await service.saveCustom(input, existingId); set({ drafts: [...get().drafts.filter(d => d.id !== draft.id), draft], warning: null, notice: 'Configuration saved locally. Connection and approval have not been requested.' }); return draft },
    removeDraft: async id => { await service.removeDraft(id); set({ drafts: get().drafts.filter(d => d.id !== id), notice: 'Local draft removed.' }) },
    dismissNotice: () => set({ notice: null }),
  }))
}
export const pluginStore = createPluginStore()
export const usePlugins = () => useStore(pluginStore)
