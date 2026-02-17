import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { StatCard } from '@/components/ui/stat-card'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Wallet, ArrowDownRight, ArrowUpRight, TrendingUp, DollarSign, ChevronLeft, ChevronRight } from 'lucide-react'

interface FinanceStats {
  total_deposits: string
  total_withdrawals: string
  net_revenue: string
  pending_withdrawals: string
  pending_count: number
}

interface FinanceTx {
  id: string
  player_name: string
  type: string
  amount: string
  status: string
  provider: string
  created_at: string
}

interface FinanceResponse {
  stats: FinanceStats
  pending_withdrawals: FinanceTx[]
  recent: FinanceTx[]
}

export default function FinancePage() {
  const [data, setData] = useState<FinanceResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState<'overview' | 'pending'>('overview')

  useEffect(() => {
    api.get<FinanceResponse>('/finance/')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const approveWithdrawal = async (id: string) => {
    try {
      await api.post(`/finance/withdrawals/${id}/approve/`)
      api.get<FinanceResponse>('/finance/').then(setData)
    } catch {}
  }

  const rejectWithdrawal = async (id: string) => {
    try {
      await api.post(`/finance/withdrawals/${id}/reject/`)
      api.get<FinanceResponse>('/finance/').then(setData)
    } catch {}
  }

  if (loading) {
    return (
      <>
        <Topbar title="Finance" />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 rounded-xl border border-border bg-card animate-pulse" />
            ))}
          </div>
        </div>
      </>
    )
  }

  const s = data!.stats

  return (
    <>
      <Topbar title="Finance" />
      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total Deposits" value={formatCurrency(s.total_deposits)} icon={<ArrowDownRight size={20} />} changeType="up" />
          <StatCard title="Total Withdrawals" value={formatCurrency(s.total_withdrawals)} icon={<ArrowUpRight size={20} />} changeType="down" />
          <StatCard title="Net Revenue" value={formatCurrency(s.net_revenue)} icon={<TrendingUp size={20} />} changeType="up" />
          <StatCard
            title="Pending Withdrawals"
            value={formatCurrency(s.pending_withdrawals)}
            icon={<Wallet size={20} />}
            change={`${s.pending_count} awaiting approval`}
            changeType="neutral"
          />
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-border pb-0">
          {(['overview', 'pending'] as const).map(t => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors capitalize cursor-pointer ${
                tab === t ? 'border-primary text-primary' : 'border-transparent text-muted hover:text-white'
              }`}
            >
              {t === 'pending' ? `Pending (${s.pending_count})` : t}
            </button>
          ))}
        </div>

        {tab === 'overview' && (
          <Card className="p-0">
            <CardHeader className="p-4 pb-0">
              <CardTitle>Recent Financial Activity</CardTitle>
            </CardHeader>
            <CardContent className="p-0 mt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Type</TableHead>
                    <TableHead>Player</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data!.recent.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={6} className="text-center py-12">
                        <DollarSign size={36} className="mx-auto mb-3 text-muted opacity-40" />
                        <div className="text-sm text-muted">No financial activity yet</div>
                        <div className="text-xs text-muted mt-1">Deposits and withdrawals will appear here</div>
                      </TableCell>
                    </TableRow>
                  ) : (
                    data!.recent.map(tx => (
                      <TableRow key={tx.id}>
                        <TableCell>
                          <Badge variant={tx.type === 'deposit' ? 'success' : 'warning'} className="capitalize">{tx.type}</Badge>
                        </TableCell>
                        <TableCell className="text-white font-medium">{tx.player_name}</TableCell>
                        <TableCell className={`font-semibold ${tx.type === 'deposit' ? 'text-success' : 'text-warning'}`}>
                          {tx.type === 'deposit' ? '+' : '-'}{formatCurrency(tx.amount)}
                        </TableCell>
                        <TableCell className="capitalize">{tx.provider}</TableCell>
                        <TableCell>
                          <Badge variant={tx.status === 'completed' ? 'success' : tx.status === 'pending' ? 'warning' : 'danger'}>
                            {tx.status}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-muted text-xs">{formatDateTime(tx.created_at)}</TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}

        {tab === 'pending' && (
          <Card className="p-0">
            <CardHeader className="p-4 pb-0">
              <CardTitle>Pending Withdrawal Approvals</CardTitle>
            </CardHeader>
            <CardContent className="p-0 mt-4">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Player</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Requested</TableHead>
                    <TableHead>Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data!.pending_withdrawals.map(tx => (
                    <TableRow key={tx.id}>
                      <TableCell className="text-white font-medium">{tx.player_name}</TableCell>
                      <TableCell className="font-semibold text-warning">{formatCurrency(tx.amount)}</TableCell>
                      <TableCell className="capitalize">{tx.provider}</TableCell>
                      <TableCell className="text-muted text-xs">{formatDateTime(tx.created_at)}</TableCell>
                      <TableCell>
                        <div className="flex gap-2">
                          <Button variant="primary" size="sm" onClick={() => approveWithdrawal(tx.id)}>Approve</Button>
                          <Button variant="danger" size="sm" onClick={() => rejectWithdrawal(tx.id)}>Reject</Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {data!.pending_withdrawals.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-center text-muted py-8">No pending withdrawals</TableCell>
                    </TableRow>
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </div>
    </>
  )
}
