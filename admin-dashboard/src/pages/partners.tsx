import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Building2, Eye, Key, Globe, Plus, X, Trash2, Pencil, Save, Check, Copy, EyeOff, ShieldCheck, ShieldOff, Shield } from 'lucide-react'

interface Partner {
  id: string
  name: string
  slug: string
  website: string
  contact_email: string
  contact_phone: string
  status: string
  debit_url: string
  credit_url: string
  rollback_url: string
  commission_percent: string
  settlement_frequency: string
  min_settlement_amount: string
  notes: string
  total_sessions: number
  total_revenue: string
  api_keys_count: number
  created_at: string
  updated_at: string
}

interface ApiKey {
  id: string
  label: string
  api_key: string
  api_secret: string
  api_secret_hint: string
  is_active: boolean
  rate_limit_per_minute: number
  ip_whitelist: string[]
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
  just_created?: boolean
}

interface Choice { value: string; label: string }

interface PartnersResponse {
  results: Partner[]
  count: number
  status_choices: Choice[]
  settlement_choices: Choice[]
}

const statusVariant = (s: string) => s === 'active' ? 'success' as const : s === 'pending' ? 'warning' as const : 'danger' as const

export default function PartnersPage() {
  const [data, setData] = useState<PartnersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState<Partner | null>(null)
  const [editing, setEditing] = useState(false)
  const [editData, setEditData] = useState<Partial<Partner>>({})
  const [showCreate, setShowCreate] = useState(false)
  const [createData, setCreateData] = useState({ name: '', slug: '', website: '', contact_email: '', contact_phone: '', status: 'pending', commission_percent: '20', settlement_frequency: 'weekly' })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([])
  const [keysLoading, setKeysLoading] = useState(false)
  const [revealedSecrets, setRevealedSecrets] = useState<Set<string>>(new Set())
  const [newKeyLabel, setNewKeyLabel] = useState('')
  const [showNewKeyForm, setShowNewKeyForm] = useState(false)
  const [copied, setCopied] = useState('')
  const [ipEditKeyId, setIpEditKeyId] = useState<string | null>(null)
  const [newIp, setNewIp] = useState('')

  const refresh = () => {
    api.get<PartnersResponse>('/partners/')
      .then(d => { setData(d); setError('') })
      .catch(e => setError(e.message || 'Failed to load'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  const createPartner = async () => {
    if (!createData.name || !createData.slug) { setError('Name and slug required'); return }
    setSaving(true); setError('')
    try {
      await api.post('/partners/', createData)
      setShowCreate(false)
      setCreateData({ name: '', slug: '', website: '', contact_email: '', contact_phone: '', status: 'pending', commission_percent: '20', settlement_frequency: 'weekly' })
      refresh()
    } catch (e: any) { setError(e.message || 'Create failed') }
    setSaving(false)
  }

  const saveEdit = async () => {
    if (!selected) return
    setSaving(true); setError('')
    try {
      const updated = await api.patch<Partner>(`/partners/${selected.id}/`, editData)
      setSelected(updated)
      setEditing(false)
      refresh()
    } catch (e: any) { setError(e.message || 'Update failed') }
    setSaving(false)
  }

  const deletePartner = async (p: Partner) => {
    if (!confirm(`Delete partner "${p.name}"? This cannot be undone.`)) return
    try {
      await api.delete(`/partners/${p.id}/`)
      setSelected(null)
      refresh()
    } catch {}
  }

  const updateStatus = async (p: Partner, newStatus: string) => {
    try {
      const updated = await api.patch<Partner>(`/partners/${p.id}/`, { status: newStatus })
      setSelected(updated)
      refresh()
    } catch {}
  }

  // === API Keys ===
  const fetchKeys = (partnerId: string) => {
    setKeysLoading(true)
    api.get<{ keys: ApiKey[] }>(`/partners/${partnerId}/keys/`)
      .then(d => setApiKeys(d.keys))
      .catch(() => setApiKeys([]))
      .finally(() => setKeysLoading(false))
  }

  const createKey = async () => {
    if (!selected) return
    setSaving(true)
    try {
      const key = await api.post<ApiKey>(`/partners/${selected.id}/keys/`, { label: newKeyLabel || 'Default' })
      setApiKeys(prev => [key, ...prev])
      setRevealedSecrets(prev => new Set(prev).add(key.id))
      setNewKeyLabel('')
      setShowNewKeyForm(false)
      refresh()
    } catch {}
    setSaving(false)
  }

  const toggleKey = async (key: ApiKey) => {
    try {
      const updated = await api.patch<ApiKey>(`/partners/${selected!.id}/keys/${key.id}/`, { is_active: !key.is_active })
      setApiKeys(prev => prev.map(k => k.id === key.id ? updated : k))
      refresh()
    } catch {}
  }

  const deleteKey = async (key: ApiKey) => {
    if (!confirm(`Delete API key "${key.label}"?`)) return
    try {
      await api.delete(`/partners/${selected!.id}/keys/${key.id}/`)
      setApiKeys(prev => prev.filter(k => k.id !== key.id))
      refresh()
    } catch {}
  }

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text)
    setCopied(id)
    setTimeout(() => setCopied(''), 2000)
  }

  const toggleReveal = (id: string) => {
    setRevealedSecrets(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const addIp = async (key: ApiKey) => {
    const ip = newIp.trim()
    if (!ip || !selected) return
    const ipRegex = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/
    if (!ipRegex.test(ip)) { setError('Invalid IP format (e.g. 192.168.1.1 or 10.0.0.0/24)'); return }
    const updated = [...(key.ip_whitelist || []), ip]
    try {
      const res = await api.patch<ApiKey>(`/partners/${selected.id}/keys/${key.id}/`, { ip_whitelist: updated })
      setApiKeys(prev => prev.map(k => k.id === key.id ? res : k))
      setNewIp('')
      setError('')
    } catch {}
  }

  const removeIp = async (key: ApiKey, ip: string) => {
    if (!selected) return
    const updated = (key.ip_whitelist || []).filter(i => i !== ip)
    try {
      const res = await api.patch<ApiKey>(`/partners/${selected.id}/keys/${key.id}/`, { ip_whitelist: updated })
      setApiKeys(prev => prev.map(k => k.id === key.id ? res : k))
    } catch {}
  }

  const selectPartner = (p: Partner) => {
    setSelected(p)
    setEditing(false)
    setApiKeys([])
    setRevealedSecrets(new Set())
    fetchKeys(p.id)
  }

  const startEdit = () => {
    if (!selected) return
    setEditData({
      name: selected.name, slug: selected.slug, website: selected.website,
      contact_email: selected.contact_email, contact_phone: selected.contact_phone,
      debit_url: selected.debit_url, credit_url: selected.credit_url, rollback_url: selected.rollback_url,
      commission_percent: selected.commission_percent, settlement_frequency: selected.settlement_frequency,
      min_settlement_amount: selected.min_settlement_amount, notes: selected.notes,
    })
    setEditing(true)
  }

  return (
    <>
      <Topbar title="Partners" />
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">{data?.count ?? 0} operator{(data?.count ?? 0) !== 1 ? 's' : ''} registered</p>
          <Button onClick={() => setShowCreate(true)}>
            <Plus size={14} /> Add Partner
          </Button>
        </div>

        {error && <div className="text-sm text-danger bg-danger/10 rounded-lg px-4 py-2">{error}</div>}

        {/* Create Form */}
        {showCreate && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>New Partner</CardTitle>
                <button onClick={() => setShowCreate(false)} className="text-muted hover:text-white cursor-pointer"><X size={18} /></button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Name *</label>
                  <Input value={createData.name} onChange={e => setCreateData({ ...createData, name: e.target.value, slug: e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, '') })} placeholder="Elitebet" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Slug *</label>
                  <Input value={createData.slug} onChange={e => setCreateData({ ...createData, slug: e.target.value })} placeholder="elitebet" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Website</label>
                  <Input value={createData.website} onChange={e => setCreateData({ ...createData, website: e.target.value })} placeholder="https://elitebetgh.com" />
                </div>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Contact Email</label>
                  <Input value={createData.contact_email} onChange={e => setCreateData({ ...createData, contact_email: e.target.value })} placeholder="partner@example.com" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Contact Phone</label>
                  <Input value={createData.contact_phone} onChange={e => setCreateData({ ...createData, contact_phone: e.target.value })} placeholder="+233..." />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 mb-1.5">Commission (%)</label>
                  <Input value={createData.commission_percent} onChange={e => setCreateData({ ...createData, commission_percent: e.target.value })} />
                </div>
              </div>
              <div className="flex justify-end gap-2">
                <Button variant="ghost" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button onClick={createPartner} disabled={saving}>{saving ? 'Creating...' : 'Create Partner'}</Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Table */}
        <Card className="p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Operator</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Commission</TableHead>
                  <TableHead>Settlement</TableHead>
                  <TableHead>Sessions</TableHead>
                  <TableHead>Revenue</TableHead>
                  <TableHead>API Keys</TableHead>
                  <TableHead>Since</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(3)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(9)].map((_, j) => (
                        <TableCell key={j}><div className="h-4 bg-surface rounded animate-pulse w-16" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : !data || data.results.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={9} className="text-center py-12">
                      <Building2 size={36} className="mx-auto mb-3 text-muted opacity-40" />
                      <div className="text-sm text-muted">No partners registered yet</div>
                      <div className="text-xs text-muted mt-1">Click "Add Partner" to onboard an operator</div>
                    </TableCell>
                  </TableRow>
                ) : (
                  data.results.map(p => (
                    <TableRow key={p.id} className="cursor-pointer hover:bg-surface-hover/50" onClick={() => selectPartner(p)}>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                            {p.name.slice(0, 2).toUpperCase()}
                          </div>
                          <div>
                            <div className="text-white font-medium">{p.name}</div>
                            <div className="text-xs text-muted flex items-center gap-1"><Globe size={10} /> {p.website || p.slug}</div>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell><Badge variant={statusVariant(p.status)}>{p.status}</Badge></TableCell>
                      <TableCell className="font-medium">{p.commission_percent}%</TableCell>
                      <TableCell className="capitalize text-sm">{p.settlement_frequency}</TableCell>
                      <TableCell>{p.total_sessions.toLocaleString()}</TableCell>
                      <TableCell className="font-medium text-accent">{formatCurrency(p.total_revenue)}</TableCell>
                      <TableCell><div className="flex items-center gap-1 text-muted"><Key size={12} /> {p.api_keys_count}</div></TableCell>
                      <TableCell className="text-muted text-xs">{formatDateTime(p.created_at)}</TableCell>
                      <TableCell>
                        <div className="flex gap-1">
                          <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); selectPartner(p) }}><Eye size={14} /></Button>
                          <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); selectPartner(p); setTimeout(startEdit, 50) }}><Pencil size={14} /></Button>
                          <Button variant="ghost" size="sm" onClick={(e) => { e.stopPropagation(); deletePartner(p) }}><Trash2 size={14} className="text-danger" /></Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {/* Detail / Edit Panel */}
        {selected && (
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-bold">
                    {selected.name.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <CardTitle>{editing ? 'Edit Partner' : selected.name}</CardTitle>
                    <p className="text-xs text-muted">{selected.slug} &middot; Created {formatDateTime(selected.created_at)}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  {!editing && (
                    <>
                      <Badge variant={statusVariant(selected.status)} className="capitalize">{selected.status}</Badge>
                      <Button variant="ghost" size="sm" onClick={startEdit}><Pencil size={14} /> Edit</Button>
                    </>
                  )}
                  <button onClick={() => { setSelected(null); setEditing(false) }} className="text-muted hover:text-white cursor-pointer p-1"><X size={18} /></button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {editing ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Name</label>
                      <Input value={editData.name || ''} onChange={e => setEditData({ ...editData, name: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Slug</label>
                      <Input value={editData.slug || ''} onChange={e => setEditData({ ...editData, slug: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Website</label>
                      <Input value={editData.website || ''} onChange={e => setEditData({ ...editData, website: e.target.value })} />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Contact Email</label>
                      <Input value={editData.contact_email || ''} onChange={e => setEditData({ ...editData, contact_email: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Contact Phone</label>
                      <Input value={editData.contact_phone || ''} onChange={e => setEditData({ ...editData, contact_phone: e.target.value })} />
                    </div>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Commission (%)</label>
                      <Input value={editData.commission_percent || ''} onChange={e => setEditData({ ...editData, commission_percent: e.target.value })} />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Settlement Frequency</label>
                      <select value={editData.settlement_frequency || 'weekly'}
                        onChange={e => setEditData({ ...editData, settlement_frequency: e.target.value })}
                        className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white">
                        {(data?.settlement_choices || []).map(c => <option key={c.value} value={c.value}>{c.label}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 mb-1.5">Min Settlement Amount</label>
                      <Input value={editData.min_settlement_amount || ''} onChange={e => setEditData({ ...editData, min_settlement_amount: e.target.value })} />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-white mb-2">Wallet Integration URLs</label>
                    <div className="grid grid-cols-1 gap-3">
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Debit URL</label>
                        <Input value={editData.debit_url || ''} onChange={e => setEditData({ ...editData, debit_url: e.target.value })} placeholder="https://partner.com/api/wallet/debit" />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Credit URL</label>
                        <Input value={editData.credit_url || ''} onChange={e => setEditData({ ...editData, credit_url: e.target.value })} placeholder="https://partner.com/api/wallet/credit" />
                      </div>
                      <div>
                        <label className="block text-xs text-slate-400 mb-1">Rollback URL</label>
                        <Input value={editData.rollback_url || ''} onChange={e => setEditData({ ...editData, rollback_url: e.target.value })} placeholder="https://partner.com/api/wallet/rollback" />
                      </div>
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 mb-1.5">Notes</label>
                    <textarea value={editData.notes || ''} rows={2}
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2 text-sm text-white resize-none"
                      onChange={e => setEditData({ ...editData, notes: e.target.value })} />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setEditing(false)}>Cancel</Button>
                    <Button onClick={saveEdit} disabled={saving}><Save size={14} /> {saving ? 'Saving...' : 'Save Changes'}</Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Info Grid */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {[
                      { label: 'Commission', value: `${selected.commission_percent}%` },
                      { label: 'Settlement', value: selected.settlement_frequency },
                      { label: 'Min Settlement', value: `GHS ${selected.min_settlement_amount}` },
                      { label: 'Sessions', value: selected.total_sessions.toLocaleString() },
                      { label: 'API Keys', value: `${selected.api_keys_count} active` },
                      { label: 'Revenue', value: formatCurrency(selected.total_revenue) },
                      { label: 'Email', value: selected.contact_email || '—' },
                      { label: 'Phone', value: selected.contact_phone || '—' },
                    ].map(item => (
                      <div key={item.label}>
                        <div className="text-xs text-muted">{item.label}</div>
                        <div className="text-sm font-medium text-white capitalize">{item.value}</div>
                      </div>
                    ))}
                  </div>

                  {/* Wallet URLs */}
                  {(selected.debit_url || selected.credit_url || selected.rollback_url) && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 mb-2">Wallet Integration</h4>
                      <div className="space-y-1 text-xs">
                        {selected.debit_url && <div><span className="text-muted">Debit:</span> <span className="text-white font-mono">{selected.debit_url}</span></div>}
                        {selected.credit_url && <div><span className="text-muted">Credit:</span> <span className="text-white font-mono">{selected.credit_url}</span></div>}
                        {selected.rollback_url && <div><span className="text-muted">Rollback:</span> <span className="text-white font-mono">{selected.rollback_url}</span></div>}
                      </div>
                    </div>
                  )}

                  {selected.notes && (
                    <div>
                      <h4 className="text-xs font-semibold text-slate-400 mb-1">Notes</h4>
                      <p className="text-sm text-muted">{selected.notes}</p>
                    </div>
                  )}

                  {/* API Keys Section */}
                  <div className="pt-2 border-t border-border">
                    <div className="flex items-center justify-between mb-3">
                      <h4 className="text-sm font-semibold text-white flex items-center gap-2"><Key size={14} /> API Keys</h4>
                      <Button size="sm" onClick={() => setShowNewKeyForm(true)}><Plus size={12} /> Generate Key</Button>
                    </div>

                    {showNewKeyForm && (
                      <div className="flex items-center gap-2 mb-3 p-3 rounded-lg border border-border bg-surface">
                        <Input value={newKeyLabel} onChange={e => setNewKeyLabel(e.target.value)} placeholder="Key label (e.g. Production)" className="flex-1" />
                        <Button size="sm" onClick={createKey} disabled={saving}>{saving ? 'Creating...' : 'Create'}</Button>
                        <Button variant="ghost" size="sm" onClick={() => setShowNewKeyForm(false)}>Cancel</Button>
                      </div>
                    )}

                    {keysLoading ? (
                      <div className="text-sm text-muted py-4 text-center">Loading keys...</div>
                    ) : apiKeys.length === 0 ? (
                      <div className="text-sm text-muted py-4 text-center">No API keys yet. Generate one to get started.</div>
                    ) : (
                      <div className="space-y-3">
                        {apiKeys.map(k => (
                          <div key={k.id} className={`rounded-lg border p-3 space-y-2 ${
                            k.just_created ? 'border-success/50 bg-success/5' : k.is_active ? 'border-border' : 'border-danger/30 bg-danger/5'
                          }`}>
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-2">
                                <span className="text-sm font-medium text-white">{k.label}</span>
                                <Badge variant={k.is_active ? 'success' : 'danger'} className="text-[10px]">
                                  {k.is_active ? 'Active' : 'Revoked'}
                                </Badge>
                                {k.just_created && <Badge variant="info" className="text-[10px]">Just created — save these credentials</Badge>}
                              </div>
                              <div className="flex items-center gap-1">
                                <Button variant="ghost" size="sm" onClick={() => toggleKey(k)} title={k.is_active ? 'Revoke' : 'Reactivate'}>
                                  {k.is_active ? <ShieldOff size={13} className="text-danger" /> : <ShieldCheck size={13} className="text-success" />}
                                </Button>
                                <Button variant="ghost" size="sm" onClick={() => deleteKey(k)}><Trash2 size={13} className="text-danger" /></Button>
                              </div>
                            </div>

                            {/* API Key */}
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted w-16 shrink-0">API Key</span>
                              <code className="flex-1 text-xs font-mono text-white bg-surface px-2 py-1 rounded border border-border truncate">{k.api_key}</code>
                              <button onClick={() => copyToClipboard(k.api_key, `key-${k.id}`)} className="text-muted hover:text-white cursor-pointer p-1" title="Copy">
                                {copied === `key-${k.id}` ? <Check size={13} className="text-success" /> : <Copy size={13} />}
                              </button>
                            </div>

                            {/* API Secret */}
                            <div className="flex items-center gap-2">
                              <span className="text-xs text-muted w-16 shrink-0">Secret</span>
                              <code className="flex-1 text-xs font-mono text-white bg-surface px-2 py-1 rounded border border-border truncate">
                                {revealedSecrets.has(k.id) ? k.api_secret : k.api_secret_hint || '••••••••••••••••'}
                              </code>
                              <button onClick={() => toggleReveal(k.id)} className="text-muted hover:text-white cursor-pointer p-1" title={revealedSecrets.has(k.id) ? 'Hide' : 'Reveal'}>
                                {revealedSecrets.has(k.id) ? <EyeOff size={13} /> : <Eye size={13} />}
                              </button>
                              <button onClick={() => copyToClipboard(k.api_secret, `secret-${k.id}`)} className="text-muted hover:text-white cursor-pointer p-1" title="Copy">
                                {copied === `secret-${k.id}` ? <Check size={13} className="text-success" /> : <Copy size={13} />}
                              </button>
                            </div>

                            {/* IP Whitelist */}
                            <div className="pt-1">
                              <div className="flex items-center justify-between">
                                <button onClick={() => setIpEditKeyId(ipEditKeyId === k.id ? null : k.id)}
                                  className="flex items-center gap-1.5 text-xs text-muted hover:text-white cursor-pointer">
                                  <Shield size={12} />
                                  <span>IP Whitelist: {k.ip_whitelist?.length ? <span className="text-warning font-medium">{k.ip_whitelist.length} IP{k.ip_whitelist.length > 1 ? 's' : ''} enforced</span> : <span className="text-slate-500">Any (open)</span>}</span>
                                </button>
                              </div>

                              {ipEditKeyId === k.id && (
                                <div className="mt-2 p-2.5 rounded-lg border border-border bg-surface/50 space-y-2">
                                  {k.ip_whitelist?.length ? (
                                    <div className="flex flex-wrap gap-1.5">
                                      {k.ip_whitelist.map(ip => (
                                        <span key={ip} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md bg-primary/10 border border-primary/20 text-xs font-mono text-white">
                                          {ip}
                                          <button onClick={() => removeIp(k, ip)} className="text-muted hover:text-danger cursor-pointer" title="Remove">
                                            <X size={10} />
                                          </button>
                                        </span>
                                      ))}
                                    </div>
                                  ) : (
                                    <p className="text-xs text-muted">No IPs whitelisted — all IPs are allowed. Add IPs to restrict access.</p>
                                  )}
                                  <div className="flex items-center gap-2">
                                    <Input value={newIp} onChange={e => setNewIp(e.target.value)}
                                      onKeyDown={e => { if (e.key === 'Enter') addIp(k) }}
                                      placeholder="e.g. 203.0.113.50 or 10.0.0.0/24" className="flex-1 !py-1 !text-xs" />
                                    <Button size="sm" onClick={() => addIp(k)} className="!py-1 !px-3 !text-xs">Add IP</Button>
                                  </div>
                                </div>
                              )}
                            </div>

                            <div className="flex items-center gap-4 text-[10px] text-muted pt-1">
                              <span>Rate: {k.rate_limit_per_minute}/min</span>
                              <span>Created: {formatDateTime(k.created_at)}</span>
                              {k.last_used_at && <span>Last used: {formatDateTime(k.last_used_at)}</span>}
                              {k.revoked_at && <span className="text-danger">Revoked: {formatDateTime(k.revoked_at)}</span>}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Status Actions */}
                  <div className="flex items-center gap-2 pt-2 border-t border-border">
                    <span className="text-xs text-muted mr-2">Change status:</span>
                    {(data?.status_choices || []).map(c => (
                      <Button key={c.value} variant={selected.status === c.value ? 'primary' : 'ghost'} size="sm"
                        disabled={selected.status === c.value}
                        onClick={() => updateStatus(selected, c.value)}>
                        {selected.status === c.value && <Check size={12} />}
                        {c.label}
                      </Button>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
