// Leaflet interaction and satellite presentation adapted from Leoul39/AgroSphere (MIT).
import { useContext, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import L from 'leaflet'
import { MapContainer, Marker, ScaleControl, TileLayer, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import '@geoman-io/leaflet-geoman-free'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'
import { Check, Layers, LocateFixed, Pencil, RotateCcw, SquareDashed, Trash2 } from 'lucide-react'
import { MapBindingContext, demoMapBinding } from './map-binding'
import type { MapBinding, MapFarm } from './map-binding'
import { leafletBounds, rectangleSelection } from '../../lib/geo'
import { errorMessage } from '../../lib/format'
import { basemaps } from './map-config'
import type { Basemap } from './map-config'
import { GeographicContext } from './GeographicContext'
import type { Coordinate } from './CoordinateWidget'
import mapStyles from '../../reference/agrosphere/MapExplorer.module.css'
import { territoryStore, useTerritory } from '../../features/territory/store'
import { TerritoryMapLayer } from './TerritoryMapLayer'

L.Icon.Default.mergeOptions({ iconUrl: markerIcon, iconRetinaUrl: markerIcon2x, shadowUrl: markerShadow })
const colors = { high: '#f87171', moderate: '#fbbf24', low: '#34d399', unknown: '#94a3b8' }
function farmIcon(farm: MapFarm, selected: boolean) {
  const safeId = farm.id.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]!)
  return L.divIcon({ className: `farm-marker ${selected ? 'is-selected' : ''}`, html: `<span class="farm-pin" style="--pin:${colors[farm.riskLevel]}">${farm.riskLevel === 'unknown' ? '?' : farm.riskLevel[0].toUpperCase()}</span><span class="farm-id">${safeId}</span>`, iconSize: [34, 35], iconAnchor: [17, 12] })
}
interface MapProps { binding?: MapBinding; active?: boolean; controlsTarget?: HTMLElement | null; coordinate?: Coordinate | null; onCoordinate?: (point: Coordinate) => void }
function MapController({ active = true, controlsTarget, coordinate, onCoordinate }: MapProps) {
  const binding = useContext(MapBindingContext)
  const map = useMap(), state = binding.useState(), rectangle = useRef<L.Rectangle | null>(null)
  const viewport = useRef({ center: map.getCenter(), zoom: map.getZoom() }), lastFocus = useRef(-1)
  const [drawing, setDrawing] = useState(false), [editing, setEditing] = useState(false)
  const { mode } = useTerritory()
  useEffect(() => { if (mode !== 'select-analysis-area') { rectangle.current?.pm?.disable(); setEditing(false); setDrawing(false) } }, [mode])
  useMapEvents({ moveend: () => { if (active) viewport.current = { center: map.getCenter(), zoom: map.getZoom() } }, click: event => { if (active && ['navigate', 'select-analysis-area'].includes(territoryStore.getState().mode) && !map.pm.globalDrawModeEnabled() && !rectangle.current?.pm?.enabled()) onCoordinate?.(event.latlng) } })
  useEffect(() => {
    if (!active) return
    map.invalidateSize(); map.setView(viewport.current.center, viewport.current.zoom, { animate: false })
    const observer = new ResizeObserver(() => { if (map.getContainer().clientWidth && map.getContainer().clientHeight) { const center = map.getCenter(), zoom = map.getZoom(); map.invalidateSize(); map.setView(center, zoom, { animate: false }) } }); observer.observe(map.getContainer())
    return () => observer.disconnect()
  }, [map, active, binding])
  useEffect(() => {
    if (active) return
    map.stop(); map.pm.disableDraw()
    const current = binding.getState()
    if (rectangle.current) { if (current.selection) rectangle.current.setBounds(leafletBounds(current.selection)); rectangle.current.pm?.disable() }
    setDrawing(false); setEditing(false)
    if (current.phase === 'selecting') current.setPhase(current.analysis?.status ?? (current.selection ? 'loading_farms' : 'idle'))
  }, [map, active, binding])
  useEffect(() => {
    if (coordinate) map.flyTo([coordinate.lat, coordinate.lng], Math.max(map.getZoom(), 14), { duration: .8, animate: !window.matchMedia('(prefers-reduced-motion: reduce)').matches })
  }, [map, coordinate])
  useEffect(() => {
    const onCreate = (event: L.LeafletEvent & { layer?: L.Layer }) => {
      if (!(event.layer instanceof L.Rectangle)) return
      if (!['navigate', 'select-analysis-area'].includes(territoryStore.getState().mode)) return
      const bounds = event.layer.getBounds(); map.removeLayer(event.layer)
      try { binding.getState().setSelection(rectangleSelection(bounds.getSouthWest(), bounds.getNorthEast()), 0) }
      catch (error) { binding.getState().notify(errorMessage(error)) }
      setDrawing(false)
      territoryStore.getState().setMode('navigate')
    }
    const onDrawEnd = () => { setDrawing(false); if (territoryStore.getState().mode === 'select-analysis-area') territoryStore.getState().setMode('navigate'); const s = binding.getState(); if (s.phase === 'selecting') s.setPhase(s.analysis?.status ?? 'idle') }
    const onKey = (event: KeyboardEvent) => { if (event.key === 'Escape' && map.getContainer().clientWidth) { map.pm.disableDraw(); onDrawEnd() } }
    map.on('pm:create', onCreate); map.on('pm:drawend', onDrawEnd); window.addEventListener('keydown', onKey)
    return () => { map.off('pm:create', onCreate); map.off('pm:drawend', onDrawEnd); window.removeEventListener('keydown', onKey); map.pm.disableDraw() }
  }, [map, binding])
  useEffect(() => {
    if (!state.selection) { rectangle.current?.remove(); rectangle.current = null; setEditing(false); return }
    const bounds = L.latLngBounds(leafletBounds(state.selection))
    if (!rectangle.current) {
      const layer = L.rectangle(bounds, { color: '#ba9fe3', weight: 2, dashArray: '6 4', fillColor: '#ba9fe3', fillOpacity: .1 }).addTo(map)
      const onEdit = () => {
        const current = binding.getState(), b = layer.getBounds()
        try { const next = rectangleSelection(b.getSouthWest(), b.getNorthEast(), 'map_rectangle_edited'); if (next.bbox.join(',') !== current.selection?.bbox.join(',')) current.setSelection(next, 350) }
        catch (error) { current.notify(errorMessage(error)); if (current.selection) layer.setBounds(leafletBounds(current.selection)) }
      }
      layer.on('pm:markerdragend', onEdit); layer.on('pm:update', onEdit); rectangle.current = layer
    } else if (!rectangle.current.getBounds().equals(bounds)) rectangle.current.setBounds(bounds)
    if (state.layers.selection) { if (!map.hasLayer(rectangle.current)) rectangle.current.addTo(map) }
    else { rectangle.current.pm?.disable(); rectangle.current.remove(); setEditing(false) }
  }, [map, state.selection, state.layers.selection, binding])
  useEffect(() => {
    if (!active || lastFocus.current === state.focus.serial) return
    lastFocus.current = state.focus.serial
    const focus = state.focus, current = binding.getState()
    if (focus.type === 'reset') map.setView([8.546, 39.273], 12, { animate: false })
    else if (focus.type === 'selection' && current.selection) map.fitBounds(leafletBounds(current.selection), { padding: [25, 25], animate: false })
    else if (focus.farmIds?.length) {
      const farms = current.farms.filter(f => focus.farmIds!.includes(f.id))
      if (farms.length === 1) map.setView([farms[0].point.lat, farms[0].point.lon], 15, { animate: false })
      else if (farms.length) map.fitBounds(L.latLngBounds(farms.map(f => [f.point.lat, f.point.lon])), { padding: [40, 40], maxZoom: 14, animate: false })
    }
  }, [map, state.focus, active, binding])
  const draw = () => {
    if (territoryStore.getState().dirty) { state.notify('Finish or discard the registration draft before selecting an analysis area.'); return }
    rectangle.current?.pm?.disable(); setEditing(false)
    if (drawing) { map.pm.disableDraw(); return }
    territoryStore.getState().setMode('select-analysis-area')
    map.pm.enableDraw('Rectangle', { snappable: false, pathOptions: { color: '#ba9fe3', weight: 2, fillOpacity: .12 } })
    state.setPhase('selecting'); setDrawing(true)
  }
  const edit = () => { if (!rectangle.current || territoryStore.getState().dirty) return; map.pm.disableDraw(); territoryStore.getState().setMode('select-analysis-area'); rectangle.current.pm.toggleEdit({ snappable: false, preventMarkerRemoval: true }); setEditing(rectangle.current.pm.enabled()); if (!rectangle.current.pm.enabled()) territoryStore.getState().setMode('navigate') }
  const farms = state.farms
  const controls = <><div className="map-tools" aria-label="Map tools"><button className={drawing ? 'active' : ''} onClick={draw} aria-label={drawing ? 'Cancel drawing' : 'Draw rectangle'} title="Draw rectangle"><SquareDashed size={16} /><span>{drawing ? 'Cancel' : 'Draw area'}</span></button><button disabled={!state.selection || !state.layers.selection} className={editing ? 'active' : ''} onClick={edit} aria-label={editing ? 'Finish editing selection' : 'Edit selection'} title="Edit selection">{editing ? <Check size={16} /> : <Pencil size={15} />}<span>{editing ? 'Done' : 'Edit'}</span></button><button disabled={!state.selection} onClick={() => { map.pm.disableDraw(); state.clearSelection() }} aria-label="Clear selection" title="Clear selection"><Trash2 size={15} /><span>Clear</span></button><button onClick={() => state.focusMap('reset')} aria-label="Reset view to Adama" title="Reset view to Adama"><RotateCcw size={15} /></button><button disabled={!farms.length} onClick={() => state.focusMap('farms', farms.map(f => f.id))} aria-label="Fit visible farms" title="Fit visible farms"><LocateFixed size={16} /></button></div>{(drawing || editing) && <p className="map-instruction">{drawing ? 'Click two opposite corners. Esc to cancel.' : 'Drag a corner to resize, then choose Done.'}</p>}</>
  return controlsTarget ? createPortal(controls, controlsTarget) : null
}
function MapLayers({ basemap, onBasemap, boundaries, onBoundaries }: { basemap: Basemap; onBasemap: (id: Basemap) => void; boundaries: boolean; onBoundaries: (value: boolean) => void }) {
  const binding = useContext(MapBindingContext)
  const map = useMap(), state = binding.useState(), [open, setOpen] = useState(false), ref = useRef<HTMLDivElement>(null)
  useEffect(() => { if (ref.current) { L.DomEvent.disableClickPropagation(ref.current); L.DomEvent.disableScrollPropagation(ref.current) } }, [map, binding])
  return <div className="map-layer-control" ref={ref}><button aria-label="Map layers" aria-expanded={open} title="Map layers" onClick={() => setOpen(!open)}><Layers size={17} /></button>{open && <section className="layers-panel"><h3>Basemap</h3>{(Object.keys(basemaps) as Basemap[]).map(id => <label key={id}><input type="radio" name="basemap" checked={basemap === id} onChange={() => onBasemap(id)} />{basemaps[id].label} basemap</label>)}<hr /><h3>Map layers</h3>{(['farms', 'selection'] as const).map(id => <label key={id}><input type="checkbox" checked={state.layers[id]} onChange={() => state.toggleLayer(id)} />{id === 'farms' ? 'Farm locations' : 'Selection boundary'}</label>)}<label><input type="checkbox" checked={boundaries} onChange={e => onBoundaries(e.target.checked)} />Regional boundaries</label><p>Rainfall, soil, NDVI and pest overlays: unavailable. Satellite imagery is a visual basemap only.</p></section>}</div>
}
function MapContents(props: MapProps) {
  const binding = useContext(MapBindingContext)
  const state = binding.useState(), [basemap, setBasemap] = useState<Basemap>('satellite'), [boundaries, setBoundaries] = useState(true)
  const [tileError, setTileError] = useState(false), [loaded, setLoaded] = useState(false)
  const farms = state.farms, config = basemaps[basemap]
  const changeBasemap = (id: Basemap) => { setBasemap(id); setTileError(false); setLoaded(false) }
  return <section className={`map-shell ${mapStyles.mapContainer}`} aria-label="Interactive farm map">
    <MapContainer center={[8.546, 39.273]} zoom={12} minZoom={3} maxZoom={20} zoomControl className="field-map" zoomAnimation={false}>
      <TileLayer key={basemap} url={config.url} attribution={config.attribution} maxZoom={config.maxZoom} keepBuffer={1} eventHandlers={{ loading: () => setLoaded(false), tileerror: () => setTileError(true), load: () => setLoaded(true) }} />
      <ScaleControl position="bottomleft" imperial={false} />
      <GeographicContext visible={boundaries} />
      {props.coordinate && <Marker position={[props.coordinate.lat, props.coordinate.lng]} alt="Selected coordinate" title="Selected coordinate" interactive={false} />}
      {state.layers.farms && farms.map(f => <Marker key={`${f.id}-${(state.selectedFarmId === f.id || !!state.highlightedIds?.includes(f.id))}`} position={[f.point.lat, f.point.lon]} icon={farmIcon(f, (state.selectedFarmId === f.id || !!state.highlightedIds?.includes(f.id)))} title={`${f.displayName} · ${f.riskLevel} priority`} alt={`${f.displayName} · ${f.riskLevel} priority`} eventHandlers={{ click: () => { const t = territoryStore.getState(); if (['navigate', 'select-farm'].includes(t.mode) && !t.dirty) state.selectFarm(f.id) } }}><Tooltip direction="top" offset={[0, -16]}>{f.displayName} · {f.currentCrop} · {f.riskLevel} priority</Tooltip></Marker>)}
      <MapController {...props} />
      <TerritoryMapLayer active={props.active ?? true} binding={binding} />
      <MapLayers basemap={basemap} onBasemap={changeBasemap} boundaries={boundaries} onBoundaries={setBoundaries} />
    </MapContainer>
    {!loaded && !tileError && <div className="tile-status">Loading {config.label.toLowerCase()} imagery…</div>}
    {tileError && <div className="tile-status error" role="status">Some map tiles could not load. Choose Street in layers to continue.</div>}
    <span className="sr-only" data-testid="map-count">{state.layers.farms ? farms.length : 0} farm markers shown</span>
  </section>
}

export default function FieldOpsMap(props: MapProps) {
  return <MapBindingContext.Provider value={props.binding ?? demoMapBinding}><MapContents {...props} /></MapBindingContext.Provider>
}
