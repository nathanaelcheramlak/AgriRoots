import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import { LocalMonitoringService } from './service'
import type { MonitoringDocument, MonitoringService } from './service'
interface MonitoringState extends MonitoringDocument {
  loaded: boolean; loading: boolean; warning: string | null; notice: string | null
  load(): Promise<void>; refresh(): Promise<void>; notify(message: string | null): void
}
export function createMonitoringStore(service: MonitoringService = new LocalMonitoringService()) {
  return createStore<MonitoringState>((set, get) => ({
    version: 1, monitors: [], feedback: [], loaded: false, loading: false, warning: null, notice: null,
    load: async () => { if (get().loaded || get().loading) return; set({ loading: true }); await get().refresh() },
    refresh: async () => {
      try { const { document, warning } = await service.read(); set({ ...document, warning, loaded: true, loading: false }) }
      catch { set({ warning: 'The local workspace could not be loaded. Reload to try again.', loading: false }) }
    },
    notify: notice => set({ notice }),
  }))
}
export const monitoringService = new LocalMonitoringService()
export const monitoringStore = createMonitoringStore(monitoringService)
export const useMonitoring = () => useStore(monitoringStore)
