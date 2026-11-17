import { createStore } from 'zustand/vanilla'
import type { SkillsApi, Skill } from './service'
import type { ManagedIdentity } from '../plugins/managed-store'

interface SkillsState {
  identity: ManagedIdentity | null; items: Skill[]; busy: boolean; loaded: boolean; error: string | null; notice: string | null;
  reset(identity: ManagedIdentity | null): void; refresh(): Promise<void>; action(work: (signal: AbortSignal) => Promise<void>): Promise<boolean>;
}
export function createSkillsStore(api: SkillsApi) {
  let generation = 0, controller = new AbortController()
  return createStore<SkillsState>((set, get) => ({
    identity: null, items: [], busy: false, loaded: false, error: null, notice: null,
    reset(identity) { generation++; controller.abort(); controller = new AbortController(); set({ identity, items: [], busy: false, loaded: false, error: null, notice: null }) },
    async refresh() {
      if (!get().identity || get().busy) return
      const token = generation; set({ busy: true, error: null })
      try { const items = await api.list(controller.signal); if (token === generation) set({ items, loaded: true }) }
      catch (e) { if (token === generation) set({ error: e instanceof Error ? e.message : 'The skill registry could not be loaded. No mock result was substituted.' }) }
      finally { if (token === generation) set({ busy: false }) }
    },
    async action(work) {
      if (!get().identity || get().busy) return false
      const token = generation, signal = controller.signal; set({ busy: true, error: null, notice: null })
      try { await work(signal); if (token !== generation) return false; const items = await api.list(signal); if (token !== generation) return false; set({ items, loaded: true, notice: 'Backend action confirmed. Validation, approval and activation are separate steps.' }); return true }
      catch (e) { if (token === generation) { set({ error: (e instanceof Error ? e.message : 'Backend operation failed.') + ' Refresh before retrying an uncertain write.' }); try { const items = await api.list(signal); if (token === generation) set({ items, loaded: true }) } catch { /* Retain last confirmed snapshot and error. */ } } return false }
      finally { if (token === generation) set({ busy: false }) }
    },
  }))
}
