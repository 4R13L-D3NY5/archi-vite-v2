import { FormEvent, useEffect, useState } from 'react'
import {
  Cloud,
  FileText,
  LogOut,
  Search,
  ShieldCheck,
  Sparkles,
  Upload,
} from 'lucide-react'
import {
  api,
  AuditLogItem,
  AuthResponse,
  DocumentItem,
  IntegrationItem,
  SearchResponse,
} from './api/client'

type Tab = 'documents' | 'search' | 'integrations' | 'audit'

export default function App() {
  const [session, setSession] = useState<AuthResponse | null>(null)
  const [authMode, setAuthMode] = useState<'register' | 'login'>('register')
  const [tenantName, setTenantName] = useState('Acme Corp')
  const [tenantSlug, setTenantSlug] = useState('acme')
  const [email, setEmail] = useState('admin@acme.com')
  const [password, setPassword] = useState('strong-password-123')

  const [tab, setTab] = useState<Tab>('documents')
  const [documents, setDocuments] = useState<DocumentItem[]>([])
  const [integrations, setIntegrations] = useState<IntegrationItem[]>([])
  const [auditLogs, setAuditLogs] = useState<AuditLogItem[]>([])
  const [searchQuery, setSearchQuery] = useState('')
  const [searchResult, setSearchResult] = useState<SearchResponse | null>(null)

  const [driveToken, setDriveToken] = useState('')
  const [webdavUrl, setWebdavUrl] = useState('')
  const [webdavToken, setWebdavToken] = useState('')
  const [statusMsg, setStatusMsg] = useState<string | null>(null)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)

  async function refreshData(auth: AuthResponse) {
    const [docs, ints] = await Promise.all([
      api.listDocuments(auth.access_token),
      api.listIntegrations(auth.access_token),
    ])
    setDocuments(docs)
    setIntegrations(ints)
    if (auth.role === 'admin') {
      const logs = await api.listAuditLogs(auth.access_token)
      setAuditLogs(logs)
    }
  }

  useEffect(() => {
    if (session) {
      refreshData(session).catch((err) => setErrorMsg(err.message))
    }
  }, [session])

  async function handleAuth(e: FormEvent) {
    e.preventDefault()
    setErrorMsg(null)
    setStatusMsg(null)
    try {
      const res =
        authMode === 'register'
          ? await api.registerTenant({
              tenant_name: tenantName,
              tenant_slug: tenantSlug,
              admin_email: email,
              admin_password: password,
            })
          : await api.login({ tenant_slug: tenantSlug, email, password })
      setSession(res)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Authentication failed')
    }
  }

  async function handleFileUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    if (!session) return
    const input = e.currentTarget.elements.namedItem('docfile') as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    setErrorMsg(null)
    setStatusMsg('Uploading and queuing AI indexing...')
    try {
      await api.uploadDocument(session.access_token, file)
      input.value = ''
      await refreshData(session)
      setStatusMsg(`Uploaded "${file.name}" and queued for AI indexing.`)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed')
    }
  }

  async function handleIndexNow(docId: string) {
    if (!session) return
    setErrorMsg(null)
    try {
      const res = await api.indexDocument(session.access_token, docId)
      setStatusMsg(`Indexed ${res.chunks_indexed} chunk(s) into pgvector.`)
      await refreshData(session)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Indexing failed')
    }
  }

  async function handleSearch(e: FormEvent) {
    e.preventDefault()
    if (!session || !searchQuery.trim()) return
    setErrorMsg(null)
    try {
      const res = await api.semanticSearch(session.access_token, searchQuery)
      setSearchResult(res)
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Search failed')
    }
  }

  async function handleConnectDrive(e: FormEvent) {
    e.preventDefault()
    if (!session) return
    setErrorMsg(null)
    try {
      await api.connectIntegration(session.access_token, 'google_drive', {
        access_token: driveToken,
      })
      setDriveToken('')
      await refreshData(session)
      setStatusMsg('Google Drive connected.')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Connection failed')
    }
  }

  async function handleConnectWebdav(e: FormEvent) {
    e.preventDefault()
    if (!session) return
    setErrorMsg(null)
    try {
      await api.connectIntegration(session.access_token, 'external_dms', {
        access_token: webdavToken,
        base_url: webdavUrl,
      })
      setWebdavToken('')
      await refreshData(session)
      setStatusMsg('External WebDAV DMS connected.')
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : 'Connection failed')
    }
  }

  if (!session) {
    return (
      <div style={{ maxWidth: 420, margin: '80px auto', padding: 24, background: '#111827', borderRadius: 12, border: '1px solid #1f2937' }}>
        <h1 style={{ marginTop: 0, fontSize: 22 }}>archi-vite-v2</h1>
        <p style={{ color: '#94a3b8', fontSize: 14 }}>
          Multi-tenant Commercial DMS & AI RAG Workspace
        </p>
        <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
          <button
            type="button"
            onClick={() => setAuthMode('register')}
            style={{ flex: 1, padding: 8, borderRadius: 6, border: 'none', cursor: 'pointer', background: authMode === 'register' ? '#2563eb' : '#1e293b', color: '#fff' }}
          >
            Register Tenant
          </button>
          <button
            type="button"
            onClick={() => setAuthMode('login')}
            style={{ flex: 1, padding: 8, borderRadius: 6, border: 'none', cursor: 'pointer', background: authMode === 'login' ? '#2563eb' : '#1e293b', color: '#fff' }}
          >
            Login
          </button>
        </div>

        <form onSubmit={handleAuth} style={{ display: 'grid', gap: 10 }}>
          {authMode === 'register' && (
            <input
              placeholder="Organization Name"
              value={tenantName}
              onChange={(e) => setTenantName(e.target.value)}
              style={{ padding: 10, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
              required
            />
          )}
          <input
            placeholder="Tenant Slug (e.g. acme)"
            value={tenantSlug}
            onChange={(e) => setTenantSlug(e.target.value)}
            style={{ padding: 10, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
            required
          />
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ padding: 10, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
            required
          />
          <input
            type="password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ padding: 10, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
            required
          />
          {errorMsg && <div style={{ color: '#f87171', fontSize: 13 }}>{errorMsg}</div>}
          <button
            type="submit"
            style={{ padding: 10, borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
          >
            {authMode === 'register' ? 'Create Workspace' : 'Sign In'}
          </button>
        </form>
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <aside style={{ width: 240, background: '#111827', borderRight: '1px solid #1f2937', padding: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
        <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 4 }}>archi-vite-v2</div>
        <div style={{ fontSize: 12, color: '#94a3b8', marginBottom: 16 }}>
          Role: <strong>{session.role.toUpperCase()}</strong>
        </div>

        {(
          [
            ['documents', 'Documents', FileText],
            ['search', 'AI Semantic Search', Search],
            ['integrations', 'Drive & DMS', Cloud],
            ['audit', 'Audit Trail', ShieldCheck],
          ] as const
        ).map(([id, label, Icon]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 10,
              padding: '10px 12px',
              borderRadius: 8,
              border: 'none',
              cursor: 'pointer',
              background: tab === id ? '#1d4ed8' : 'transparent',
              color: '#e2e8f0',
              textAlign: 'left',
            }}
          >
            <Icon size={16} />
            {label}
          </button>
        ))}

        <button
          onClick={() => setSession(null)}
          style={{ marginTop: 'auto', display: 'flex', alignItems: 'center', gap: 8, padding: 10, borderRadius: 8, border: '1px solid #334155', background: 'transparent', color: '#cbd5e1', cursor: 'pointer' }}
        >
          <LogOut size={16} /> Sign Out
        </button>
      </aside>

      <main style={{ flex: 1, padding: 32, maxWidth: 960 }}>
        {statusMsg && (
          <div style={{ padding: 12, marginBottom: 16, borderRadius: 8, background: '#064e3b', color: '#a7f3d0', fontSize: 14 }}>
            {statusMsg}
          </div>
        )}
        {errorMsg && (
          <div style={{ padding: 12, marginBottom: 16, borderRadius: 8, background: '#7f1d1d', color: '#fecaca', fontSize: 14 }}>
            {errorMsg}
          </div>
        )}

        {tab === 'documents' && (
          <section>
            <h2 style={{ marginTop: 0 }}>Tenant Documents</h2>
            <form onSubmit={handleFileUpload} style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
              <input name="docfile" type="file" required />
              <button
                type="submit"
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '8px 14px', borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', cursor: 'pointer' }}
              >
                <Upload size={16} /> Upload
              </button>
            </form>

            <div style={{ display: 'grid', gap: 10 }}>
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 14, borderRadius: 8, background: '#111827', border: '1px solid #1f2937' }}
                >
                  <div>
                    <div style={{ fontWeight: 600 }}>{doc.title}</div>
                    <div style={{ fontSize: 12, color: '#94a3b8' }}>
                      {doc.mime_type} • {doc.size_bytes} bytes • source: {doc.source}
                    </div>
                  </div>
                  <button
                    onClick={() => handleIndexNow(doc.id)}
                    style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 10px', borderRadius: 6, border: '1px solid #334155', background: '#1e293b', color: '#e2e8f0', cursor: 'pointer', fontSize: 13 }}
                  >
                    <Sparkles size={14} /> Index AI
                  </button>
                </div>
              ))}
              {documents.length === 0 && <p style={{ color: '#64748b' }}>No documents uploaded yet.</p>}
            </div>
          </section>
        )}

        {tab === 'search' && (
          <section>
            <h2 style={{ marginTop: 0 }}>Semantic Search (pgvector RAG)</h2>
            <form onSubmit={handleSearch} style={{ display: 'flex', gap: 10, marginBottom: 20 }}>
              <input
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Ask or search across indexed documents..."
                style={{ flex: 1, padding: 10, borderRadius: 6, border: '1px solid #334155', background: '#111827', color: '#fff' }}
              />
              <button
                type="submit"
                style={{ padding: '10px 18px', borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', cursor: 'pointer' }}
              >
                Search
              </button>
            </form>

            {searchResult && (
              <div style={{ display: 'grid', gap: 12 }}>
                <div style={{ padding: 14, borderRadius: 8, background: '#1e293b', border: '1px solid #334155' }}>
                  <strong>Summary:</strong> {searchResult.summary}
                </div>
                {searchResult.results.map((m) => (
                  <div key={`${m.document_id}-${m.chunk_index}`} style={{ padding: 14, borderRadius: 8, background: '#111827', border: '1px solid #1f2937' }}>
                    <div style={{ fontSize: 13, color: '#60a5fa', marginBottom: 6 }}>
                      {m.document_title} (chunk #{m.chunk_index} • score {m.score.toFixed(3)})
                    </div>
                    <div style={{ fontSize: 14, color: '#cbd5e1' }}>{m.content}</div>
                  </div>
                ))}
              </div>
            )}
          </section>
        )}

        {tab === 'integrations' && (
          <section style={{ display: 'grid', gap: 20 }}>
            <h2 style={{ marginTop: 0 }}>External DMS Connectors</h2>
            <form onSubmit={handleConnectDrive} style={{ padding: 16, borderRadius: 8, background: '#111827', border: '1px solid #1f2937', display: 'grid', gap: 10 }}>
              <strong>Google Drive (REST API v3)</strong>
              <input
                placeholder="OAuth2 Access Token"
                value={driveToken}
                onChange={(e) => setDriveToken(e.target.value)}
                style={{ padding: 8, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
                required
              />
              <button type="submit" style={{ width: 180, padding: 8, borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', cursor: 'pointer' }}>
                Connect Google Drive
              </button>
            </form>

            <form onSubmit={handleConnectWebdav} style={{ padding: 16, borderRadius: 8, background: '#111827', border: '1px solid #1f2937', display: 'grid', gap: 10 }}>
              <strong>External WebDAV / Nextcloud DMS</strong>
              <input
                placeholder="Base URL (e.g. https://cloud.example.com/remote.php/dav/files/user)"
                value={webdavUrl}
                onChange={(e) => setWebdavUrl(e.target.value)}
                style={{ padding: 8, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
                required
              />
              <input
                placeholder="Bearer Token"
                value={webdavToken}
                onChange={(e) => setWebdavToken(e.target.value)}
                style={{ padding: 8, borderRadius: 6, border: '1px solid #334155', background: '#0f172a', color: '#fff' }}
                required
              />
              <button type="submit" style={{ width: 180, padding: 8, borderRadius: 6, border: 'none', background: '#2563eb', color: '#fff', cursor: 'pointer' }}>
                Connect WebDAV DMS
              </button>
            </form>

            <div>
              <h3>Active Connections ({integrations.length})</h3>
              {integrations.map((item) => (
                <div key={item.id} style={{ padding: 12, borderRadius: 8, background: '#111827', border: '1px solid #1f2937', marginBottom: 8 }}>
                  <strong>{item.provider}</strong> — cursor: {item.sync_cursor || 'initial'}
                </div>
              ))}
            </div>
          </section>
        )}

        {tab === 'audit' && (
          <section>
            <h2 style={{ marginTop: 0 }}>Audit Log (ADMIN)</h2>
            <div style={{ display: 'grid', gap: 8 }}>
              {auditLogs.map((log) => (
                <div key={log.id} style={{ padding: 12, borderRadius: 8, background: '#111827', border: '1px solid #1f2937', fontSize: 13 }}>
                  <strong>{log.action}</strong> • {log.resource_type} ({log.resource_id}) • {new Date(log.created_at).toLocaleString()}
                </div>
              ))}
              {auditLogs.length === 0 && <p style={{ color: '#64748b' }}>No audit entries yet.</p>}
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
