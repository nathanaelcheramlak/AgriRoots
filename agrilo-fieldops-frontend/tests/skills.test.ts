import { describe, expect, it, vi } from 'vitest'
import { HomeApi } from '../src/api/home-api'
import { createHomeStore, investigationBlock } from '../src/state/home-store'
import { SkillsApi, skillSchema } from '../src/features/skills/service'
import { createSkillsStore } from '../src/features/skills/store'
import { runtimeSkill, scopeLabel, unsupportedInputs, scientificLimits } from '../src/features/skills/presentation'
import { context, plotId, job, result, evidence } from './home-fixtures'
import { rectangleSelection } from '../src/lib/geo'

const skill = skillSchema.parse({ id: 'fixture-skill', name: 'fixture_combined', revision: 2, version: 2, version_id: 'new-draft', digest: 'd'.repeat(64), approved: false, enabled: true, enabled_version: 1, manifest: { name: 'fixture_combined', description: 'New draft', instructions: 'No permissions', required_capabilities: ['not.available'], optional_capabilities: [] }, execution: { version: 1, approved: true, available: true, blocked_reason: null, blocked_code: null, manifest: { name: 'fixture_combined', description: 'Enabled evidence', instructions: 'Explain limitations', required_capabilities: ['weather.forecast', 'soil.profile'], optional_capabilities: [] }, tools: context.skills[0].tools.map(t => ({ ...t, source: { name: 'Explicit fixture', host: 'example.invalid' } })), dependencies: [{ capability: 'soil.profile', required: true, available: true }], missing_optional_capabilities: [] } })
function setup() {
  const api = { clearSession: vi.fn(), login: vi.fn().mockResolvedValue('fixture-user'), context: vi.fn().mockResolvedValue(structuredClone(context)), start: vi.fn().mockResolvedValue(job), job: vi.fn().mockResolvedValue({ ...job, status: 'succeeded', result }), evidence: vi.fn().mockResolvedValue(evidence) }
  return { api, store: createHomeStore(api as unknown as HomeApi, 1) }
}
describe('Skills and Home shared execution', () => {
  it('preserves enabled runtime metadata independently of the newer draft and scientific caveats', () => {
    expect(skill.approved).toBe(false); expect(runtimeSkill(skill)?.version).toBe(1)
    expect(runtimeSkill(skill)?.description).toBe('Enabled evidence')
    expect(scopeLabel(runtimeSkill(skill))).toContain('Exactly one')
    expect(scientificLimits(skill).some(t => t.includes('laboratory'))).toBe(true)
  })
  it('prepares Home without a run, preserving geometry, conversation, history and map focus while renewing consent', async () => {
    const { api, store } = setup(); await store.getState().login('fixture-phone', 'fixture-pass')
    store.getState().selectFarm(plotId); store.getState().authorize('network', true); store.getState().authorize('model', true)
    await store.getState().submit('Inspect fixture evidence')
    const geometry = rectangleSelection({ lat: 9, lng: 38 }, { lat: 9.1, lng: 38.8 })
    store.getState().setSelection(geometry)
    const before = store.getState(), history = before.investigations, conversation = before.conversationId, focus = before.focus
    expect(await store.getState().prepareSkill('fixture-skill', [plotId], {})).toBe(true)
    expect(store.getState().selection).toBe(before.selection); expect(store.getState().focus).toBe(focus)
    expect(store.getState().investigations).toBe(history); expect(store.getState().conversationId).toBe(conversation)
    expect(store.getState().authorizations).toEqual({ network: false, model: false, credit: false })
    expect(api.start).toHaveBeenCalledTimes(1)
  })
  it('rejects foreign/duplicate farms and active or uncertain work without replacing Home', async () => {
    const { store, api } = setup(); await store.getState().login('fixture-phone', 'fixture-pass')
    expect(await store.getState().prepareSkill('fixture-skill', ['foreign'], {})).toBe(false)
    expect(await store.getState().prepareSkill('fixture-skill', [plotId, plotId], {})).toBe(false)
    store.setState({ activeId: 'existing-job' })
    expect(await store.getState().prepareSkill('fixture-skill', [plotId], {})).toBe(false)
    expect(store.getState().activeId).toBe('existing-job'); expect(api.start).not.toHaveBeenCalled()
  })
  it('refreshes availability and rejects revoked skills, unsupported fields and invalid required dates', async () => {
    const { store, api } = setup(); await store.getState().login('fixture-phone', 'fixture-pass')
    api.context.mockResolvedValue({ ...context, skills: [{ ...context.skills[0], available: false, blocked_reason: 'Dependency revoked' }] })
    expect(await store.getState().prepareSkill('fixture-skill', [plotId], {})).toBe(false)
    expect(store.getState().error).toBe('Dependency revoked')
    api.context.mockResolvedValue(structuredClone(context))
    expect(await store.getState().prepareSkill('fixture-skill', [plotId], { arbitrary_url: 'bad' })).toBe(false)
    const dated = { ...context.skills[0], tools: [{ ...context.skills[0].tools[0], input_schema: { properties: { start: { type: 'string', format: 'date' }, end: { type: 'string', format: 'date' } }, required: ['start', 'end'] } }] }
    store.setState({ context: { ...context, skills: [dated] }, selectedIds: [plotId], authorizations: { network: true, model: true, credit: false }, parameters: {} })
    expect(investigationBlock(store.getState())).toBe('Enter start.')
    store.setState({ parameters: { start: '2025-07-07', end: '2025-07-01' } })
    expect(investigationBlock(store.getState())).toContain('past date range')
    expect(unsupportedInputs({ ...dated, tools: [{ ...dated.tools[0], input_schema: { required: ['new_field'] } }] })).toEqual(['new_field'])
  })
  it('ignores a catalog response after logout rather than leaking a prior office', async () => {
    let finish!: (r: Response) => void
    const api = new SkillsApi(new HomeApi('/backend', () => new Promise(r => { finish = r }))), store = createSkillsStore(api)
    store.getState().reset({ user: 'fixture', office: 'office', role: 'extension_officer' })
    const pending = store.getState().refresh(); store.getState().reset(null)
    finish(new Response(JSON.stringify({ items: [skill] }), { status: 200 })); await pending
    expect(store.getState().identity).toBeNull(); expect(store.getState().items).toEqual([])
  })
})
