const API_BASE = '/api/admin/v1'

interface RequestOptions {
  method?: string
  body?: unknown
  params?: Record<string, string>
}

class ApiClient {
  private token: string | null = null

  setToken(token: string | null) {
    this.token = token
    if (token) localStorage.setItem('cf_admin_token', token)
    else localStorage.removeItem('cf_admin_token')
  }

  getToken(): string | null {
    if (!this.token) this.token = localStorage.getItem('cf_admin_token')
    return this.token
  }

  async request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, params } = options
    let url = `${API_BASE}${endpoint}`
    if (params) {
      const qs = new URLSearchParams(params).toString()
      url += `?${qs}`
    }

    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    const token = this.getToken()
    if (token) headers['Authorization'] = `Bearer ${token}`

    const resp = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    })

    if (resp.status === 401) {
      this.setToken(null)
      window.location.href = '/login'
      throw new Error('Unauthorized')
    }

    if (!resp.ok) {
      const err = await resp.json().catch(() => ({ error: resp.statusText }))
      throw new Error(err.error || err.detail || resp.statusText)
    }

    if (resp.status === 204) return {} as T
    return resp.json()
  }

  get<T>(endpoint: string, params?: Record<string, string>) {
    return this.request<T>(endpoint, { params })
  }

  post<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'POST', body })
  }

  patch<T>(endpoint: string, body?: unknown) {
    return this.request<T>(endpoint, { method: 'PATCH', body })
  }

  delete<T>(endpoint: string) {
    return this.request<T>(endpoint, { method: 'DELETE' })
  }
}

export const api = new ApiClient()
