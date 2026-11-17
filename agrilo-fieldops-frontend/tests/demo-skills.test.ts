import { beforeEach, expect, it, vi } from 'vitest'
import { homeApi, homeStore } from '../src/state/useHome'
import { demoSkillsStore, collectDemo, askDemoAI, recoverDemo } from '../src/features/skills/demo-runtime'
import { HomeApiError } from '../src/api/home-api'
import { context, evidence, job, result } from './home-fixtures'

beforeEach(() => {
  vi.restoreAllMocks()
  homeStore.setState({ session: 'signed_out', context: null })
  homeStore.setState({ session: 'ready', context: structuredClone(context) })
})

it('collects photo evidence then asks AI with only the source report ID and no repeated upload or provider consent', async () => {
  const upload = vi.spyOn(homeApi, 'upload').mockResolvedValue({ id: 'fixture-private-image', media_type: 'image/jpeg', byte_size: 123 })
  const request = vi.spyOn(homeApi, 'skillRequest').mockResolvedValue({ ...job, id: 'photo-evidence', status: 'succeeded', result })
  vi.spyOn(homeApi, 'evidence').mockResolvedValue(evidence)
  await collectDemo('photo', 'fixture-photo-skill', { plot_ids: [], authorize_network: true, authorize_credit_use: true }, new File(['fixture'], 'crop.jpg', { type: 'image/jpeg' }))
  expect(demoSkillsStore.getState().photo.evidence).toEqual([evidence])
  expect(JSON.parse(request.mock.calls[0][2]!.body as string)).toMatchObject({ image_asset_id: 'fixture-private-image', plot_ids: [], authorize_credit_use: true })
  request.mockResolvedValue({ ...job, id: 'ai-explanation', status: 'succeeded', result })
  await askDemoAI('photo', 'fixture-photo-skill', 'Explain the crop candidates and general crop care.')
  expect(upload).toHaveBeenCalledTimes(1)
  const body = JSON.parse(request.mock.calls[1][2]!.body as string)
  expect(body).toMatchObject({ evidence_job_id: 'photo-evidence', authorize_model: true })
  expect(body).not.toHaveProperty('image_asset_id')
  expect(body).not.toHaveProperty('authorize_network')
  expect(localStorage.length).toBe(0)
})

it('recovers an uncertain POST with the same request key instead of submitting another rainfall request', async () => {
  const request = vi.spyOn(homeApi, 'skillRequest').mockRejectedValueOnce(new HomeApiError('Connection interrupted', 0, 'BACKEND_UNAVAILABLE', true))
  vi.spyOn(homeApi, 'evidence').mockResolvedValue(evidence)
  await collectDemo('rainfall', 'fixture-rainfall', { territory_id: 'assigned-territory', start: '2025-07-01', end: '2025-07-31', authorize_network: true })
  expect(demoSkillsStore.getState().rainfall.pending).not.toBeNull()
  request.mockResolvedValue({ ...job, id: 'recovered-report', status: 'succeeded', result })
  await recoverDemo('rainfall')
  expect(request.mock.calls[1][2]!.body).toBe(request.mock.calls[0][2]!.body)
  expect(demoSkillsStore.getState().rainfall.pending).toBeNull()
})

it('aborts and discards a report response after the officer session changes', async () => {
  let finish!: (value: unknown) => void
  vi.spyOn(homeApi, 'skillRequest').mockImplementation((_path, signal) => new Promise((resolve, reject) => {
    finish = resolve
    signal.addEventListener('abort', () => reject(new DOMException('Session changed', 'AbortError')), { once: true })
  }))
  const pending = collectDemo('rainfall', 'fixture-rainfall', { territory_id: 'assigned-territory' })
  homeStore.setState({ session: 'signed_out', context: null })
  finish({ ...job, status: 'succeeded', result })
  await pending
  expect(demoSkillsStore.getState().owner).toBeNull()
  expect(demoSkillsStore.getState().rainfall.evidenceJob).toBeNull()
  expect(demoSkillsStore.getState().rainfall.evidence).toEqual([])
})
