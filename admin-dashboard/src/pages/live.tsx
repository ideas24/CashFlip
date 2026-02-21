import { useEffect, useState, useRef } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { api } from '@/lib/api'
import { formatCurrency, timeAgo } from '@/lib/utils'
import { Activity, Users, Zap, TrendingUp, ArrowDownRight, ArrowUpRight, Circle, Coins } from 'lucide-react'

const POLL_INTERVAL = 4000 // 4 seconds

interface LivePlayer {
  session_id: string
  player_id: string
  player_name: string
  stake: string
  balance: string
  flips: number
  currency: string
  last_flip_at: string
  started_at: string
}

interface FlipEvent {
  id: string | number
  player_name: string
  value: string
  is_zero: boolean
  flip_number: number
  session_id: string
  currency: string
  timestamp: string
}

interface MoneyEvent {
  type: 'deposit' | 'withdrawal'
  player_name: string
  amount: string
  status: string
  timestamp: string
}

interface TodayStats {
  sessions: number
  flips: number
  total_staked: string
  total_paid_out: string
  ggr: string
}

interface LiveData {
  timestamp: string
  active_sessions: number
  live_players: LivePlayer[]
  flip_feed: FlipEvent[]
  money_feed: MoneyEvent[]
  today: TodayStats
}

export default function LiveActivityPage() {
  const [data, setData] = useState<LiveData | null>(null)
  const [connected, setConnected] = useState(false)
  const [error, setError] = useState('')
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const [pulseKey, setPulseKey] = useState(0)

  const fetchLive = async () => {
    try {
      const d = await api.get<LiveData>('/live/')
      setData(d)
      setConnected(true)
      setError('')
      setPulseKey(k => k + 1)
    } catch (e: any) {
      setError(e.message || 'Connection lost')
      setConnected(false)
    }
  }

  useEffect(() => {
    fetchLive()
    intervalRef.current = setInterval(fetchLive, POLL_INTERVAL)
    return () => { if (intervalRef.current) clearInterval(intervalRef.current) }
  }, [])

  const d = data

  return (
    <>
      <Topbar title="Live Activity" />
      <div className="p-6 space-y-5">
        {/* Connection status bar */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Circle
              size={10}
              className={connected ? 'fill-green-500 text-green-500 animate-pulse' : 'fill-red-500 text-red-500'}
            />
            <span className="text-xs text-muted">
              {connected ? `Live — polling every ${POLL_INTERVAL / 1000}s` : error || 'Disconnected'}
            </span>
          </div>
          {d && (
            <span className="text-xs text-muted">
              Last update: {new Date(d.timestamp).toLocaleTimeString()}
            </span>
          )}
        </div>

        {/* Quick stat cards */}
        {d && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <Card className="border-primary/30">
              <CardContent className="py-3 px-4 text-center">
                <div className="text-3xl font-bold text-primary" key={`as-${pulseKey}`}>
                  {d.active_sessions}
                </div>
                <div className="text-[10px] text-muted mt-0.5 flex items-center justify-center gap-1">
                  <Activity size={10} /> Active Sessions
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-3 px-4 text-center">
                <div className="text-3xl font-bold text-white">{d.live_players.length}</div>
                <div className="text-[10px] text-muted mt-0.5 flex items-center justify-center gap-1">
                  <Users size={10} /> Live Players
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-3 px-4 text-center">
                <div className="text-2xl font-bold text-white">{d.today.sessions.toLocaleString()}</div>
                <div className="text-[10px] text-muted mt-0.5">Sessions Today</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="py-3 px-4 text-center">
                <div className="text-2xl font-bold text-white">{d.today.flips.toLocaleString()}</div>
                <div className="text-[10px] text-muted mt-0.5 flex items-center justify-center gap-1">
                  <Zap size={10} /> Flips Today
                </div>
              </CardContent>
            </Card>
            <Card className="border-success/30">
              <CardContent className="py-3 px-4 text-center">
                <div className="text-2xl font-bold text-success">{formatCurrency(d.today.ggr)}</div>
                <div className="text-[10px] text-muted mt-0.5 flex items-center justify-center gap-1">
                  <TrendingUp size={10} /> GGR Today
                </div>
              </CardContent>
            </Card>
          </div>
        )}

        {/* Main content: 3-column layout */}
        {d && (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

            {/* Live Players */}
            <Card className="lg:col-span-1">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Users size={14} className="text-primary" /> Live Players
                  <Badge variant="info" className="ml-auto text-[10px]">{d.live_players.length}</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-[420px] overflow-y-auto">
                {d.live_players.length === 0 ? (
                  <p className="text-xs text-muted text-center py-8">No active players right now</p>
                ) : (
                  <div className="space-y-2">
                    {d.live_players.map(p => (
                      <div key={p.session_id} className="flex items-center justify-between py-2 px-2 rounded-lg bg-card/50 border border-border/30">
                        <div>
                          <div className="text-sm font-medium text-white">{p.player_name}</div>
                          <div className="text-[10px] text-muted">
                            Stake: {p.currency}{p.stake} · {p.flips} flips · {timeAgo(p.started_at)}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-bold text-primary">{p.currency}{parseFloat(p.balance).toFixed(2)}</div>
                          <div className="text-[10px] text-muted">{timeAgo(p.last_flip_at)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Flip Feed */}
            <Card className="lg:col-span-1">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <Zap size={14} className="text-warning" /> Flip Feed
                  <Badge variant="warning" className="ml-auto text-[10px]">Last 60s</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-[420px] overflow-y-auto">
                {d.flip_feed.length === 0 ? (
                  <p className="text-xs text-muted text-center py-8">No flips in the last minute</p>
                ) : (
                  <div className="space-y-1">
                    {d.flip_feed.map((f, i) => (
                      <div
                        key={`${f.session_id}-${f.flip_number}-${i}`}
                        className={`flex items-center justify-between py-1.5 px-2 rounded text-xs ${
                          f.is_zero ? 'bg-red-500/10 border border-red-500/20' : 'bg-card/30'
                        }`}
                      >
                        <div className="flex items-center gap-2">
                          <Coins size={12} className={f.is_zero ? 'text-red-400' : 'text-primary'} />
                          <span className="text-white font-medium">{f.player_name}</span>
                          <span className="text-muted">#{f.flip_number}</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className={`font-bold ${f.is_zero ? 'text-red-400' : 'text-success'}`}>
                            {f.is_zero ? 'ZERO' : `${f.currency}${f.value}`}
                          </span>
                          <span className="text-muted text-[10px]">{timeAgo(f.timestamp)}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Money Flow */}
            <Card className="lg:col-span-1">
              <CardHeader className="pb-2">
                <CardTitle className="text-sm flex items-center gap-2">
                  <TrendingUp size={14} className="text-success" /> Money Flow
                  <Badge variant="success" className="ml-auto text-[10px]">Last 5m</Badge>
                </CardTitle>
              </CardHeader>
              <CardContent className="max-h-[420px] overflow-y-auto">
                {d.money_feed.length === 0 ? (
                  <p className="text-xs text-muted text-center py-8">No deposits/withdrawals recently</p>
                ) : (
                  <div className="space-y-1.5">
                    {d.money_feed.map((m, i) => (
                      <div key={`${m.type}-${m.timestamp}-${i}`} className="flex items-center justify-between py-1.5 px-2 rounded bg-card/30">
                        <div className="flex items-center gap-2">
                          <div className={`w-6 h-6 rounded flex items-center justify-center ${
                            m.type === 'deposit' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'
                          }`}>
                            {m.type === 'deposit' ? <ArrowDownRight size={12} /> : <ArrowUpRight size={12} />}
                          </div>
                          <div>
                            <div className="text-xs text-white font-medium">{m.player_name}</div>
                            <div className="text-[10px] text-muted capitalize">{m.type}</div>
                          </div>
                        </div>
                        <div className="text-right">
                          <div className={`text-xs font-bold ${m.type === 'deposit' ? 'text-success' : 'text-warning'}`}>
                            {m.type === 'deposit' ? '+' : '-'}{formatCurrency(m.amount)}
                          </div>
                          <Badge variant={m.status === 'completed' ? 'success' : m.status === 'pending' ? 'warning' : 'danger'} className="text-[9px]">
                            {m.status}
                          </Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        )}

        {/* Today summary bar */}
        {d && (
          <Card>
            <CardContent className="py-3 px-6">
              <div className="flex flex-wrap items-center justify-between gap-4 text-xs">
                <div><span className="text-muted">Total Staked:</span> <span className="text-white font-bold ml-1">{formatCurrency(d.today.total_staked)}</span></div>
                <div><span className="text-muted">Total Paid Out:</span> <span className="text-warning font-bold ml-1">{formatCurrency(d.today.total_paid_out)}</span></div>
                <div><span className="text-muted">GGR:</span> <span className="text-success font-bold ml-1">{formatCurrency(d.today.ggr)}</span></div>
                <div><span className="text-muted">Sessions:</span> <span className="text-white font-bold ml-1">{d.today.sessions}</span></div>
                <div><span className="text-muted">Flips:</span> <span className="text-white font-bold ml-1">{d.today.flips.toLocaleString()}</span></div>
              </div>
            </CardContent>
          </Card>
        )}

        {!d && !error && (
          <div className="flex items-center justify-center py-20">
            <div className="text-center">
              <Activity size={40} className="mx-auto mb-3 text-primary animate-pulse" />
              <p className="text-muted text-sm">Connecting to live feed...</p>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
