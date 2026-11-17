import { useState } from 'react'
import { ArrowRight, LockKeyhole, Radio, Globe2 } from 'lucide-react'
import { customInputSchema } from '../../features/plugins/types'
import type { CustomInput, PluginDraft } from '../../features/plugins/types'
import { usePlugins } from '../../features/plugins/store'
import { PluginModal } from './PluginModal'

export function PluginForm({ kind, existing, onClose, onSaved }: { kind: 'mcp' | 'rest'; existing?: PluginDraft; onClose: () => void; onSaved: (id: string) => void }) {
  const state = usePlugins(), initial = existing?.type === 'custom' ? existing.configuration : null
  const [values, setValues] = useState<CustomInput>(initial ?? { kind, name: '', description: '', endpoint: '', authMethod: 'none', apiKeyHeader: '' })
  const [errors, setErrors] = useState<Record<string, string>>({}), [busy, setBusy] = useState(false), [failure, setFailure] = useState<string | null>(null)
  const change = <K extends keyof CustomInput>(key: K, value: CustomInput[K]) => { setValues(previous => ({ ...previous, [key]: value })); setErrors(previous => ({ ...previous, [key]: '' })); setFailure(null) }
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setFailure(null)
    const parsed = customInputSchema.safeParse(values)
    if (!parsed.success) { setErrors(Object.fromEntries(parsed.error.issues.map(issue => [String(issue.path[0]), issue.message]))); return }
    setBusy(true)
    try { const draft = await state.saveCustom(parsed.data, existing?.id); onSaved(draft.id) }
    catch { setFailure('Could not save this draft on your device. Check browser storage permissions and try again.'); setBusy(false) }
  }
  return <PluginModal title={`${existing ? 'Edit' : 'Add'} ${kind === 'mcp' ? 'MCP server' : 'API plugin'}`} onClose={onClose}>
    <div className="plugin-form-intro"><span className="form-connection-icon">{kind === 'mcp' ? <Radio size={23} /> : <Globe2 size={23} />}</span><div><strong>A connection starts with a draft.</strong><p>Save the configuration on this device. No server will be contacted.</p></div></div>
    <form className="plugin-config-form" onSubmit={submit} noValidate>
      <label htmlFor="plugin-name">Name<input id="plugin-name" value={values.name} maxLength={80} placeholder={kind === 'mcp' ? 'My agricultural MCP server' : 'My field data API'} onChange={e => change('name', e.target.value)} aria-invalid={!!errors.name} aria-describedby={errors.name ? 'plugin-name-error' : undefined} /></label>{errors.name && <p className="plugin-field-error" id="plugin-name-error">{errors.name}</p>}
      <label htmlFor="plugin-description">Description <span>Optional</span><textarea id="plugin-description" rows={2} maxLength={500} value={values.description} placeholder="What will this connection help you do?" onChange={e => change('description', e.target.value)} aria-invalid={!!errors.description} /></label>{errors.description && <p className="plugin-field-error">{errors.description}</p>}
      <label htmlFor="plugin-endpoint">{kind === 'mcp' ? 'Server URL' : 'Base URL'}<input id="plugin-endpoint" type="url" autoComplete="off" spellCheck={false} value={values.endpoint} placeholder={kind === 'mcp' ? 'https://your-server.example/mcp' : 'https://your-api.example/v1'} onChange={e => change('endpoint', e.target.value)} aria-invalid={!!errors.endpoint} aria-describedby="plugin-endpoint-help plugin-endpoint-error" /></label><p className="plugin-input-help" id="plugin-endpoint-help">{kind === 'mcp' ? 'HTTP MCP endpoint. ' : ''}Use a credential-free URL. No query parameters, fragments, passwords, or tokens.</p>{errors.endpoint && <p className="plugin-field-error" id="plugin-endpoint-error">{errors.endpoint}</p>}
      <label htmlFor="plugin-auth">Authentication method<select id="plugin-auth" value={values.authMethod} onChange={e => { const authMethod = e.target.value as CustomInput['authMethod']; setValues(previous => ({ ...previous, authMethod, apiKeyHeader: authMethod === 'api_key' ? 'X-API-Key' : '' })); setErrors(previous => ({ ...previous, apiKeyHeader: '' })) }}><option value="none">None</option><option value="api_key">API key</option><option value="bearer">Bearer token</option></select></label>
      {values.authMethod === 'api_key' && <><label htmlFor="plugin-header">API key header name<input id="plugin-header" value={values.apiKeyHeader} maxLength={64} placeholder="X-API-Key" onChange={e => change('apiKeyHeader', e.target.value)} aria-invalid={!!errors.apiKeyHeader} /></label>{errors.apiKeyHeader && <p className="plugin-field-error">{errors.apiKeyHeader}</p>}</>}
      <div className="plugin-credential-note"><LockKeyhole size={16} /><p>Only the authentication method is saved. Credentials will be set up through the future backend; do not paste them into any field.</p></div>
      {failure && <p className="plugin-field-error" role="alert">{failure}</p>}
      <footer className="plugin-form-actions"><button type="button" className="plugin-secondary" onClick={onClose}>Cancel</button><button className="plugin-primary" type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save draft'}<ArrowRight size={15} /></button></footer>
    </form>
  </PluginModal>
}
