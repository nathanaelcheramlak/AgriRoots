import { useStore } from 'zustand'
import { QueryClient } from '@tanstack/react-query'
import { createFieldOpsStore } from './store'
import { MockFieldOpsApi } from '../api/mock-fieldops-api'
import { HttpFieldOpsApi } from '../api/http-fieldops-api'
export const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
const scenario = import.meta.env.VITE_DEMO_SCENARIO
const api = import.meta.env.VITE_API_MODE === 'http' ? new HttpFieldOpsApi(import.meta.env.VITE_API_BASE_URL ?? '') : new MockFieldOpsApi(scenario === 'error' || scenario === 'partial' ? scenario : 'success')
export const fieldOpsStore = createFieldOpsStore(api, queryClient)
export const useFieldOps = () => useStore(fieldOpsStore)
