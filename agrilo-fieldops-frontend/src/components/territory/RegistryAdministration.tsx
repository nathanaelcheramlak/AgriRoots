import { useEffect, useState } from 'react'
import { z } from 'zod'
import { useHome } from '../../state/useHome'
import { useTerritory } from '../../features/territory/store'
import { registryRequest, write } from '../../features/territory/backend'

const memberSchema = z.object({ items: z.array(z.object({ user_id: z.string(), role: z.string() })) })
const assignmentSchema = z.object({ items: z.array(z.object({ id: z.string(), user_id: z.string(), role: z.string(), revoked: z.boolean(), revision: z.number(), starts_at: z.string(), ends_at: z.string().nullable() })) })
export function RegistryAdministration() {
  const s = useTerritory(), h = useHome(), t = s.territories.find(t => t.id === s.currentId)
  const [members, setMembers] = useState<z.infer<typeof memberSchema>['items']>([]), [assignments, setAssignments] = useState<z.infer<typeof assignmentSchema>['items']>([])
  const [user, setUser] = useState(''), [error, setError] = useState(''), [busy, setBusy] = useState(false), [serial, setSerial] = useState(0)
  const admin = h.context?.role === 'office_admin'
  useEffect(() => {
    const controller = new AbortController()
    if (admin && t?.origin === 'backend') {
      Promise.all([registryRequest('/members', {}, controller.signal), registryRequest(`/territories/${t.id}/assignments`, {}, controller.signal)])
        .then(([m, a]) => { setMembers(memberSchema.parse(m).items); setAssignments(assignmentSchema.parse(a).items) })
        .catch(e => { if (!controller.signal.aborted) setError(e instanceof Error ? e.message : 'Could not load office assignments') })
    }
    return () => controller.abort()
  }, [admin, t?.id, t?.origin, serial])
  const assign = async () => {
    if (!t || !user) return
    setBusy(true); setError('')
    try { await registryRequest(`/territories/${t.id}/assignments`, write({ user_id: user, role: 'manager' })); setSerial(v => v + 1) }
    catch (e) { setError(e instanceof Error ? e.message : 'Assignment failed') } finally { setBusy(false) }
  }
  return <section className="territory-form-section"><button className="plugin-secondary" disabled={s.busy} onClick={() => void s.refreshRegistry()}>Refresh office registry</button>
    {admin && t?.origin === 'backend' && <><h3>Office approval and assignments</h3>
      {t.status === 'pending-approval' && <div className="territory-actions"><button className="plugin-primary" disabled={s.busy} onClick={() => void s.reviewTerritory('approve')}>Approve territory boundary</button><button className="plugin-secondary" disabled={s.busy} onClick={() => void s.reviewTerritory('reject')}>Reject proposal</button></div>}
      {t.status === 'assigned' && <><label>Assign office staff<select value={user} onChange={e => setUser(e.target.value)}><option value="">Choose an officer</option>{members.map(m => <option key={m.user_id} value={m.user_id}>{m.user_id === h.context?.user_id ? 'Me' : m.user_id} · {m.role}</option>)}</select></label><button className="plugin-primary" disabled={!user || busy} onClick={() => void assign()}>Assign territory manager</button></>}
      {assignments.map(a => <p key={a.id}>{a.user_id} · {a.role} · {a.revoked ? 'Revoked' : `Effective ${a.starts_at}${a.ends_at ? ' until ' + a.ends_at : ''}`}{!a.revoked && <button className="plugin-secondary" disabled={busy} onClick={async () => { setBusy(true); try { await registryRequest(`/assignments/${a.id}?expected_revision=${a.revision}`, { method: 'DELETE' }); setSerial(v => v + 1) } catch (e) { setError(e instanceof Error ? e.message : 'Revocation failed') } finally { setBusy(false) } }}>Revoke assignment</button>}</p>)}
    </>}{error && <p role="alert">{error}</p>}</section>
}
