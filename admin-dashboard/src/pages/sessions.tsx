import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, Eye } from 'lucide-react'

interface Session {
  id: string
  player_name: string
  player_phone: string
  stake: string
  currency: string
  flips: number
  result: string
  payout: string
  created_at: string
  status: string
}

interface SessionsResponse {
  results: Session[]
  count: number
  next: string | null
}

export default function SessionsPage() {
  const [data, setData] = useState<SessionsResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')

  const fetchSessions = (p = 1, q = '', status = '') => {
    setLoading(true)
    const params: Record<string, string> = { page: String(p) }
    if (q) params.search = q
    if (status) params.status = status
    api.get<SessionsResponse>('/sessions/', params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchSessions() }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetchSessions(1, search, statusFilter)
  }

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  const statusBadge = (status: string) => {
    const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
      active: 'info', completed: 'success', cashed_out: 'success', lost: 'danger', expired: 'warning',
    }
    return <Badge variant={map[status] || 'default'}>{status.replace('_', ' ')}</Badge>
  }

  return (
    <>
      <Topbar title="Game Sessions" />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <Input placeholder="Search by player..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 w-64" />
            </div>
            <select
              value={statusFilter}
              onChange={e => { setStatusFilter(e.target.value); setPage(1); fetchSessions(1, search, e.target.value) }}
              className="rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white"
            >
              <option value="">All Status</option>
              <option value="active">Active</option>
              <option value="completed">Completed</option>
              <option value="cashed_out">Cashed Out</option>
              <option value="lost">Lost</option>
            </select>
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
          <span className="text-sm text-muted">{data?.count ?? 0} sessions</span>
        </div>

        <Card className="p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Player</TableHead>
                  <TableHead>Stake</TableHead>
                  <TableHead>Flips</TableHead>
                  <TableHead>Payout</TableHead>
                  <TableHead>Result</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                  <TableHead>Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(8)].map((_, j) => (
                        <TableCell key={j}><div className="h-4 bg-surface rounded animate-pulse w-16" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : !data?.results.length ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12">
                      <div className="text-muted">
                        <div className="text-lg mb-1">No game sessions found</div>
                        <div className="text-sm">{search || statusFilter ? 'Try adjusting your filters' : 'Sessions will appear here once players start playing'}</div>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : data?.results.map(s => (
                  <TableRow key={s.id}>
                    <TableCell>
                      <div>
                        <div className="text-white font-medium text-sm">{s.player_name}</div>
                        <div className="text-xs text-muted">{s.player_phone}</div>
                      </div>
                    </TableCell>
                    <TableCell className="font-medium">{formatCurrency(s.stake, s.currency)}</TableCell>
                    <TableCell>{s.flips}</TableCell>
                    <TableCell className={`font-medium ${parseFloat(s.payout) > 0 ? 'text-success' : 'text-slate-400'}`}>
                      {formatCurrency(s.payout, s.currency)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={s.result === 'won' ? 'success' : s.result === 'lost' ? 'danger' : 'info'}>
                        {s.result || 'in play'}
                      </Badge>
                    </TableCell>
                    <TableCell>{statusBadge(s.status)}</TableCell>
                    <TableCell className="text-muted text-xs">{formatDateTime(s.created_at)}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm"><Eye size={14} /></Button>
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
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => { setPage(p => p - 1); fetchSessions(page - 1, search, statusFilter) }}>
                <ChevronLeft size={14} /> Previous
              </Button>
              <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => { setPage(p => p + 1); fetchSessions(page + 1, search, statusFilter) }}>
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
