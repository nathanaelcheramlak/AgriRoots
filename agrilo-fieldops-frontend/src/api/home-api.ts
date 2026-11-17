import { z } from 'zod'
import { authSchema, evidenceResponseSchema, homeContextSchema, jobSchema } from './home-contracts'
import type { HomeRunInput } from './home-contracts'

export class HomeApiError extends Error {
  constructor(message: string, readonly status: number, readonly code: string, readonly ambiguous = false) { super(message) }
}
export class HomeApi {
  private token: string | null = null
  private sessionVersion = 0
  onSessionExpired: (() => void) | undefined
  constructor(private readonly baseUrl: string, private readonly transport: typeof fetch = (...args) => fetch(...args)) {}
  clearSession() { this.token = null; this.sessionVersion++ }
  async connectorRequest(path: string, signal: AbortSignal, options: RequestInit = {}): Promise<unknown> {
    if (!/^\/api\/v1\/(providers|integrations|connector-jobs|audit)(\/|\?|$)/.test(path)) throw new Error('Unsupported connection-management route.')
    const version = this.sessionVersion
    const data = await this.request(path, signal, options)
    if (signal.aborted || version !== this.sessionVersion) throw new DOMException('Session changed', 'AbortError')
    return data
  }
  async skillRequest(path: string, signal: AbortSignal, options: RequestInit = {}): Promise<unknown> {
    if (!/^\/api\/v1\/skills(\/|\?|$)/.test(path)) throw new Error('Unsupported skill-management route.')
    const version = this.sessionVersion
    const data = await this.request(path, signal, options)
    if (signal.aborted || version !== this.sessionVersion) throw new DOMException('Session changed', 'AbortError')
    return data
  }
  private async request(path: string, signal: AbortSignal, options: RequestInit = {}): Promise<unknown> {
    const sessionVersion = this.sessionVersion
    let response: Response
    try {
      response = await this.transport(`${this.baseUrl.replace(/\/$/, '')}${path}`, { ...options, signal, credentials: 'omit',
        headers: { ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }), ...(this.token ? { Authorization: `Bearer ${this.token}` } : {}), ...options.headers },
      })
    } catch (error) {
      if (signal.aborted) throw error
      throw new HomeApiError('The backend could not be reached. No demo result was substituted.', 0, 'BACKEND_UNAVAILABLE', options.method === 'POST')
    }
    const data: unknown = await response.json().catch(() => null)
    if (!response.ok) {
      const body = z.object({ error: z.object({ code: z.string(), message: z.string() }).optional(), detail: z.unknown().optional() }).safeParse(data)
      const code = body.success ? body.data.error?.code : undefined
      // Provider AUTH_INVALID is also HTTP 401, but is not an expired officer session.
      if (response.status === 401 && code !== 'AUTH_INVALID' && path !== '/api/auth/login' && sessionVersion === this.sessionVersion) { this.clearSession(); this.onSessionExpired?.() }
      const message = body.success && body.data.error ? body.data.error.message : response.status === 401 && path === '/api/auth/login' ? 'Phone number or password was not accepted.' : response.status === 401 ? 'Sign in again. Your session is missing or expired.' : response.status === 403 ? 'Permission denied for this office or operation.' : response.status === 422 ? 'The backend rejected the supplied inputs.' : `Backend request failed (HTTP ${response.status}).`
      throw new HomeApiError(message, response.status, code ?? `HTTP_${response.status}`, response.status >= 500 && options.method === 'POST')
    }
    return data
  }
  async login(phone_number: string, password: string, signal: AbortSignal) {
    this.clearSession()
    const sessionVersion = this.sessionVersion
    const response = authSchema.parse(await this.request('/api/auth/login', signal, { method: 'POST', body: JSON.stringify({ phone_number, password }) }))
    if (signal.aborted || sessionVersion !== this.sessionVersion) throw new DOMException('Session changed', 'AbortError')
    this.token = response.access_token // In memory only; never localStorage, sessionStorage, URLs or logs.
    return response.user.user_id
  }
  async context(signal: AbortSignal) { return homeContextSchema.parse(await this.request('/api/v1/companion/context', signal)) }
  async start(skillId: string, input: HomeRunInput, signal: AbortSignal) { return jobSchema.parse(await this.request(`/api/v1/skills/${encodeURIComponent(skillId)}/runs`, signal, { method: 'POST', body: JSON.stringify(input) })) }
  async job(id: string, signal: AbortSignal) { return jobSchema.parse(await this.request(`/api/v1/connector-jobs/${encodeURIComponent(id)}?include_progress=true`, signal)) }
  async cancel(id: string, signal: AbortSignal) { return jobSchema.parse(await this.request(`/api/v1/runs/${encodeURIComponent(id)}/cancel`, signal, { method: 'POST' })) }
  async evidence(id: string, signal: AbortSignal) { return evidenceResponseSchema.parse(await this.request(`/api/v1/evidence/${encodeURIComponent(id)}`, signal)) }
  async upload(image: File, signal: AbortSignal) {
    if (!['image/jpeg', 'image/png'].includes(image.type) || image.size > 10 * 1024 * 1024 || !image.size) throw new Error('Choose a JPEG or PNG image up to 10 MB.')
    const form = new FormData(); form.append('image', image)
    return z.object({ id: z.string(), media_type: z.string(), byte_size: z.number() }).parse(await this.request('/api/v1/image-assets', signal, { method: 'POST', body: form }))
  }
}
