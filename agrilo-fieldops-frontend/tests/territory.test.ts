import { beforeEach, describe, expect, it, vi } from 'vitest'
import { rectangle, measuredArea, contained, sharedArea, boundarySchema } from '../src/features/territory/geometry'
import { createTerritoryStore } from '../src/features/territory/store'
import { demoTerritory } from '../src/features/territory/fixtures'
import { farmPlotService, farmInvestigationService, restoreLocalWorkspace, storageKey, territoryService } from '../src/features/territory/services'
import { context, plotId } from './home-fixtures'
import { createHomeStore, investigationBlock } from '../src/state/home-store'
import type { HomeApi } from '../src/api/home-api'
import { prepareMonitoringContext, prepareOutreachContext } from '../src/features/territory/handoffs'

const boundary = () => rectangle(39.2, 8.5, 39.3, 8.6)
const plotBoundary = () => rectangle(39.24, 8.54, 39.241, 8.541)
function ready() { const store = createTerritoryStore(); store.getState().session('office-a:officer-a', context, true); return store }
function territory(store = ready()) {
  store.getState().beginTerritory(); store.getState().updateTerritory({ name: 'Entered name stays private', region: 'Example region', district: 'Example district' }); store.getState().preview(boundary()); expect(store.getState().saveTerritory()).toBe(true); return store
}
function plot(store = territory(), geometry = plotBoundary()) {
  store.getState().enableDemoFarmers(); store.getState().beginPlot(); store.getState().preview(geometry); store.getState().updatePlot({ name: 'Example crop plot', farmerIds: ['DEMO-FARMER-0001'] }); store.getState().updateSeason({ crop: 'Maize', plantingDate: '2026-05-01' }); expect(store.getState().savePlot(false)).toBe(true); return store
}
beforeEach(() => { localStorage.clear(); vi.restoreAllMocks() })
describe('territory geography', () => {
  it('validates WGS84 ordering, area limits and nondegenerate geometry', () => {
    for (const box of [[39, 9, 38, 10], [0, 0, 0, 1], [-181, 0, 2, 1], [0, 89, 1, 91], [NaN, 0, 1, 1]]) expect(() => rectangle(...box as [number, number, number, number])).toThrow()
    expect(boundarySchema.safeParse({ type: 'Polygon', coordinates: [[[0, 0], [1, 1], [0, 1], [1, 0], [0, 0]]] }).success).toBe(false)
    const s = ready(); s.getState().beginTerritory(); s.getState().preview(rectangle(0, 0, 5, 5)); expect(s.getState().geometry).toBeNull(); expect(s.getState().error).toContain('10,000')
  })
  it('uses spherical area and distinguishes containment, shared edges and meaningful overlap', () => {
    const equator = measuredArea(rectangle(0, 0, 1, 1)), highLatitude = measuredArea(rectangle(0, 60, 1, 61))
    expect(equator / highLatitude).toBeGreaterThan(1.9)
    expect(contained(plotBoundary(), boundary())).toBe(true)
    expect(contained(rectangle(39.29, 8.54, 39.31, 8.55), boundary())).toBe(false)
    expect(sharedArea(rectangle(0, 0, 1, 1), rectangle(1, 0, 2, 1))).toBe(0)
    expect(sharedArea(plotBoundary(), plotBoundary())).toBeGreaterThan(10000)
  })
  it('respects holes and MultiPolygon territories', () => {
    const withHole = { ...boundary(), coordinates: [...boundary().coordinates, rectangle(39.23, 8.53, 39.25, 8.55).coordinates[0]] }
    expect(contained(plotBoundary(), withHole)).toBe(false)
    expect(contained(plotBoundary(), { type: 'MultiPolygon', coordinates: [boundary().coordinates] })).toBe(true)
  })
})
describe('territory lifecycle and authorization', () => {
  it('distinguishes unsupported, unavailable, genuinely empty, pending and assigned responses', () => {
    expect(territoryService.getAssigned(context).status).toBe('unsupported')
    expect(territoryService.getAssigned(null).status).toBe('connection-unavailable')
    expect(territoryService.getAssigned({ ...context, territory_workspace: { status: 'unavailable', territories: [] } }).status).toBe('unavailable')
    expect(territoryService.getAssigned({ ...context, territory_workspace: { status: 'available', territories: [] } })).toEqual({ status: 'available', territories: [] })
    const empty = ready(); empty.getState().session('office-a:officer-a', { ...context, territory_workspace: { status: 'available', territories: [] } }, true); expect(empty.getState().panel).toBe('territory')
    expect(territoryService.getAssigned({ ...context, territory_workspace: { status: 'available', territories: [{ ...demoTerritory, status: 'assigned' }] } }).status).toBe('unavailable')
    const assigned = { ...demoTerritory, origin: 'backend', status: 'assigned', officeId: context.office_id, authorizedPlotIds: [plotId] }
    const s = ready(); s.getState().session('office-a:officer-a', { ...context, territory_workspace: { status: 'available', territories: [assigned, { ...assigned, id: 'second-assignment' }] } }, true)
    expect(s.getState().currentId).toBe(assigned.id)
    s.getState().beginTerritory(); s.getState().updateTerritory({ name: 'Unsaved' }); expect(s.getState().switchTerritory('second-assignment')).toBe(false)
    expect(s.getState().switchTerritory('second-assignment', true)).toBe(true)
    s.getState().beginTerritory(assigned.id); expect(s.getState().error).toContain('read-only')
  })
  it('saves, restores, edits and undoes only completed local territory boundaries', () => {
    const s = territory(), id = s.getState().currentId
    expect(s.getState().territories[0].status).toBe('local-draft')
    s.getState().beginTerritory(id!); s.getState().setMode('draw-territory'); expect(s.getState().territories[0].boundary).toEqual(boundary())
    s.getState().preview(rectangle(39.2, 8.5, 39.31, 8.61)); s.getState().undoGeometry(); expect(s.getState().geometry).toEqual(boundary())
    s.getState().close(true); expect(s.getState().territories[0].boundary).toEqual(boundary())
    const restored = restoreLocalWorkspace('office-a:officer-a')!; expect(restored.territories[0].boundary).toEqual(boundary()); expect(restored.territories[0].name).toBe('Local territory 1')
    expect(JSON.stringify(restored)).not.toContain('Entered name stays private')
  })
  it('retains separate geometries, validates plots and flags overlaps without blanket rejection', () => {
    const s = plot(), saved = s.getState().plots[0]
    expect(farmPlotService.validate(saved.geometry, s.getState().territories[0], [saved])).toEqual([saved.id])
    s.getState().beginPlot(); s.getState().preview(rectangle(39.29, 8.54, 39.31, 8.55)); expect(s.getState().geometry).toBeNull(); expect(s.getState().error).toContain('crosses')
    s.getState().preview(plotBoundary()); s.getState().updatePlot({ name: 'Shared plot', farmerIds: ['DEMO-FARMER-0001'] }); expect(s.getState().savePlot(false)).toBe(false); expect(s.getState().savePlot(true)).toBe(true)
    expect(s.getState().plots).toHaveLength(2); expect(s.getState().territories[0].boundary).toEqual(boundary())
    s.getState().beginTerritory(s.getState().currentId!); s.getState().preview(rectangle(39.2, 8.5, 39.21, 8.51)); expect(s.getState().saveTerritory()).toBe(false)
    s.getState().close(true); s.getState().removePlot(saved.id); expect(s.getState().plots).toHaveLength(1); expect(s.getState().farmers).toHaveLength(2000)
  })
  it('handles corrupt, oversized, cross-referenced and unavailable device storage honestly', () => {
    localStorage.setItem(storageKey('broken'), '{bad'); const s = ready(); s.getState().session('broken', context, true); expect(s.getState().storageError).toContain('not restored')
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') }); const m = territory(); expect(m.getState().territories).toHaveLength(1); expect(m.getState().storageError).toContain('not been saved')
  })
})
describe('farmer privacy, relationships and live investigation boundary', () => {
  it('prepares territory-scoped Monitoring and deduplicated Outreach references without granting execution rights', () => {
    const s = plot(), p = s.getState().plots[0], second = { ...p, id: 'local-plot-second' }, plots = [p, second]
    const monitor = prepareMonitoringContext(p.territoryId, [p.id], plots, s.getState().seasons)
    expect(monitor.authority).toBe('local-preview'); expect(monitor.plotIds).toEqual([p.id])
    const outreach = prepareOutreachContext(p.territoryId, [p.id, second.id], plots, s.getState().farmers)
    expect(outreach.farmerIds).toEqual(['DEMO-FARMER-0001']); expect(outreach.authority).toBe('local-preview')
    expect(() => prepareOutreachContext('another-territory', [p.id], plots, s.getState().farmers)).toThrow()
  })
  it('permits only matching drawing modes and leaves saved records unchanged when canceling a preview', () => {
    const s = territory(); s.getState().setMode('draw-farm-plot'); expect(s.getState().mode).toBe('navigate')
    s.getState().beginPlot(); expect(s.getState().mode).toBe('draw-farm-plot'); s.getState().setMode('edit-territory'); expect(s.getState().mode).toBe('draw-farm-plot')
    s.getState().setMode('navigate'); s.getState().close(true); expect(s.getState().territories[0].boundary).toEqual(boundary())
  })
  it('links one temporary farmer to multiple plots without storing private form fields', () => {
    const s = territory(); s.getState().beginFarmer(); s.getState().updateFarmer({ displayName: 'Private Person', reference: 'private-ref', phone: '+251911123456', email: 'private@example.com', notes: 'private note' }); expect(s.getState().saveFarmer()).toBe(true)
    const farmerId = s.getState().farmers[0].id
    for (const geometry of [plotBoundary(), rectangle(39.25, 8.55, 39.251, 8.551)]) { s.getState().beginPlot(); s.getState().preview(geometry); s.getState().updatePlot({ name: 'Private plot name', farmerIds: [farmerId], notes: 'sensitive observations' }); expect(s.getState().savePlot(false)).toBe(true) }
    expect(s.getState().plots.filter(p => p.farmerIds.includes(farmerId))).toHaveLength(2)
    const saved = localStorage.getItem(storageKey('office-a:officer-a'))!
    for (const privateValue of ['Private Person', 'private-ref', '+251911123456', 'private@example.com', 'private note', 'Private plot name', 'sensitive observations', farmerId]) expect(saved).not.toContain(privateValue)
    s.getState().session('another-office:another-officer', context, true); expect(s.getState().farmers).toHaveLength(0); expect(s.getState().plots).toHaveLength(0)
  })
  it('detects duplicate references and invalid contacts, with unknown optional agricultural values', () => {
    const s = territory(); s.getState().enableDemoFarmers(); s.getState().beginFarmer(); s.getState().updateFarmer({ displayName: 'Example', reference: 'DEMO-REF-0001' }); expect(s.getState().saveFarmer()).toBe(false)
    s.getState().updateFarmer({ reference: 'unique', phone: 'invalid' }); expect(s.getState().saveFarmer()).toBe(false)
    expect(s.getState().seasonForm.plantingDate).toBe(''); expect(s.getState().seasonForm.stage).toBe('Unknown')
  })
  it('restores only deterministic synthetic references, and cannot promote a local ID to backend authorization', () => {
    const s = plot(); expect(restoreLocalWorkspace('office-a:officer-a')!.plots[0].farmerIds).toEqual(['DEMO-FARMER-0001'])
    expect(farmInvestigationService.resolve(s.getState().plots[0].id, context)).toBeNull()
    expect(farmInvestigationService.resolve(plotId, context)?.authorized).toBe(true)
  })
  it('blocks local selections and untrusted IDs before any skill request; clearing analysis keeps territories', async () => {
    const api = { clearSession: vi.fn(), start: vi.fn() }, h = createHomeStore(api as unknown as HomeApi)
    h.setState({ context, session: 'ready', selectedIds: [plotId], skillId: context.skills[0].id, authorizations: { network: true, model: true, credit: false } })
    h.getState().setLocalDraftSelected(true); expect(investigationBlock(h.getState())).toContain('registered, authorized')
    await h.getState().submit('Inspect this local draft'); expect(api.start).not.toHaveBeenCalled()
    h.getState().setLocalDraftSelected(false); h.setState({ selectedIds: ['local-plot-invented'] }); await h.getState().submit('Inspect an invented ID'); expect(api.start).not.toHaveBeenCalled()
    const t = plot(); h.getState().clearSelection(); expect(t.getState().territories).toHaveLength(1); expect(t.getState().plots).toHaveLength(1)
    h.getState().logout(); expect(h.getState().localDraftSelected).toBe(false)
  })
})
