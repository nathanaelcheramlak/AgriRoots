import { createStore } from 'zustand/vanilla'
import { abortableDelay } from '../../api/fieldops-api'
import type { ManagedPluginApi, ManagedConnection, ManagedProvider, ManagedTool, Diagnostic } from './managed-api'
import { connectionSchema, toolSchema, diagnosticSchema } from './managed-api'

export interface ManagedIdentity { user: string; office: string; role: string }
interface ManagedState {
  identity: ManagedIdentity | null; providers: ManagedProvider[]; connections: ManagedConnection[];
  tools: Record<string, ManagedTool[]>; tests: Record<string, Diagnostic[]>; jobs: Record<string, Diagnostic>;
  busy: boolean; loaded: boolean; error: string | null; notice: string | null;
  reset(identity: ManagedIdentity | null): void; refresh(): Promise<void>;
  perform(work: (signal: AbortSignal) => Promise<void>): Promise<boolean>;
  watch(connectionId: string, job: Diagnostic, signal: AbortSignal): Promise<void>;
}
export function createManagedStore(api: ManagedPluginApi, pollMs = 1000) {
  let generation = 0, controller = new AbortController()
  return createStore<ManagedState>((set, get) => {
    const read = async (signal: AbortSignal) => {
      const token = generation
      const [providers, connections] = await Promise.all([api.providers(signal), api.pages('/integrations', connectionSchema, signal)])
      const rows = []
      // Bound concurrent reads for large office registries.
      for (let i = 0; i < connections.length; i += 4) rows.push(...await Promise.all(connections.slice(i, i + 4).map(async c => ({ id: c.id,
        tools: await api.pages(`/integrations/${c.id}/tools`, toolSchema, signal), tests: await api.pages(`/integrations/${c.id}/tests`, diagnosticSchema, signal) }))))
      if (token === generation && !signal.aborted) set({ providers, connections, tools: Object.fromEntries(rows.map(r => [r.id, r.tools])), tests: Object.fromEntries(rows.map(r => [r.id, r.tests])), loaded: true })
    }
    return {
      identity: null, providers: [], connections: [], tools: {}, tests: {}, jobs: {}, busy: false, loaded: false, error: null, notice: null,
      reset(identity) { generation++; controller.abort(); controller = new AbortController(); set({ identity, providers: [], connections: [], tools: {}, tests: {}, jobs: {}, loaded: false, busy: false, error: null, notice: null }) },
      async refresh() { if (!get().identity || get().busy) return; const token = generation; set({ busy: true, error: null }); try { await read(controller.signal) } catch (e) { if (token === generation) set({ error: e instanceof Error ? e.message : 'Registry could not be loaded. No local data was substituted.' }) } finally { if (token === generation) set({ busy: false }) } },
      async perform(work) {
        if (get().busy || !get().identity) return false
        const token = generation, signal = controller.signal
        set({ busy: true, error: null, notice: null })
        try { await work(signal); if (token !== generation || signal.aborted) return false; await read(signal); if (token === generation) set({ notice: 'Backend action confirmed. Review the recorded states below.' }); return token === generation }
        catch (e) { if (token === generation) { set({ error: (e instanceof Error ? e.message : 'Backend action failed.') + ' Refresh before retrying an uncertain write; registration is not idempotent.' }); try { await read(signal) } catch { /* Preserve the original error and last confirmed snapshot. */ } } return false }
        finally { if (token === generation) set({ busy: false }) }
      },
      async watch(connectionId, initial, signal) {
        const token = generation
        let job = initial
        for (let i = 0; i < 120; i++) {
          if (token !== generation || signal.aborted) return
          set(s => ({ jobs: { ...s.jobs, [connectionId]: job } }))
          if (!['queued', 'running'].includes(job.status)) {
            if (job.status !== 'succeeded') throw new Error(`${job.status}: ${job.error?.code ?? 'INCOMPLETE'} · ${job.error?.message ?? 'Inspect the actual diagnostics; success was not assumed.'}`)
            return
          }
          await abortableDelay(pollMs, signal)
          job = diagnosticSchema.parse(await api.call(`/connector-jobs/${job.id}`, signal))
        }
        throw new Error('Status polling paused. Use Refresh status on this job; do not submit it again.')
      },
    }
  })
}
