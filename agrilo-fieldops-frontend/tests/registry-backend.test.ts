import { afterEach, describe, expect, it, vi } from 'vitest'
import { homeApi } from '../src/state/useHome'
import { createTerritoryStore } from '../src/features/territory/store'
import { parseFarmer, parsePlot } from '../src/features/territory/backend'
import { context, plotId } from './home-fixtures'
import { rectangle } from '../src/features/territory/geometry'
import { HomeApi } from '../src/api/home-api'
import { createHomeStore } from '../src/state/home-store'
import { job, result, evidence } from './home-fixtures'

afterEach(() => vi.restoreAllMocks())
const territory = { id:'server-territory', name:'Assigned test territory', region:'', district:'', description:'', officeId:context.office_id,
  status:'assigned', origin:'backend', boundary:rectangle(38.6,8.8,38.7,8.9), createdAt:'2026-11-17T00:00:00Z', revision:2, authorizedPlotIds:[] }
function ready() {
  const store = createTerritoryStore()
  store.getState().session('registry-owner', { ...context, registry_workspace:{ available:true,version:1,spatial_engine:'postgis',plot_page_limit:100,territory_total:1 }, territory_workspace:{status:'available',territories:[territory]} }, true)
  return store
}
describe('authenticated registry adapter', () => {
  it('uses the existing memory-only login and refuses routes outside the registry', async () => {
    const transport = vi.fn().mockResolvedValue(new Response(JSON.stringify({items:[],total:0}),{status:200}))
    const api = new HomeApi('/backend', transport)
    await api.registryRequest('/api/v1/registry/farmers', new AbortController().signal)
    expect(transport.mock.calls[0][1].credentials).toBe('omit')
    await expect(api.registryRequest('/api/auth/login',new AbortController().signal)).rejects.toThrow('Unsupported')
  })
  it('submits farmer data to the existing office registry and persists no profile in localStorage', async () => {
    localStorage.clear()
    const store = ready(), request = vi.spyOn(homeApi, 'registryRequest').mockResolvedValue({id:'permanent-farmer',reference:'TEST-1',display_name:'Test Farmer',village:'',language:'en',channel:'none',consent:'unknown',synthetic:false,revision:1})
    store.getState().beginFarmer()
    store.getState().updateFarmer({reference:'TEST-1',displayName:'Test Farmer',phone:'+251911123456'})
    expect(await store.getState().registerFarmer()).toBe(true)
    expect(request.mock.calls[0][0]).toBe('/api/v1/registry/farmers')
    expect(JSON.parse(String(request.mock.calls[0][2]?.body)).territory_id).toBe(territory.id)
    expect(store.getState().farmers[0].origin).toBe('backend')
    expect(JSON.stringify(localStorage)).not.toContain('+251911123456')
    expect(JSON.stringify(localStorage)).not.toContain('Test Farmer')
  })
  it('ignores a paginated response arriving after logout', async () => {
    const store = ready()
    let resolve!: (data: unknown) => void
    vi.spyOn(homeApi, 'registryRequest').mockImplementation(() => new Promise(r => { resolve = r }))
    const loading = store.getState().loadFarmers()
    store.getState().session(null,null,true)
    resolve({items:[],total:2000,limit:25,offset:0})
    await loading
    expect(store.getState().farmerTotal).toBe(0)
    expect(store.getState().farmers).toHaveLength(0)
  })
  it('keeps permanent registration separate from local IDs and restricted private profiles', () => {
    const farmer = parseFarmer({id:'f-1',reference:'DEMO-1',display_name:'Test Farmer',village:'',language:'en',channel:'none',consent:'unknown',synthetic:true,revision:1,private:{phone:'not-in-directory'}})
    expect(farmer.phone).toBe('')
    const parsed = parsePlot({id:plotId,territoryId:territory.id,name:'Test plot',geometry:rectangle(38.61,8.81,38.611,8.811),farmerIds:['f-1'],status:'registered',origin:'backend',createdAt:'2026-11-17T00:00:00Z',revision:1,home_plot:context.plots[0],season:null})
    expect(parsed.plot.origin).toBe('backend')
    expect(parsed.plot.id.startsWith('local-')).toBe(false)
  })
  it('opens saved evidence through existing job polling without starting a new model/provider run', async () => {
    const api = { clearSession:vi.fn(), login:vi.fn().mockResolvedValue('fixture'),context:vi.fn().mockResolvedValue(context),
      job:vi.fn().mockResolvedValue({...job,status:'succeeded',result}),evidence:vi.fn().mockResolvedValue(evidence),start:vi.fn() }
    const store = createHomeStore(api as unknown as HomeApi,1)
    await store.getState().login('fixture','fixture')
    await store.getState().openSavedJob(job.id,plotId)
    expect(store.getState().investigations[0].evidence).toHaveLength(1)
    expect(api.start).not.toHaveBeenCalled()
    expect(store.getState().activeId).toBeNull()
  })
})
