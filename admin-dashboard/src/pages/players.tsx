import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, Eye, Ban, CheckCircle, X, Wallet, Gamepad2, ArrowDownRight, ArrowUpRight, PlusCircle, MinusCircle } from 'lucide-react'

interface Player {
  id: string
  phone: string
  display_name: string
  balance: string
  total_sessions: number
  total_wagered: string
  is_active: boolean
  date_joined: string
  last_login: string
}

interface PlayerDetail {
  id: string
  phone: string
  display_name: string
  is_active: boolean
  date_joined: string
  last_login: string | null
  balance: string
  total_sessions: number
  total_wagered: string
  total_won: string
  total_deposited: string
  total_withdrawn: string
  recent_sessions: { id: string; stake: string; payout: string; status: string; flips: number; created_at: string }[]
  recent_deposits: { id: string; amount: string; status: string; reference: string; created_at: string }[]
  recent_withdrawals: { id: string; amount: string; status: string; reference: string; created_at: string }[]
}

interface PlayersResponse {
  results: Player[]
  count: number
  next: string | null
  previous: string | null
}

export default function PlayersPage() {
  const [data, setData] = useState<PlayersResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [detail, setDetail] = useState<PlayerDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)
  const [adjusting, setAdjusting] = useState(false)
  const [adjustAmount, setAdjustAmount] = useState('')
  const [adjustNote, setAdjustNote] = useState('')
  const [adjustType, setAdjustType] = useState<'admin_credit' | 'admin_debit'>('admin_credit')
  const [adjustMsg, setAdjustMsg] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  const fetchPlayers = (p = 1, q = '') => {
    setLoading(true)
    const params: Record<string, string> = { page: String(p) }
    if (q) params.search = q
    api.get<PlayersResponse>('/players/', params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchPlayers() }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchPlayers(1, search)
  }

  const toggleActive = async (player: Player) => {
    try {
      await api.patch(`/players/${player.id}/`, { is_active: !player.is_active })
      fetchPlayers(page, search)
    } catch {}
  }

  const viewPlayer = async (id: string) => {
    setDetailLoading(true)
    setDetail(null)
    setAdjustMsg(null)
    setAdjustAmount('')
    setAdjustNote('')
    setAdjusting(false)
    try {
      const d = await api.get<PlayerDetail>(`/players/${id}/`)
      setDetail(d)
    } catch {}
    setDetailLoading(false)
  }

  const doWalletAdjust = async () => {
    if (!detail || !adjustAmount) return
    setAdjustMsg(null)
    try {
      const res = await api.post<{ success: boolean; new_balance: string; error?: string }>(
        `/players/${detail.id}/wallet/adjust/`,
        { amount: adjustAmount, tx_type: adjustType, note: adjustNote }
      )
      setAdjustMsg({ type: 'success', text: `Done! New balance: GHS ${parseFloat(res.new_balance).toFixed(2)}` })
      setAdjustAmount('')
      setAdjustNote('')
      // Refresh detail
      const d = await api.get<PlayerDetail>(`/players/${detail.id}/`)
      setDetail(d)
    } catch (e: any) {
      setAdjustMsg({ type: 'error', text: e?.message || 'Failed to adjust wallet' })
    }
  }

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  return (
    <>
      <Topbar title="Players" />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <Input
                placeholder="Search by phone or name..."
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="pl-9 w-72"
              />
            </div>
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
          <span className="text-sm text-muted">{data?.count ?? 0} players total</span>
        </div>

        <Card className="p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead>Phone</TableHead>
                  <TableHead>Balance</TableHead>
                  <TableHead>Sessions</TableHead>
                  <TableHead>Total Wagered</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Joined</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(8)].map((_, j) => (
                        <TableCell key={j}><div className="h-4 bg-surface rounded animate-pulse w-20" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : !data?.results.length ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12">
                      <div className="text-muted">
                        <div className="text-lg mb-1">No players found</div>
                        <div className="text-sm">{search ? 'Try adjusting your search query' : 'Players will appear here once they sign up'}</div>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : data?.results.map(player => (
                  <TableRow key={player.id}>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <div className="w-8 h-8 rounded-full bg-primary/15 flex items-center justify-center text-primary text-xs font-bold">
                          {player.display_name?.[0]?.toUpperCase() || '?'}
                        </div>
                        <span className="font-medium text-white">{player.display_name || 'Anonymous'}</span>
                      </div>
                    </TableCell>
                    <TableCell>{player.phone}</TableCell>
                    <TableCell className="font-medium text-accent">{formatCurrency(player.balance)}</TableCell>
                    <TableCell>{player.total_sessions}</TableCell>
                    <TableCell>{formatCurrency(player.total_wagered)}</TableCell>
                    <TableCell>
                      <Badge variant={player.is_active ? 'success' : 'danger'}>
                        {player.is_active ? 'Active' : 'Suspended'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted text-xs">{formatDateTime(player.date_joined)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" title="View details" onClick={() => viewPlayer(player.id)}>
                          <Eye size={14} />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          title={player.is_active ? 'Suspend' : 'Activate'}
                          onClick={() => toggleActive(player)}
                        >
                          {player.is_active ? <Ban size={14} className="text-danger" /> : <CheckCircle size={14} className="text-success" />}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>

        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-muted">Page {page} of {totalPages}</span>
            <div className="flex items-center gap-2">
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => { setPage(p => p - 1); fetchPlayers(page - 1, search) }}>
                <ChevronLeft size={14} /> Previous
              </Button>
              <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => { setPage(p => p + 1); fetchPlayers(page + 1, search) }}>
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Player Detail Drawer */}
      {(detail || detailLoading) && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/50" onClick={() => setDetail(null)} />
          <div className="relative w-full max-w-lg bg-card border-l border-border overflow-y-auto">
            <div className="sticky top-0 bg-card border-b border-border p-4 flex items-center justify-between z-10">
              <h2 className="text-lg font-semibold text-white">Player Details</h2>
              <button onClick={() => setDetail(null)} className="text-muted hover:text-white cursor-pointer"><X size={20} /></button>
            </div>
            {detailLoading ? (
              <div className="p-6 space-y-4">{[...Array(4)].map((_, i) => <div key={i} className="h-16 bg-surface rounded-lg animate-pulse" />)}</div>
            ) : detail && (
              <div className="p-4 space-y-5">
                {/* Header */}
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-primary/15 flex items-center justify-center text-primary text-lg font-bold">
                    {detail.display_name?.[0]?.toUpperCase() || '?'}
                  </div>
                  <div>
                    <div className="text-white font-semibold">{detail.display_name}</div>
                    <div className="text-sm text-muted">{detail.phone}</div>
                  </div>
                  <Badge variant={detail.is_active ? 'success' : 'danger'} className="ml-auto">
                    {detail.is_active ? 'Active' : 'Suspended'}
                  </Badge>
                </div>

                {/* Stats Grid */}
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: 'Balance', value: formatCurrency(detail.balance), icon: Wallet, color: 'text-accent' },
                    { label: 'Sessions', value: detail.total_sessions, icon: Gamepad2, color: 'text-primary' },
                    { label: 'Wagered', value: formatCurrency(detail.total_wagered), icon: ArrowUpRight, color: 'text-warning' },
                    { label: 'Won', value: formatCurrency(detail.total_won), icon: ArrowDownRight, color: 'text-success' },
                    { label: 'Deposited', value: formatCurrency(detail.total_deposited), icon: ArrowDownRight, color: 'text-success' },
                    { label: 'Withdrawn', value: formatCurrency(detail.total_withdrawn), icon: ArrowUpRight, color: 'text-warning' },
                  ].map(s => (
                    <div key={s.label} className="p-3 rounded-lg bg-surface border border-border">
                      <div className="flex items-center gap-1.5 text-xs text-muted mb-1"><s.icon size={12} /> {s.label}</div>
                      <div className={`text-sm font-semibold ${s.color}`}>{s.value}</div>
                    </div>
                  ))}
                </div>

                {/* Meta */}
                <div className="text-xs text-muted space-y-1">
                  <div>Joined: {formatDateTime(detail.date_joined)}</div>
                  <div>Last login: {detail.last_login ? formatDateTime(detail.last_login) : 'Never'}</div>
                </div>

                {/* Recent Sessions */}
                {detail.recent_sessions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-2">Recent Sessions</h3>
                    <div className="space-y-1.5">
                      {detail.recent_sessions.map(s => (
                        <div key={s.id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface border border-border text-xs">
                          <div>
                            <span className="text-white font-medium">Stake: {formatCurrency(s.stake)}</span>
                            <span className="text-muted ml-2">{s.flips} flips</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className={parseFloat(s.payout) > 0 ? 'text-success font-medium' : 'text-slate-400'}>
                              {formatCurrency(s.payout)}
                            </span>
                            <Badge variant={s.status === 'cashed_out' ? 'success' : s.status === 'lost' ? 'danger' : 'info'}>
                              {s.status.replace('_', ' ')}
                            </Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent Deposits */}
                {detail.recent_deposits.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-2">Recent Deposits</h3>
                    <div className="space-y-1.5">
                      {detail.recent_deposits.map(d => (
                        <div key={d.id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface border border-border text-xs">
                          <span className="text-success font-medium">+{formatCurrency(d.amount)}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-muted font-mono">{d.reference?.slice(0, 12) || '—'}</span>
                            <Badge variant={d.status === 'completed' ? 'success' : d.status === 'pending' ? 'warning' : 'danger'}>{d.status}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Recent Withdrawals */}
                {detail.recent_withdrawals.length > 0 && (
                  <div>
                    <h3 className="text-sm font-semibold text-white mb-2">Recent Withdrawals</h3>
                    <div className="space-y-1.5">
                      {detail.recent_withdrawals.map(w => (
                        <div key={w.id} className="flex items-center justify-between p-2.5 rounded-lg bg-surface border border-border text-xs">
                          <span className="text-warning font-medium">-{formatCurrency(w.amount)}</span>
                          <div className="flex items-center gap-2">
                            <span className="text-muted font-mono">{w.reference?.slice(0, 12) || '—'}</span>
                            <Badge variant={w.status === 'completed' ? 'success' : w.status === 'pending' ? 'warning' : 'danger'}>{w.status}</Badge>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Admin Wallet Adjustment */}
                <div className="border border-border rounded-lg p-4 bg-surface">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-sm font-semibold text-white flex items-center gap-1.5">
                      <Wallet size={14} className="text-primary" /> Wallet Adjustment
                    </h3>
                    <Button variant="ghost" size="sm" onClick={() => setAdjusting(v => !v)}>
                      {adjusting ? 'Cancel' : 'Adjust'}
                    </Button>
                  </div>
                  {adjusting && (
                    <div className="space-y-3">
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          variant={adjustType === 'admin_credit' ? 'primary' : 'outline'}
                          className="flex-1 gap-1"
                          onClick={() => setAdjustType('admin_credit')}
                        >
                          <PlusCircle size={13} /> Credit
                        </Button>
                        <Button
                          size="sm"
                          variant={adjustType === 'admin_debit' ? 'danger' : 'outline'}
                          className="flex-1 gap-1"
                          onClick={() => setAdjustType('admin_debit')}
                        >
                          <MinusCircle size={13} /> Debit
                        </Button>
                      </div>
                      <Input
                        type="number"
                        placeholder="Amount (GHS)"
                        value={adjustAmount}
                        onChange={e => setAdjustAmount(e.target.value)}
                        min="0.01"
                        step="0.01"
                      />
                      <Input
                        placeholder="Note / reason (optional)"
                        value={adjustNote}
                        onChange={e => setAdjustNote(e.target.value)}
                      />
                      <Button
                        className="w-full"
                        variant={adjustType === 'admin_credit' ? 'primary' : 'danger'}
                        disabled={!adjustAmount || parseFloat(adjustAmount) <= 0}
                        onClick={doWalletAdjust}
                      >
                        {adjustType === 'admin_credit' ? `Credit GHS ${adjustAmount || '0'}` : `Debit GHS ${adjustAmount || '0'}`}
                      </Button>
                      {adjustMsg && (
                        <p className={`text-xs ${adjustMsg.type === 'success' ? 'text-success' : 'text-danger'}`}>
                          {adjustMsg.text}
                        </p>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  )
}
