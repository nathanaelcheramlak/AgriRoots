import { useStore } from 'zustand'
import { useShallow } from 'zustand/react/shallow'
import { HomeApi } from '../api/home-api'
import { createHomeStore } from './home-store'
import type { MapBinding } from '../components/map/map-binding'

export const homeApi = new HomeApi(import.meta.env.VITE_API_BASE_URL || '/backend')
export const homeStore = createHomeStore(homeApi)
export const useHome = () => useStore(homeStore)
function useLiveMapState() {
  return useStore(homeStore, useShallow(s => ({ farms: s.farms, selection: s.selection, phase: s.phase, analysis: s.analysis,
    layers: s.layers, selectedFarmId: s.selectedFarmId, highlightedIds: s.highlightedIds, focus: s.focus,
    setSelection: s.setSelection, clearSelection: s.clearSelection, setPhase: s.setPhase, focusMap: s.focusMap,
    notify: s.notify, toggleLayer: s.toggleLayer, selectFarm: s.selectFarm })))
}
export const liveMapBinding: MapBinding = { useState: useLiveMapState, getState: homeStore.getState }
