import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { StatCard } from '@/components/ui/stat-card'
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/card'
import { api } from '@/lib/api'
import { formatCurrency } from '@/lib/utils'
import { TrendingUp, Users, Gamepad2, Percent } from 'lucide-react'
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

interface AnalyticsData {
  summary: {
    total_ggr: string
    avg_session_value: string
    avg_flips_per_session: number
    house_edge_actual: string
    retention_7d: string
  }
  daily_revenue: { date: string; revenue: number; ggr: number }[]
  daily_players: { date: string; new_players: number; active_players: number }[]
  top_denominations: { denomination: string; count: number }[]
}

export default function AnalyticsPage() {
  const [data, setData] = useState<AnalyticsData | null>(null)
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('30d')

  useEffect(() => {
    api.get<AnalyticsData>('/analytics/', { period })
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [period])

  if (loading) {
    return (
      <>
        <Topbar title="Analytics" />
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

  const s = data!.summary

  return (
    <>
      <Topbar title="Analytics" />
      <div className="p-6 space-y-6">
        {/* Period selector */}
        <div className="flex gap-2">
          {['7d', '30d', '90d'].map(p => (
            <button
              key={p}
              onClick={() => { setPeriod(p); setLoading(true) }}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors cursor-pointer ${
                period === p ? 'bg-primary/15 text-primary' : 'bg-surface text-muted hover:text-white'
              }`}
            >
              {p === '7d' ? '7 Days' : p === '30d' ? '30 Days' : '90 Days'}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard title="Total GGR" value={formatCurrency(s.total_ggr)} icon={<TrendingUp size={20} />} />
          <StatCard title="Avg Session Value" value={formatCurrency(s.avg_session_value)} icon={<Gamepad2 size={20} />} />
          <StatCard title="Avg Flips/Session" value={s.avg_flips_per_session.toFixed(1)} icon={<Percent size={20} />} />
          <StatCard title="7-Day Retention" value={`${s.retention_7d}%`} icon={<Users size={20} />} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Revenue Chart */}
          <Card>
            <CardHeader><CardTitle>Revenue & GGR</CardTitle></CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={data!.daily_revenue}>
                    <defs>
                      <linearGradient id="colorRev" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00BFA6" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00BFA6" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="colorGGR" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#F5C842" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#F5C842" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} />
                    <YAxis stroke="#94A3B8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #334155', borderRadius: '8px', color: '#F1F5F9' }} />
                    <Area type="monotone" dataKey="revenue" stroke="#00BFA6" fill="url(#colorRev)" strokeWidth={2} />
                    <Area type="monotone" dataKey="ggr" stroke="#F5C842" fill="url(#colorGGR)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          {/* Player Activity Chart */}
          <Card>
            <CardHeader><CardTitle>Player Activity</CardTitle></CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data!.daily_players}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                    <XAxis dataKey="date" stroke="#94A3B8" fontSize={11} />
                    <YAxis stroke="#94A3B8" fontSize={11} />
                    <Tooltip contentStyle={{ backgroundColor: '#1E293B', border: '1px solid #334155', borderRadius: '8px', color: '#F1F5F9' }} />
                    <Bar dataKey="active_players" fill="#00BFA6" radius={[4, 4, 0, 0]} />
                    <Bar dataKey="new_players" fill="#F5C842" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </>
  )
}
