// Adapted from Leoul39/AgroSphere MapExplorer.tsx (MIT, copyright 2025 Leoul39).
import { useEffect, useState } from 'react'
import { CircleMarker, GeoJSON, Tooltip, useMap, useMapEvents } from 'react-leaflet'
import type { Feature, FeatureCollection } from 'geojson'
import type { Layer } from 'leaflet'
import africaBorders from './boundaries/africa.json'
import ethiopiaRegions from './boundaries/ethiopia-regions.json'
import ethiopiaCities from './boundaries/ethiopia-cities.json'

export function GeographicContext({ visible }: { visible: boolean }) {
  const map = useMap(), [zoom, setZoom] = useState(map.getZoom())
  useMapEvents({ zoomend: () => setZoom(map.getZoom()) })
  useEffect(() => {
    const updateZoomClass = () => {
      const z = map.getZoom(), container = map.getContainer()
      container.className = container.className.replace(/\bzoom-level-\d+\b/g, '')
      container.classList.add(`zoom-level-${z <= 3 ? 1 : z === 4 ? 2 : z === 5 ? 3 : z === 6 ? 4 : z <= 8 ? 5 : 6}`)
    }
    map.on('zoom', updateZoomClass); updateZoomClass()
    return () => { map.off('zoom', updateZoomClass) }
  }, [map])
  if (!visible || zoom > 9) return null
  const onEachCountry = (feature: Feature, layer: Layer) => {
    if (typeof feature.properties?.name === 'string') layer.bindTooltip(feature.properties.name, { permanent: true, direction: 'center', className: 'countryLabel' })
  }
  const onEachRegion = (feature: Feature, layer: Layer) => {
    const name = feature.properties?.shapeName
    const hidden = ['Addis Ababa', 'Dire Dawa', 'Harari Region', 'Benshangul-Gumaz', 'Benishangul Gumuz', 'Benishangul-Gumuz', 'Benshangul Gumuz']
    if (typeof name === 'string' && !hidden.includes(name)) layer.bindTooltip(name, { permanent: true, direction: 'center', className: 'regionLabel' })
  }
  return <>
    {zoom <= 5 && <GeoJSON data={africaBorders as FeatureCollection} onEachFeature={onEachCountry} style={{ color: 'rgba(255,255,255,.4)', weight: 1.5, fillOpacity: 0, dashArray: '5 5' }} interactive={false} />}
    <GeoJSON data={ethiopiaRegions as FeatureCollection} onEachFeature={onEachRegion} style={{ color: '#a8ffb2', weight: 1.5, fillOpacity: 0, opacity: .6, dashArray: '3 3' }} interactive={false} />
    {ethiopiaCities.map(city => <CircleMarker key={city.name} center={[city.lat, city.lng]} radius={4} pathOptions={{ color: '#fff', fillColor: '#10b981', fillOpacity: .8, className: 'city-marker' }} interactive={false}><Tooltip permanent direction="bottom" className="cityLabel" offset={[0, 5]}>{city.name}</Tooltip></CircleMarker>)}
  </>
}
