import { useEffect, useRef } from 'react'
import L from 'leaflet'
import { useMap } from 'react-leaflet'
import { createPortal } from 'react-dom'
import { homeStore } from '../../state/useHome'
import { useTerritory, territoryStore } from '../../features/territory/store'
import { bounds, rectangle } from '../../features/territory/geometry'
import type { MapBinding } from './map-binding'

const territoryStyle = { color: '#8fc7a0', weight: 3, fillColor: '#8fc7a0', fillOpacity: .06, pmIgnore: true }
export function TerritoryMapLayer({ active, binding }: { active: boolean; binding: MapBinding }) {
  const map = useMap(), s = useTerritory(), group = useRef(L.layerGroup()), edit = useRef<L.Rectangle | null>(null), modeRef = useRef(s.mode), lastFit = useRef(-1), banner = useRef<HTMLDivElement>(null)
  modeRef.current = s.mode
  const territory = s.territories.find(t => t.id === s.currentId)
  useEffect(() => { const layers = group.current; layers.addTo(map); return () => { layers.remove() } }, [map])
  useEffect(() => {
    if (!active || !s.backendReady || territory?.origin !== 'backend' || territory.status !== 'assigned') return
    let timer: ReturnType<typeof setTimeout>
    const query = () => { clearTimeout(timer); timer = setTimeout(() => { const b = map.getBounds(); void territoryStore.getState().loadRegisteredPlots(homeStore.getState().selection?.bbox ?? [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()]) }, 300) }
    map.on('moveend', query)
    return () => { clearTimeout(timer); map.off('moveend', query) }
  }, [active, map, s.backendReady, territory?.id, territory?.status, territory?.origin])
  useEffect(() => {
    const layers = group.current; layers.clearLayers()
    if (territory) L.geoJSON(territory.boundary, { style: () => ({ ...territoryStyle, dashArray: territory.status === 'assigned' ? undefined : '10 4' }), interactive: false }).addTo(layers)
    for (const p of s.plots.filter(p => p.territoryId === s.currentId)) {
      const selected = p.id === s.selectedPlotId
      const layer = L.geoJSON(p.geometry, { style: () => ({ color: selected ? '#eacb82' : '#9eb9dd', weight: selected ? 3 : 1.5, fillOpacity: selected ? .2 : .1, dashArray: '5 3', pmIgnore: true }) }).addTo(layers)
      // DOM text keeps entered farm labels out of HTML interpolation.
      const label = document.createElement('span'); label.textContent = `${p.name} · local draft`
      layer.bindTooltip(label)
      layer.on('click', () => { if (modeRef.current === 'navigate' || modeRef.current === 'select-farm') territoryStore.getState().selectPlot(p.id) })
    }
    if (s.geometry) L.geoJSON(s.geometry, { style: () => ({ color: '#eacb82', weight: 2, dashArray: '3 6', fillOpacity: .12, pmIgnore: true }), interactive: false }).addTo(layers)
  }, [map, territory, s.currentId, s.plots, s.selectedPlotId, s.geometry])
  useEffect(() => {
    if (!active || !s.focus.geometry || lastFit.current === s.focus.serial) return
    lastFit.current = s.focus.serial
    const [w, south, e, n] = bounds(s.focus.geometry)
    map.fitBounds([[south, w], [n, e]], { padding: [20, 20], maxZoom: 17, animate: false })
  }, [map, s.focus, active])
  useEffect(() => {
    if (!active) { map.pm.disableDraw(); edit.current?.remove(); edit.current = null; return }
    if (s.mode === 'select-analysis-area') return
    map.pm.disableDraw(); edit.current?.remove(); edit.current = null
    if (s.mode === 'draw-territory' || s.mode === 'draw-farm-plot') map.pm.enableDraw('Rectangle', { snappable: false, pathOptions: { color: s.mode === 'draw-territory' ? '#8fc7a0' : '#eacb82', weight: 2, dashArray: '6 4', fillOpacity: .12 } })
    if ((s.mode === 'edit-territory' || s.mode === 'edit-farm-plot') && s.geometry) {
      const [w, south, e, n] = bounds(s.geometry)
      const layer = L.rectangle([[south, w], [n, e]], { color: '#eacb82', weight: 2, dashArray: '3 6' }).addTo(map)
      layer.pm.enable({ snappable: false, preventMarkerRemoval: true })
      edit.current = layer
    }
    return () => { edit.current?.pm.disable(); edit.current?.remove(); edit.current = null }
  }, [map, s.mode, s.geometry, active])
  useEffect(() => {
    const create = (event: L.LeafletEvent & { layer?: L.Layer }) => {
      const current = territoryStore.getState()
      if (!['draw-territory', 'draw-farm-plot'].includes(current.mode) || !(event.layer instanceof L.Rectangle)) return
      const b = event.layer.getBounds(); event.layer.remove()
      try { current.preview(rectangle(b.getWest(), b.getSouth(), b.getEast(), b.getNorth())) }
      catch { territoryStore.setState({ error: 'The rectangle is invalid. Draw a complete, nondegenerate boundary.', mode: 'navigate' }) }
    }
    const key = (event: KeyboardEvent) => {
      if (event.key !== 'Escape' || !active || ['navigate', 'select-analysis-area', 'select-farm'].includes(territoryStore.getState().mode)) return
      map.pm.disableDraw(); territoryStore.getState().setMode('navigate')
    }
    map.on('pm:create', create); window.addEventListener('keydown', key)
    return () => { map.off('pm:create', create); window.removeEventListener('keydown', key) }
  }, [map, active])
  useEffect(() => { if (banner.current) { L.DomEvent.disableClickPropagation(banner.current); L.DomEvent.disableScrollPropagation(banner.current) } }, [s.mode])
  if (s.mode === 'navigate' || s.mode === 'select-analysis-area' || s.mode === 'select-farm' || !active) return null
  const editing = s.mode.startsWith('edit-')
  return createPortal(<div className="territory-map-mode" ref={banner}><strong>{editing ? 'Edit the draft boundary' : s.mode === 'draw-territory' ? 'Draw territory proposal' : 'Draw farm plot draft'}</strong><span>{editing ? 'Drag a corner, then apply the boundary.' : 'Click two opposite corners. Escape cancels.'}</span>{editing && <button onClick={() => { const b = edit.current?.getBounds(); if (b) s.preview(rectangle(b.getWest(), b.getSouth(), b.getEast(), b.getNorth())) }}>Apply boundary</button>}<button onClick={() => { map.pm.disableDraw(); s.setMode('navigate'); binding.getState().notify('Drawing canceled. Saved boundaries are unchanged.') }}>Cancel</button></div>, map.getContainer())
}
