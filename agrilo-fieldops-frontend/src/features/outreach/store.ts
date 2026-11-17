import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import { LocalOutreachService } from './service'
import type { OutreachService } from './service'
import type { OutreachCampaign, OutreachFollowUp } from './types'
interface OutreachState { campaigns: OutreachCampaign[]; followUps: OutreachFollowUp[]; loaded: boolean; loading: boolean; warning: string | null; notice: string | null; load(): Promise<void>; refresh(): Promise<void>; notify(message: string | null): void }
export function createOutreachStore(service: OutreachService = new LocalOutreachService()) {
  return createStore<OutreachState>((set, get) => ({
    campaigns: [], followUps: [], loaded: false, loading: false, warning: null, notice: null,
    load: async () => { if (get().loaded || get().loading) return; set({ loading: true }); await get().refresh() },
    refresh: async () => { try { const data = await service.read(); set({ ...data, loaded: true, loading: false }) } catch { set({ loading: false, warning: 'The local workspace could not be read. Reload to try again.' }) } },
    notify: notice => set({ notice }),
  }))
}
export const outreachService = new LocalOutreachService()
export const outreachStore = createOutreachStore(outreachService)
export const useOutreach = () => useStore(outreachStore)
