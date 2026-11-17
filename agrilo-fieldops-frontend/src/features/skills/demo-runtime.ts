import { createStore } from 'zustand/vanilla'
import { useStore } from 'zustand'
import { homeApi, homeStore } from '../../state/useHome'
import { HomeApiError } from '../../api/home-api'
import { jobSchema, resultSchema, type HomeEvidence, type HomeJob } from '../../api/home-contracts'

export type DemoKind = 'photo' | 'rainfall'
type Report = { evidenceJob: HomeJob | null; aiJob: HomeJob | null; evidence: HomeEvidence[]; busy: boolean; error: string | null; pending: { skill: string; phase: 'evidence-runs' | 'explanations'; body: Record<string, unknown> } | null }
const blank = (): Report => ({ evidenceJob: null, aiJob: null, evidence: [], busy: false, error: null, pending: null })
const controllers: Partial<Record<DemoKind, AbortController>> = {}
type State = { owner: string | null; photo: Report; rainfall: Report }
export const demoSkillsStore = createStore<State>(() => ({ owner: null, photo: blank(), rainfall: blank() }))
export const useDemoSkills = () => useStore(demoSkillsStore)
const owner = () => { const h = homeStore.getState(); return h.session === 'ready' && h.context ? `${h.context.office_id}:${h.context.user_id}:${h.context.role}` : null }
const sync = () => {
  const next = owner()
  if (next === demoSkillsStore.getState().owner) return
  Object.values(controllers).forEach(c => c?.abort())
  demoSkillsStore.setState({ owner: next, photo: blank(), rainfall: blank() })
}
homeStore.subscribe(sync); sync()
const patch = (kind: DemoKind, update: Partial<Report>) => demoSkillsStore.setState(s => ({ [kind]: { ...s[kind], ...update } }))
const assertActive = (signal: AbortSignal) => { if (signal.aborted) throw new DOMException('Session changed', 'AbortError') }
export const activeDemoJob = (r: Report) => r.aiJob ?? r.evidenceJob
export const jobActive = (j: HomeJob | null) => !!j && ['queued', 'running'].includes(j.status)

async function operation(kind: DemoKind, run: (signal: AbortSignal) => Promise<void>) {
  controllers[kind]?.abort()
  const controller = new AbortController(), current = owner()
  controllers[kind] = controller
  patch(kind, { busy: true, error: null })
  try { await run(controller.signal) }
  catch (e) { if (!controller.signal.aborted && current === owner()) patch(kind, { error: e instanceof Error ? e.message : 'The request failed.' }) }
  finally { if (controllers[kind] === controller && current === owner()) patch(kind, { busy: false }) }
}
async function follow(kind: DemoKind, job: HomeJob, ai: boolean, signal: AbortSignal) {
  const update = (j: HomeJob) => { assertActive(signal); patch(kind, ai ? { aiJob: j } : { evidenceJob: j }) }
  update(job)
  while (jobActive(job)) {
    await new Promise<void>((resolve, reject) => {
      const abort = () => { clearTimeout(timer); reject(new DOMException('Aborted', 'AbortError')) }
      const timer = setTimeout(() => { signal.removeEventListener('abort', abort); resolve() }, 1200)
      signal.addEventListener('abort', abort, { once: true })
      if (signal.aborted) abort()
    })
    job = await homeApi.job(job.id, signal); update(job)
  }
  const result = resultSchema.safeParse(job.result)
  if (!ai && result.success) {
    const evidence = await Promise.all(result.data.evidence_ids.map(id => homeApi.evidence(id, signal)))
    assertActive(signal)
    patch(kind, { evidence })
  }
  if (job.error) patch(kind, { error: job.error.message })
}
async function post(kind: DemoKind, pending: NonNullable<Report['pending']>, signal: AbortSignal) {
  patch(kind, { pending })
  let job: HomeJob
  try { job = jobSchema.parse(await homeApi.skillRequest(`/api/v1/skills/${encodeURIComponent(pending.skill)}/${pending.phase}`, signal, { method: 'POST', body: JSON.stringify(pending.body) })) }
  catch (e) {
    if (!signal.aborted && !(e instanceof HomeApiError && e.ambiguous)) patch(kind, { pending: null })
    throw e
  }
  assertActive(signal)
  patch(kind, { pending: null })
  await follow(kind, job, pending.phase === 'explanations', signal)
}
export const collectDemo = (kind: DemoKind, skill: string, body: Record<string, unknown>, file?: File) => operation(kind, async signal => {
  if (jobActive(activeDemoJob(demoSkillsStore.getState()[kind]))) throw new Error('Wait for the current report or cancel it first.')
  if (demoSkillsStore.getState()[kind].pending) throw new Error('Recover the uncertain submission before starting another report.')
  const image = file ? await homeApi.upload(file, signal) : null
  assertActive(signal)
  patch(kind, { evidenceJob: null, aiJob: null, evidence: [] })
  await post(kind, { skill, phase: 'evidence-runs', body: { ...body, ...(image ? { image_asset_id: image.id } : {}), request_key: crypto.randomUUID() } }, signal)
})
export const askDemoAI = (kind: DemoKind, skill: string, task: string) => operation(kind, async signal => {
  const report = demoSkillsStore.getState()[kind]
  if (!report.evidenceJob || !report.evidence.length || jobActive(activeDemoJob(report))) throw new Error('Collect valid provider evidence first.')
  await post(kind, { skill, phase: 'explanations', body: { evidence_job_id: report.evidenceJob.id, task, authorize_model: true, request_key: crypto.randomUUID() } }, signal)
})
export const recoverDemo = (kind: DemoKind) => operation(kind, async signal => {
  const report = demoSkillsStore.getState()[kind]
  if (report.pending) return post(kind, report.pending, signal)
  const job = activeDemoJob(report)
  if (job) await follow(kind, await homeApi.job(job.id, signal), job.id === report.aiJob?.id, signal)
})
export const cancelDemo = (kind: DemoKind) => operation(kind, async signal => {
  const report = demoSkillsStore.getState()[kind], job = activeDemoJob(report)
  if (job && jobActive(job)) await follow(kind, await homeApi.cancel(job.id, signal), job.id === report.aiJob?.id, signal)
})
