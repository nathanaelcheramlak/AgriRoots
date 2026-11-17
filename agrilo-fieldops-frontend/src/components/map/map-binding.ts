import { createContext } from 'react'
import type { Farm } from '../../api/types'
import { fieldOpsStore, useFieldOps } from '../../state/useFieldOps'
import { visibleFarms, type FieldOpsState } from '../../state/store'

export type MapFarm = Pick<Farm, 'id' | 'displayName' | 'point' | 'currentCrop' | 'riskLevel'>
export type MapState = Pick<FieldOpsState, 'selection' | 'phase' | 'analysis' | 'layers' | 'selectedFarmId' | 'focus' | 'setSelection' | 'clearSelection' | 'setPhase' | 'focusMap' | 'notify' | 'toggleLayer' | 'selectFarm'> & { farms: MapFarm[]; highlightedIds?: string[] }
export type MapBinding = { useState: () => MapState; getState: () => MapState }
function useDemoMapState(): MapState { const s = useFieldOps(); return { ...s, farms: visibleFarms(s) } }
export const demoMapBinding: MapBinding = { useState: useDemoMapState, getState: fieldOpsStore.getState }
export const MapBindingContext = createContext<MapBinding>(demoMapBinding)
