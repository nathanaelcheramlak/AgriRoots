import { useStore } from 'zustand'
import { homeApi, homeStore } from '../../state/useHome'
import { ManagedPluginApi } from './managed-api'
import { createManagedStore } from './managed-store'

export const managedApi = new ManagedPluginApi(homeApi)
export const managedStore = createManagedStore(managedApi)
const sync = () => {
  const h = homeStore.getState(), c = h.session === 'ready' ? h.context : null
  const identity = c ? { user: c.user_id, office: c.office_id, role: c.role } : null
  const old = managedStore.getState().identity
  if (identity?.user !== old?.user || identity?.office !== old?.office || identity?.role !== old?.role) managedStore.getState().reset(identity)
}
homeStore.subscribe(sync)
sync()
export const useManagedPlugins = () => useStore(managedStore)
