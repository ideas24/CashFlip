import { useState, useEffect, useCallback } from 'react'
import { api } from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import {
  Ticket, Plus, Copy, Search, Ban, Package, CheckCircle2,
  Clock, XCircle, AlertCircle, ChevronLeft, ChevronRight,
} from 'lucide-react'

interface VoucherItem {
  id: string; code: string; amount: string; currency_code: string; status: string
  batch_id: string | null; batch_name: string | null
  created_by: string | null; redeemed_by: string | null
  redeemed_at: string | null; expires_at: string | null; created_at: string; notes: string
}
interface BatchItem {
  id: string; name: string; amount: string; currency_code: string; quantity: number
  total_vouchers: number; redeemed: number; active: number
  created_by: string | null; expires_at: string | null; created_at: string; notes: string
}
interface Stats {
  total: number; active: number; redeemed: number; disabled: number; expired: number
  total_redeemed_value: string
}

const PRESET_AMOUNTS = [1, 2, 5, 10, 20, 50, 100]

export default function VouchersPage() {
  const [tab, setTab] = useState<'vouchers' | 'batches' | 'create'>('vouchers')
  const [stats, setStats] = useState<Stats | null>(null)
  const [vouchers, setVouchers] = useState<VoucherItem[]>([])
  const [batches, setBatches] = useState<BatchItem[]>([])
  const [vTotal, setVTotal] = useState(0)
  const [vPage, setVPage] = useState(1)
  const [vFilter, setVFilter] = useState('')
  const [vSearch, setVSearch] = useState('')
  const [loading, setLoading] = useState(false)

  // Create form
  const [createMode, setCreateMode] = useState<'single' | 'batch'>('batch')
  const [formAmount, setFormAmount] = useState('5')
  const [formQty, setFormQty] = useState('10')
  const [formName, setFormName] = useState('')
  const [formExpiry, setFormExpiry] = useState('')
  const [formNotes, setFormNotes] = useState('')
  const [creating, setCreating] = useState(false)
  const [createdCodes, setCreatedCodes] = useState<string[]>([])

  const loadStats = useCallback(async () => {
    try { setStats(await api.get('/vouchers/stats/')) } catch {}
  }, [])

  const loadVouchers = useCallback(async () => {
    setLoading(true)
    try {
      const params: Record<string, string> = { page: String(vPage), per_page: '30' }
      if (vFilter) params.status = vFilter
      if (vSearch) params.search = vSearch
      const res = await api.get<{ vouchers: VoucherItem[]; total: number }>('/vouchers/list/', params)
      setVouchers(res.vouchers)
      setVTotal(res.total)
    } catch {}
    setLoading(false)
  }, [vPage, vFilter, vSearch])

  const loadBatches = useCallback(async () => {
    try {
      const res = await api.get<{ batches: BatchItem[] }>('/vouchers/batches/')
      setBatches(res.batches)
    } catch {}
  }, [])

  useEffect(() => { loadStats() }, [loadStats])
  useEffect(() => { if (tab === 'vouchers') loadVouchers() }, [tab, loadVouchers])
  useEffect(() => { if (tab === 'batches') loadBatches() }, [tab, loadBatches])

  const copyCode = (code: string) => {
    navigator.clipboard.writeText(code)
  }

  const copyAllCodes = () => {
    navigator.clipboard.writeText(createdCodes.join('\n'))
  }

  const disableVoucher = async (id: string) => {
    if (!confirm('Disable this voucher?')) return
    try {
      await api.post(`/vouchers/${id}/disable/`)
      loadVouchers()
      loadStats()
    } catch {}
  }

  const handleCreate = async () => {
    setCreating(true)
    setCreatedCodes([])
    try {
      if (createMode === 'single') {
        const res = await api.post<{ code: string }>('/vouchers/create/', {
          amount: formAmount, currency_code: 'GHS', expires_at: formExpiry || null, notes: formNotes,
        })
        setCreatedCodes([res.code])
      } else {
        const res = await api.post<{ codes: string[] }>('/vouchers/batches/create/', {
          name: formName || `Batch ${formAmount} GHS`,
          amount: formAmount, quantity: parseInt(formQty) || 10,
          currency_code: 'GHS', expires_at: formExpiry || null, notes: formNotes,
        })
        setCreatedCodes(res.codes)
      }
      loadStats()
    } catch (e: any) {
      alert(e.message || 'Failed to create')
    }
    setCreating(false)
  }

  const statusBadge = (s: string) => {
    const map: Record<string, string> = {
      active: 'bg-emerald-500/15 text-emerald-400',
      redeemed: 'bg-blue-500/15 text-blue-400',
      disabled: 'bg-red-500/15 text-red-400',
      expired: 'bg-yellow-500/15 text-yellow-400',
    }
    return <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium ${map[s] || 'bg-zinc-700 text-zinc-300'}`}>{s}</span>
  }

  const fmtDate = (d: string | null) => d ? new Date(d).toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—'

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2"><Ticket size={24} /> Voucher Management</h1>
          <p className="text-sm text-muted mt-1">Create, manage, and track voucher codes</p>
        </div>
      </div>

      {/* Stats */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
          {[
            { label: 'Total', value: stats.total, icon: Ticket, color: 'text-white' },
            { label: 'Active', value: stats.active, icon: CheckCircle2, color: 'text-emerald-400' },
            { label: 'Redeemed', value: stats.redeemed, icon: Package, color: 'text-blue-400' },
            { label: 'Disabled', value: stats.disabled, icon: XCircle, color: 'text-red-400' },
            { label: 'Redeemed Value', value: `GHS ${parseFloat(stats.total_redeemed_value).toFixed(0)}`, icon: AlertCircle, color: 'text-amber-400' },
          ].map(s => (
            <Card key={s.label}>
              <CardContent className="p-3">
                <div className="flex items-center gap-2">
                  <s.icon size={16} className={s.color} />
                  <span className="text-xs text-muted">{s.label}</span>
                </div>
                <div className={`text-lg font-bold mt-1 ${s.color}`}>{s.value}</div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-border pb-2">
        {(['vouchers', 'batches', 'create'] as const).map(t => (
          <button key={t} onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-t-lg text-sm font-medium transition-colors cursor-pointer ${
              tab === t ? 'bg-primary/15 text-primary border-b-2 border-primary' : 'text-slate-400 hover:text-white'
            }`}>
            {t === 'vouchers' ? 'All Vouchers' : t === 'batches' ? 'Batches' : '+ Create'}
          </button>
        ))}
      </div>

      {/* TAB: All Vouchers */}
      {tab === 'vouchers' && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3 flex-wrap">
              <div className="relative flex-1 min-w-[200px]">
                <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
                <Input placeholder="Search code..." className="pl-9 text-sm" value={vSearch}
                  onChange={e => { setVSearch(e.target.value); setVPage(1) }} />
              </div>
              <select value={vFilter} onChange={e => { setVFilter(e.target.value); setVPage(1) }}
                className="rounded-lg border border-border bg-surface px-3 py-2 text-sm text-white">
                <option value="">All statuses</option>
                <option value="active">Active</option>
                <option value="redeemed">Redeemed</option>
                <option value="disabled">Disabled</option>
                <option value="expired">Expired</option>
              </select>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? <div className="text-center py-8 text-muted animate-pulse">Loading...</div> : (
              <>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-muted">
                        <th className="pb-2 pr-3">Code</th>
                        <th className="pb-2 pr-3">Amount</th>
                        <th className="pb-2 pr-3">Status</th>
                        <th className="pb-2 pr-3">Batch</th>
                        <th className="pb-2 pr-3">Redeemed By</th>
                        <th className="pb-2 pr-3">Created</th>
                        <th className="pb-2">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {vouchers.map(v => (
                        <tr key={v.id} className="border-b border-border/50 hover:bg-surface-hover/30">
                          <td className="py-2 pr-3">
                            <div className="flex items-center gap-1">
                              <code className="text-xs font-mono text-white bg-zinc-800 px-2 py-0.5 rounded">{v.code}</code>
                              <button onClick={() => copyCode(v.code)} className="text-muted hover:text-white cursor-pointer">
                                <Copy size={12} />
                              </button>
                            </div>
                          </td>
                          <td className="py-2 pr-3 text-white font-medium">{v.currency_code} {v.amount}</td>
                          <td className="py-2 pr-3">{statusBadge(v.status)}</td>
                          <td className="py-2 pr-3 text-muted text-xs">{v.batch_name || '—'}</td>
                          <td className="py-2 pr-3 text-muted text-xs">{v.redeemed_by || '—'}</td>
                          <td className="py-2 pr-3 text-muted text-xs">{fmtDate(v.created_at)}</td>
                          <td className="py-2">
                            {v.status === 'active' && (
                              <button onClick={() => disableVoucher(v.id)}
                                className="text-red-400 hover:text-red-300 text-xs flex items-center gap-1 cursor-pointer">
                                <Ban size={12} /> Disable
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                      {vouchers.length === 0 && (
                        <tr><td colSpan={7} className="text-center py-8 text-muted">No vouchers found</td></tr>
                      )}
                    </tbody>
                  </table>
                </div>
                {/* Pagination */}
                <div className="flex items-center justify-between mt-4">
                  <span className="text-xs text-muted">{vTotal} voucher{vTotal !== 1 ? 's' : ''}</span>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" disabled={vPage <= 1} onClick={() => setVPage(p => p - 1)}>
                      <ChevronLeft size={14} />
                    </Button>
                    <span className="text-sm text-muted">Page {vPage}</span>
                    <Button size="sm" variant="outline" disabled={vPage * 30 >= vTotal} onClick={() => setVPage(p => p + 1)}>
                      <ChevronRight size={14} />
                    </Button>
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      )}

      {/* TAB: Batches */}
      {tab === 'batches' && (
        <Card>
          <CardHeader>
            <CardTitle>Voucher Batches</CardTitle>
            <CardDescription>Groups of vouchers created together</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted">
                    <th className="pb-2 pr-3">Name</th>
                    <th className="pb-2 pr-3">Amount</th>
                    <th className="pb-2 pr-3">Total</th>
                    <th className="pb-2 pr-3">Active</th>
                    <th className="pb-2 pr-3">Redeemed</th>
                    <th className="pb-2 pr-3">Expires</th>
                    <th className="pb-2 pr-3">Created</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map(b => (
                    <tr key={b.id} className="border-b border-border/50 hover:bg-surface-hover/30 cursor-pointer"
                      onClick={() => { setVFilter(''); setVSearch(''); setTab('vouchers') }}>
                      <td className="py-2 pr-3 text-white font-medium">{b.name}</td>
                      <td className="py-2 pr-3 text-emerald-400">{b.currency_code} {b.amount}</td>
                      <td className="py-2 pr-3 text-white">{b.total_vouchers}</td>
                      <td className="py-2 pr-3 text-emerald-400">{b.active}</td>
                      <td className="py-2 pr-3 text-blue-400">{b.redeemed}</td>
                      <td className="py-2 pr-3 text-muted text-xs">{b.expires_at ? fmtDate(b.expires_at) : 'Never'}</td>
                      <td className="py-2 pr-3 text-muted text-xs">{fmtDate(b.created_at)}</td>
                    </tr>
                  ))}
                  {batches.length === 0 && (
                    <tr><td colSpan={7} className="text-center py-8 text-muted">No batches yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}

      {/* TAB: Create */}
      {tab === 'create' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Create Vouchers</CardTitle>
              <CardDescription>Generate single vouchers or batches</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Mode toggle */}
              <div className="flex gap-2">
                {(['single', 'batch'] as const).map(m => (
                  <button key={m} onClick={() => setCreateMode(m)}
                    className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                      createMode === m ? 'bg-primary/15 text-primary' : 'bg-zinc-800 text-slate-400 hover:text-white'
                    }`}>
                    {m === 'single' ? 'Single Voucher' : 'Batch'}
                  </button>
                ))}
              </div>

              {/* Amount presets */}
              <div>
                <label className="block text-xs text-slate-400 mb-2 font-medium">Amount (GHS)</label>
                <div className="flex flex-wrap gap-2 mb-2">
                  {PRESET_AMOUNTS.map(a => (
                    <button key={a} onClick={() => setFormAmount(String(a))}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
                        formAmount === String(a)
                          ? 'bg-emerald-600 border-emerald-500 text-white'
                          : 'bg-zinc-800 border-border text-slate-400 hover:text-white'
                      }`}>
                      GHS {a}
                    </button>
                  ))}
                </div>
                <Input type="number" min="0.50" step="0.50" value={formAmount}
                  onChange={e => setFormAmount(e.target.value)} placeholder="Custom amount" />
              </div>

              {/* Batch-specific fields */}
              {createMode === 'batch' && (
                <>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1 font-medium">Batch Name</label>
                    <Input value={formName} onChange={e => setFormName(e.target.value)}
                      placeholder={`e.g. Launch Promo ${formAmount} GHS`} />
                  </div>
                  <div>
                    <label className="block text-xs text-slate-400 mb-1 font-medium">Quantity</label>
                    <div className="flex gap-2 mb-2">
                      {[5, 10, 25, 50, 100].map(q => (
                        <button key={q} onClick={() => setFormQty(String(q))}
                          className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors cursor-pointer ${
                            formQty === String(q)
                              ? 'bg-blue-600 border-blue-500 text-white'
                              : 'bg-zinc-800 border-border text-slate-400 hover:text-white'
                          }`}>
                          {q}
                        </button>
                      ))}
                    </div>
                    <Input type="number" min="1" max="1000" value={formQty}
                      onChange={e => setFormQty(e.target.value)} />
                  </div>
                </>
              )}

              {/* Expiry */}
              <div>
                <label className="block text-xs text-slate-400 mb-1 font-medium">Expiry (optional)</label>
                <Input type="datetime-local" value={formExpiry} onChange={e => setFormExpiry(e.target.value)} />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-xs text-slate-400 mb-1 font-medium">Notes (optional)</label>
                <Input value={formNotes} onChange={e => setFormNotes(e.target.value)} placeholder="Internal notes..." />
              </div>

              <Button className="w-full" onClick={handleCreate} disabled={creating}>
                <Plus size={16} className="mr-2" />
                {creating ? 'Creating...' : createMode === 'single' ? 'Create Voucher' : `Create ${formQty} Vouchers`}
              </Button>

              {createMode === 'batch' && (
                <p className="text-xs text-muted text-center">
                  Total value: GHS {(parseFloat(formAmount || '0') * parseInt(formQty || '0')).toFixed(2)}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Created codes output */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>Generated Codes</CardTitle>
                {createdCodes.length > 0 && (
                  <Button size="sm" variant="outline" onClick={copyAllCodes}>
                    <Copy size={14} className="mr-1" /> Copy All
                  </Button>
                )}
              </div>
            </CardHeader>
            <CardContent>
              {createdCodes.length === 0 ? (
                <div className="text-center py-12 text-muted">
                  <Ticket size={40} className="mx-auto mb-3 opacity-30" />
                  <p>Generated codes will appear here</p>
                </div>
              ) : (
                <div className="max-h-[400px] overflow-y-auto space-y-1">
                  {createdCodes.map((code, i) => (
                    <div key={i} className="flex items-center justify-between px-3 py-2 rounded-lg bg-zinc-800/50 hover:bg-zinc-800">
                      <code className="text-sm font-mono text-emerald-400">{code}</code>
                      <button onClick={() => copyCode(code)} className="text-muted hover:text-white cursor-pointer">
                        <Copy size={14} />
                      </button>
                    </div>
                  ))}
                  <p className="text-xs text-muted text-center mt-3">{createdCodes.length} code{createdCodes.length !== 1 ? 's' : ''} generated</p>
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
