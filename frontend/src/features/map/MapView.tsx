import { useEffect, useRef } from 'react'
import Map, { NavigationControl, Source, Layer } from 'react-map-gl/maplibre'
import type { MapRef } from 'react-map-gl/maplibre'
import type { RouteResult } from '../../api/types'
import type { LayerProps } from 'react-map-gl/maplibre'

const riskColors: Record<string, string> = { LOW: '#16a34a', MODERATE: '#ca8a04', HIGH: '#ea580c', SEVERE: '#dc2626', NO_TRAVEL: '#7f1d1d', UNKNOWN: '#64748b' }
const routeColors = ['#2563eb', '#7c3aed', '#0891b2']
const routeLayer: LayerProps = { id: 'routes', type: 'line', paint: { 'line-color': ['get', 'color'], 'line-width': ['case', ['get', 'selected'], 7, 3], 'line-opacity': ['case', ['get', 'selected'], 1, 0.62] } }
export function MapView({ routes, selectedId, onSelect, heatFeatures, hour, metric = 'risk' }: { routes: RouteResult[]; selectedId: string | null; onSelect: (id: string) => void; heatFeatures?: GeoJSON.Feature[]; hour?: number; metric?: string }) {
  const mapRef = useRef<MapRef | null>(null)
  useEffect(() => {
    if (!mapRef.current || routes.length === 0) return
    const coordinates = routes.flatMap((route) => route.geometry.coordinates)
    const lons = coordinates.map(([lon]) => lon)
    const lats = coordinates.map(([, lat]) => lat)
    mapRef.current.fitBounds([[Math.min(...lons), Math.min(...lats)], [Math.max(...lons), Math.max(...lats)]], { padding: 70, duration: 700, maxZoom: 9 })
  }, [routes])
  const features = routes.map((route, index) => ({ type: 'Feature' as const, geometry: route.geometry, properties: { id: route.id, selected: route.id === selectedId, color: routeColors[index % routeColors.length] } }))
  const points = routes.flatMap((route) => route.checkpoints.map((cp, index) => ({ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [cp.lon, cp.lat] }, properties: { color: riskColors[cp.risk.level] ?? riskColors.UNKNOWN, risk: cp.risk.level, routeId: route.id, index } })))
  return <Map ref={mapRef} initialViewState={{ longitude: -98, latitude: 38, zoom: 4 }} mapStyle={import.meta.env.VITE_MAP_STYLE_URL ?? 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json'} style={{ width: '100%', height: '100%' }} onClick={(event) => { const hit = event.features?.[0]?.properties?.id as string | undefined; if (hit) onSelect(hit) }} interactiveLayerIds={['routes']}>
    <NavigationControl position="top-right" />
    {heatFeatures && <Source id="heat-data" type="geojson" data={{ type: 'FeatureCollection', features: heatFeatures }}><Layer id="heat-layer" type="heatmap" paint={{ 'heatmap-weight': ['get', metric === 'risk' ? `h${hour ?? 0}` : `${metric}_h${hour ?? 0}`], 'heatmap-radius': 35, 'heatmap-opacity': 0.7 }} /></Source>}
    <Source id="route-data" type="geojson" data={{ type: 'FeatureCollection', features }}>{<Layer {...routeLayer} />}</Source>
    <Source id="checkpoint-data" type="geojson" data={{ type: 'FeatureCollection', features: points }}><Layer id="checkpoints" type="circle" paint={{ 'circle-color': ['get', 'color'], 'circle-radius': ['case', ['==', ['get', 'risk'], 'NO_TRAVEL'], 8, 6], 'circle-stroke-color': '#fff', 'circle-stroke-width': 2 }} /></Source>
  </Map>
}
