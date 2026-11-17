import { useHome } from '../state/useHome'
import LegacyHomeWorkspace from './LegacyHomeWorkspace'
import MapFirstHome from './MapFirstHome'

export default function LiveHomeWorkspace({ active, onExploreDemo }: { active: boolean; onExploreDemo?: () => void }) {
  const s = useHome()
  return s.session === 'ready' && s.context?.registry_workspace?.available
    ? <MapFirstHome key={s.conversationId} active={active} />
    : <LegacyHomeWorkspace active={active} onExploreDemo={onExploreDemo} />
}
