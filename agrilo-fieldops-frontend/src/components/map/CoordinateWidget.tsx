import { useEffect, useState } from 'react'
import { Crosshair, Copy, Expand, MapPin } from 'lucide-react'
import type { MapBinding } from './map-binding'
import { useFieldOps } from '../../state/useFieldOps'
import { areaKm2, demoSelection, rectangleSelection } from '../../lib/geo'
import { errorMessage } from '../../lib/format'
import styles from '../../app/App.module.css'
export type Coordinate = { lat: number; lng: number }
export function CoordinateWidget({ coordinate, onCoordinate, binding }: { coordinate: Coordinate | null; onCoordinate: (point: Coordinate) => void; binding?: MapBinding }) {
  const s = (binding ?? { useState: useFieldOps }).useState(), [lat, setLat] = useState(''), [lng, setLng] = useState(''), [width, setWidth] = useState('10')
  useEffect(() => { if (coordinate) { setLat(String(coordinate.lat)); setLng(String(coordinate.lng)) } }, [coordinate])
  const selection = s.selection
  const analyze = (event: React.FormEvent) => {
    event.preventDefault()
    try {
      const point = { lat: Number(lat), lng: Number(lng) }, km = Number(width)
      if (!lat.trim() || !lng.trim() || !Number.isFinite(point.lat) || !Number.isFinite(point.lng) || !Number.isFinite(km) || km < .1 || km > 40) throw new Error('Enter valid coordinates and an area width between 0.1 and 40 km.')
      const latOffset = km / (2 * 111.32), lonOffset = latOffset / Math.cos(point.lat * Math.PI / 180)
      const next = rectangleSelection({ lat: point.lat - latOffset, lng: point.lng - lonOffset }, { lat: point.lat + latOffset, lng: point.lng + lonOffset }, 'manual_area')
      onCoordinate(point); s.setSelection(next, 0); s.focusMap('selection')
    } catch (error) { s.notify(errorMessage(error)) }
  }
  return <>
    <div className={`${styles.coordinateWidget} coordinate-widget`}>
      <div className={styles.coordinateData}><strong>{selection ? 'Area selected' : coordinate ? 'Target selected' : 'Awaiting an area'}</strong><p>{selection ? `${areaKm2(selection.bbox).toFixed(1)} km² · ${binding ? s.farms.length : s.analysis ? s.farms.length : '…'} ${binding ? 'authorized farm points' : 'registered demo farms'}` : coordinate ? `${coordinate.lat.toFixed(5)}, ${coordinate.lng.toFixed(5)}` : 'Draw on the map or enter coordinates'}</p></div>
      {selection && <div className="selection-card"><div><span>N {selection.bbox[3].toFixed(4)}° · S {selection.bbox[1].toFixed(4)}°</span><span>W {selection.bbox[0].toFixed(4)}° · E {selection.bbox[2].toFixed(4)}°</span></div><button aria-label="Copy selection GeoJSON" title="Copy GeoJSON" onClick={() => { void navigator.clipboard.writeText(JSON.stringify({ type: 'Feature', bbox: selection.bbox, geometry: selection.geometry, properties: { selection_id: selection.selection_id } }, null, 2)).then(() => s.notify('Selection GeoJSON copied.')).catch(() => s.notify('Clipboard unavailable. Copy the payload from Overview → Selection details.')) }}><Copy size={15} /></button><button aria-label="Fit to selection" title="Fit to selection" onClick={() => s.focusMap('selection')}><Expand size={15} /></button></div>}
      <form className={styles.coordForm} onSubmit={analyze}>
        <div className={styles.coordInputsWrapper}><div className={styles.inputGroup}><label htmlFor="area-lat">LAT</label><input id="area-lat" type="number" step="any" min="-89" max="89" required value={lat} onChange={e => setLat(e.target.value)} placeholder="8.546" className={styles.coordInput} /></div><div className={styles.inputDivider} /><div className={styles.inputGroup}><label htmlFor="area-lng">LNG</label><input id="area-lng" type="number" step="any" min="-180" max="180" required value={lng} onChange={e => setLng(e.target.value)} placeholder="39.273" className={styles.coordInput} /></div></div>
        <div className="area-width-row"><label htmlFor="area-width"><Crosshair size={13} />Area width</label><input id="area-width" aria-label="Area width in kilometres" type="number" min="0.1" max="40" step="0.1" required value={width} onChange={e => setWidth(e.target.value)} /><span>km</span></div>
        <button type="submit" className={styles.coordSubmitBtn}>{binding ? 'Filter map area' : 'Analyze area'}</button>
      </form>
    </div>
    {!binding && <button className="demo-area-button" onClick={() => { s.setSelection(demoSelection(), 0); s.focusMap('selection') }}><MapPin size={16} />Try demo area <span>12 farms near Adama</span></button>}
  </>
}
