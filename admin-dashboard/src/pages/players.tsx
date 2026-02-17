import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, Eye, Ban, CheckCircle } from 'lucide-react'

interface Player {
  id: string
  phone: string
  display_name: string
  balance: string
  total_sessions: number
  total_wagered: string
  is_active: boolean
  created_at: string
  last_login: string
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
                    <TableCell className="text-muted text-xs">{formatDateTime(player.created_at)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1">
                        <Button variant="ghost" size="sm" title="View details">
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
    </>
  )
}
