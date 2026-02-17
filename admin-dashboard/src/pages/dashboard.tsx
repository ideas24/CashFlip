import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { StatCard } from '@/components/ui/stat-card'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime, timeAgo } from '@/lib/utils'
import { Users, Gamepad2, Wallet, TrendingUp, ArrowUpRight, ArrowDownRight } from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface DashboardStats {
  total_players: number
  active_today: number
  total_sessions_today: number
  total_revenue_today: string
  total_deposits_today: string
  total_withdrawals_today: string
  ggr_today: string
  player_change_pct: string
  revenue_change_pct: string
  revenue_chart: { date: string; revenue: number; players: number }[]
  recent_sessions: { id: string; player_name: string; stake: string; result: string; created_at: string }[]
  recent_transactions: { id: string; player_name: string; type: string; amount: string; status: string; created_at: string }[]
}

export default function DashboardPage() {
  const [stats, setStats] = useState<DashboardStats | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<DashboardStats>('/dashboard/')
      .then(setStats)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <>
        <Topbar title="Dashboard" />
        <div className="p-6">
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {[...Array(4)].map((_, i) => (
              <div key={i} className="h-32 rounded-xl border border-border bg-card animate-pulse" />
            ))}
          </div>
        </div>
      </>
    )
  }

  const s = stats!

  return (
    <>
      <Topbar title="Dashboard" />
      <div className="p-6 space-y-6">
        {/* Stat cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Players"
            value={s.total_players.toLocaleString()}
            icon={<Users size={20} />}
            change={`${s.player_change_pct}% vs yesterday`}
            changeType={parseFloat(s.player_change_pct) >= 0 ? 'up' : 'down'}
          />
          <StatCard
            title="Sessions Today"
            value={s.total_sessions_today.toLocaleString()}
            icon={<Gamepad2 size={20} />}
            change={`${s.active_today} active players`}
            changeType="neutral"
          />
          <StatCard
            title="Revenue Today"
            value={formatCurrency(s.total_revenue_today)}
            icon={<TrendingUp size={20} />}
            change={`${s.revenue_change_pct}% vs yesterday`}
            changeType={parseFloat(s.revenue_change_pct) >= 0 ? 'up' : 'down'}
          />
          <StatCard
            title="GGR Today"
            value={formatCurrency(s.ggr_today)}
            icon={<Wallet size={20} />}
            change={`Dep: ${formatCurrency(s.total_deposits_today)}`}
            changeType="neutral"
          />
        </div>

        {/* Chart + Recent Activity */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Revenue Chart */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>Revenue (Last 30 Days)</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-72">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={s.revenue_chart}>
                    <defs>
                      <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00BFA6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00BFA6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" stroke="#94A3B8" fontSize={12} />
                    <YAxis stroke="#94A3B8" fontSize={12} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #334155', borderRadius: '8px', color: '#F1F5F9' }}
                      labelStyle={{ color: '#94A3B8' }}
                    />
                    <Area type="monotone" dataKey="revenue" stroke="#00BFA6" fill="url(#colorRevenue)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Recent Sessions */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Sessions</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {s.recent_sessions.map(session => (
                  <div key={session.id} className="flex items-center justify-between py-2 border-b border-border/50 last:border-0">
                    <div>
                      <div className="text-sm text-white font-medium">{session.player_name}</div>
                      <div className="text-xs text-muted">{timeAgo(session.created_at)}</div>
                    </div>
                    <div className="text-right">
                      <div className="text-sm font-medium text-white">{formatCurrency(session.stake)}</div>
                      <Badge variant={session.result === 'won' ? 'success' : session.result === 'lost' ? 'danger' : 'info'}>
                        {session.result}
                      </Badge>
                    </div>
                  </div>
                ))}
                {s.recent_sessions.length === 0 && (
                  <p className="text-sm text-muted text-center py-4">No sessions today</p>
                )}
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Recent Transactions */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {s.recent_transactions.map(tx => (
                <div key={tx.id} className="flex items-center justify-between py-2.5 border-b border-border/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tx.type === 'deposit' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
                      {tx.type === 'deposit' ? <ArrowDownRight size={16} /> : <ArrowUpRight size={16} />}
                    </div>
                    <div>
                      <div className="text-sm text-white font-medium">{tx.player_name}</div>
                      <div className="text-xs text-muted capitalize">{tx.type} &middot; {timeAgo(tx.created_at)}</div>
                    </div>
                  </div>
                  <div className="text-right">
                    <div className={`text-sm font-medium ${tx.type === 'deposit' ? 'text-success' : 'text-warning'}`}>
                      {tx.type === 'deposit' ? '+' : '-'}{formatCurrency(tx.amount)}
                    </div>
                    <Badge variant={tx.status === 'completed' ? 'success' : tx.status === 'pending' ? 'warning' : 'danger'}>
                      {tx.status}
                    </Badge>
                  </div>
                </div>
              ))}
              {s.recent_transactions.length === 0 && (
                <p className="text-sm text-muted text-center py-4">No transactions today</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
