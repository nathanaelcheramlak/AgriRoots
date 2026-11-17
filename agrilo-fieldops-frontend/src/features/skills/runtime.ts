import { useStore } from 'zustand'
import { homeApi, homeStore } from '../../state/useHome'
import { SkillsApi } from './service'
import { createSkillsStore } from './store'

export const skillsApi = new SkillsApi(homeApi)
export const skillsStore = createSkillsStore(skillsApi)
const sync = () => {
  const h = homeStore.getState(), c = h.session === 'ready' ? h.context : null
  const identity = c ? { user: c.user_id, office: c.office_id, role: c.role } : null, old = skillsStore.getState().identity
  if (identity?.user !== old?.user || identity?.office !== old?.office || identity?.role !== old?.role) skillsStore.getState().reset(identity)
}
homeStore.subscribe(sync); sync()
export const useSkills = () => useStore(skillsStore)
