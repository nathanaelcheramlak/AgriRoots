import { useEffect, type ReactNode } from 'react'
import { useHome, homeStore } from '../../state/useHome'
import { useTerritory, territoryStore } from './store'
import '../../styles/territory.css'

export function TerritorySession({ live, active, children }: { live: boolean; active: boolean; children: ReactNode }) {
  const h = useHome()
  const context = live && h.session === 'ready' ? h.context : null
  const owner = live ? context ? `${context.office_id}:${context.user_id}` : null : 'synthetic-demo'
  // Home point merges preserve this server envelope; do not reset registry state on point merges.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { territoryStore.getState().session(owner, context, live) }, [owner, context?.territory_workspace, context?.registry_workspace?.available, live])
  useEffect(() => { if (context?.registry_workspace?.available && owner) void territoryStore.getState().refreshRegistry() }, [owner, context?.territory_workspace, context?.registry_workspace?.available])
  useEffect(() => { if (!active) territoryStore.getState().setMode('navigate') }, [active])
  useEffect(() => {
    if (!live) return
    let oldTerritory = territoryStore.getState().currentId
    const applyScope = (reset: boolean) => {
      const next = territoryStore.getState(), t = next.territories.find(t => t.id === next.currentId)
      const ids = t?.origin === 'backend' && t.status === 'assigned' ? t.authorizedPlotIds ?? [] : null
      if (reset || JSON.stringify(ids) !== JSON.stringify(homeStore.getState().territoryPlotIds)) homeStore.getState().setTerritoryScope(ids, reset)
    }
    applyScope(false)
    const stop = territoryStore.subscribe((next, previous) => {
      if (next.currentId !== oldTerritory) {
        oldTerritory = next.currentId
        applyScope(true)
      } else if (next.territories !== previous.territories) applyScope(false)
      if (next.selectedPlotId !== previous.selectedPlotId) {
        const plot = next.plots.find(p => p.id === next.selectedPlotId)
        if (plot?.origin === 'backend') {
          homeStore.getState().setLocalDraftSelected(false)
          if (!homeStore.getState().selectedIds.includes(plot.id)) homeStore.getState().selectFarm(plot.id)
        } else homeStore.getState().setLocalDraftSelected(!!next.selectedPlotId)
      }
    })
    const stopHome = homeStore.subscribe((next, previous) => {
      if (next.selection !== previous.selection && territoryStore.getState().backendReady) void territoryStore.getState().loadRegisteredPlots(next.selection?.bbox)
      if (!next.localDraftSelected && previous.localDraftSelected) territoryStore.setState({ selectedPlotId: null })
    })
    return () => { stop(); stopHome() }
  }, [live])
  return children
}
export function LocalFarmCompanionContext() {
  const s = useTerritory(), h = useHome(), p = s.plots.find(p => p.id === s.selectedPlotId)
  if (!p || p.origin === 'backend' || s.live && !h.localDraftSelected) return null
  const season = s.seasons.find(c => c.plotId === p.id)
  return <section className="territory-companion-context" aria-label="Selected local farm context"><span className="territory-status">Local draft · not authorized</span><h3>{p.name}</h3><p>{season?.crop ?? 'Unknown crop'} · {p.farmerIds.map(id => s.farmers.find(f => f.id === id)?.displayName ?? 'Session-only association unavailable').join(', ')}</p><p>Live investigation requires a registered, authorized farm.</p><button className="plugin-secondary" onClick={() => s.selectPlot(p.id)}>View farm details</button></section>
}
