import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import { GeoJSON, MapContainer, ScaleControl, TileLayer, useMap } from 'react-leaflet'
import '@geoman-io/leaflet-geoman-free'
import 'leaflet/dist/leaflet.css'
import '@geoman-io/leaflet-geoman-free/dist/leaflet-geoman.css'
import type { MultiPolygon, Polygon } from 'geojson'
import { basemaps, type Basemap } from './map-config'
import { bounds, contained, rectangle, validateBoundary } from '../../features/territory/geometry'
import type { FarmPlot } from '../../features/territory/types'

type Boundary = Polygon | MultiPolygon
interface Props {
  kind: 'overview' | 'farm'; active: boolean; drawing: boolean; boundary: Boundary | null;
  preview: Polygon | null; plots?: FarmPlot[]; selectedId?: string | null;
  onDraw(geometry: Polygon): void; onCancel(): void; onError(message: string): void; onSelect?(id: string): void;
}
function Interactions({ kind, active, drawing, boundary, onDraw, onCancel, onError }: Props) {
  const map = useMap(), callbacks = useRef({ onDraw, onCancel, onError })
  callbacks.current = { onDraw, onCancel, onError }
  const boundaryRef = useRef(boundary); boundaryRef.current = boundary
  const boundaryKey = JSON.stringify(boundary)
  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize({ pan: false }))
    observer.observe(map.getContainer()); return () => observer.disconnect()
  }, [map])
  useEffect(() => { if (active) map.invalidateSize({ pan: false }); else map.pm.disableDraw() }, [active, map])
  useEffect(() => {
    const geometry = boundaryRef.current
    if (!geometry) return
    const [w, s, e, n] = bounds(geometry), box = L.latLngBounds([s, w], [n, e])
    map.setMinZoom(3); map.fitBounds(box, { padding: [16, 16], maxZoom: 18, animate: false })
    if (kind !== 'farm') return
    map.setMinZoom(map.getZoom()); map.setMaxBounds(box)
    // Mask imagery outside the selected polygon, including holes. This map is a
    // separate Leaflet instance; the overview's drawing handlers cannot reach it.
    if (!map.getPane('outside-crop')) { const pane = map.createPane('outside-crop'); pane.style.zIndex = '450'; pane.style.pointerEvents = 'none' }
    const polygons = geometry.type === 'Polygon' ? [geometry.coordinates] : geometry.coordinates
    const rings = polygons.flatMap(p => p.map(ring => ring.map(([lon, lat]) => [lat, lon] as L.LatLngTuple)))
    const mask = L.polygon([[[85, -180], [85, 180], [-85, 180], [-85, -180]], ...rings], {
      pane: 'outside-crop', fillColor: '#111111', fillOpacity: 1, color: '#111111', stroke: false, interactive: false, fillRule: 'evenodd',
    }).addTo(map)
    return () => { mask.remove(); map.setMaxBounds(L.latLngBounds([-85, -180], [85, 180])); map.setMinZoom(3) }
  }, [map, kind, boundaryKey])
  useEffect(() => {
    if (!drawing || !active) { map.pm.disableDraw(); return }
    const create = (event: L.LeafletEvent & { layer?: L.Layer }) => {
      if (!(event.layer instanceof L.Rectangle)) return
      const b = event.layer.getBounds(); event.layer.remove(); map.pm.disableDraw()
      try {
        const geometry = rectangle(b.getWest(), b.getSouth(), b.getEast(), b.getNorth())
        validateBoundary(geometry, kind === 'farm' ? 'plot' : 'territory')
        if (kind === 'farm' && (!boundaryRef.current || !contained(geometry, boundaryRef.current))) throw new Error('Keep the whole farm inside the cropped area. Please draw it again.')
        callbacks.current.onDraw(geometry)
      } catch (e) { callbacks.current.onError(e instanceof Error ? e.message : 'Please draw a valid rectangle.') }
      callbacks.current.onCancel()
    }
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') { map.pm.disableDraw(); callbacks.current.onCancel() } }
    map.on('pm:create', create); window.addEventListener('keydown', escape)
    map.pm.enableDraw('Rectangle', { snappable: false, pathOptions: { color: '#79b6ff', weight: 2, fillColor: '#79b6ff', fillOpacity: .16 } })
    return () => { map.off('pm:create', create); window.removeEventListener('keydown', escape); map.pm.disableDraw() }
  }, [map, kind, drawing, active])
  return null
}

export default function AreaCanvas(props: Props) {
  const [style, setStyle] = useState<Basemap>('satellite'), [tileError, setTileError] = useState(false)
  const config = basemaps[style]
  return <div className={'area-canvas area-canvas-' + props.kind}>
    <MapContainer center={[8.546, 39.273]} zoom={12} minZoom={3} maxZoom={20} zoomSnap={.25}
      maxBoundsViscosity={1} className="field-map" aria-label={props.kind === 'farm' ? 'Cropped farm drawing map' : 'Overview area selection map'}>
      <TileLayer key={style} url={config.url} attribution={config.attribution} maxZoom={config.maxZoom} noWrap
        eventHandlers={{ tileerror: () => setTileError(true) }} />
      <ScaleControl position="bottomleft" imperial={false} />
      {props.boundary && <GeoJSON key={JSON.stringify(props.boundary)} data={props.boundary} interactive={false} style={{ color: '#79b6ff', weight: 2, fillOpacity: 0, pmIgnore: true }} />}
      {props.kind === 'farm' && props.plots?.map(plot => <GeoJSON key={plot.id + JSON.stringify(plot.geometry)} data={plot.geometry}
        style={{ color: plot.id === props.selectedId ? '#e6cd8a' : '#a9d5b6', weight: plot.id === props.selectedId ? 3 : 2, fillOpacity: .2, pmIgnore: true }}
        onEachFeature={(_, layer) => { const label = document.createElement('span'); label.textContent = plot.name; layer.bindTooltip(label); layer.on('click', () => { if (!props.drawing) props.onSelect?.(plot.id) }) }} />)}
      {props.preview && <GeoJSON key={'draft-' + JSON.stringify(props.preview)} data={props.preview} interactive={false} style={{ color: '#79b6ff', weight: 2, fillOpacity: .2, pmIgnore: true }} />}
      <Interactions {...props} />
    </MapContainer>
    <label className="area-map-style"><span className="sr-only">{props.kind === 'farm' ? 'Cropped map style' : 'Overview map style'}</span><select value={style} onChange={e => { setStyle(e.target.value as Basemap); setTileError(false) }}><option value="satellite">Satellite</option><option value="street">Street</option></select></label>
    {props.drawing && <div className="area-draw-hint" role="status">{props.kind === 'farm' ? 'Draw the farm on this cropped map.' : 'Draw your area.'} Click two opposite corners. <button onClick={props.onCancel}>Cancel</button></div>}
    {tileError && <p className="area-tile-notice" role="status">Some map imagery could not load. You can switch to Street.</p>}
  </div>
}
