const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8001'

export interface AuthResponse {
  access_token: string
  token_type: string
  tenant_id: string
  user_id: string
  role: 'admin' | 'editor' | 'viewer'
}

export interface DocumentItem {
  id: string
  tenant_id: string
  title: string
  mime_type: string
  size_bytes: number
  source: 'local' | 'google_drive' | 'external_dms'
  folder_id: string | null
  created_at: string
}

export interface SearchMatch {
  document_id: string
  document_title: string
  chunk_index: number
  content: string
  score: number
}

export interface SearchResponse {
  query: string
  summary: string
  results: SearchMatch[]
}

export interface IntegrationItem {
  id: string
  provider: 'google_drive' | 'external_dms'
  base_url: string | null
  sync_cursor: string | null
  is_active: boolean
  updated_at: string
}

export interface AuditLogItem {
  id: string
  actor_user_id: string
  action: string
  resource_type: string
  resource_id: string
  created_at: string
}

async function request<T>(
  path: string,
  options: RequestInit = {},
  token?: string
): Promise<T> {
  const headers = new Headers(options.headers || {})
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  if (!(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json')
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers })
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  registerTenant(payload: {
    tenant_name: string
    tenant_slug: string
    admin_email: string
    admin_password: string
  }) {
    return request<AuthResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  login(payload: { tenant_slug: string; email: string; password: string }) {
    return request<AuthResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify(payload),
    })
  },

  listDocuments(token: string) {
    return request<DocumentItem[]>('/api/v1/documents', {}, token)
  },

  uploadDocument(token: string, file: File) {
    const form = new FormData()
    form.append('file', file)
    return request<DocumentItem>(
      '/api/v1/documents',
      { method: 'POST', body: form },
      token
    )
  },

  indexDocument(token: string, documentId: string) {
    return request<{ document_id: string; chunks_indexed: number }>(
      `/api/v1/documents/${documentId}/index`,
      { method: 'POST' },
      token
    )
  },

  semanticSearch(token: string, query: string, limit = 5) {
    return request<SearchResponse>(
      '/api/v1/search',
      { method: 'POST', body: JSON.stringify({ query, limit }) },
      token
    )
  },

  listIntegrations(token: string) {
    return request<IntegrationItem[]>('/api/v1/integrations', {}, token)
  },

  connectIntegration(
    token: string,
    provider: 'google_drive' | 'external_dms',
    payload: { access_token: string; base_url?: string }
  ) {
    return request<IntegrationItem>(
      `/api/v1/integrations/${provider}`,
      { method: 'POST', body: JSON.stringify(payload) },
      token
    )
  },

  syncIntegration(token: string, provider: 'google_drive' | 'external_dms') {
    return request<{ synced_count: number; next_cursor: string | null }>(
      `/api/v1/integrations/${provider}/sync`,
      { method: 'POST' },
      token
    )
  },

  listAuditLogs(token: string) {
    return request<AuditLogItem[]>('/api/v1/audit-logs', {}, token)
  },
}
