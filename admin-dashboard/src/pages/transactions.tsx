import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Search, ChevronLeft, ChevronRight, ArrowUpRight, ArrowDownRight } from 'lucide-react'

interface Transaction {
  id: string
  player_name: string
  player_phone: string
  type: string
  amount: string
  currency: string
  status: string
  reference: string
  provider: string
  created_at: string
}

interface TxResponse {
  results: Transaction[]
  count: number
  next: string | null
}

export default function TransactionsPage() {
  const [data, setData] = useState<TxResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [typeFilter, setTypeFilter] = useState('')

  const fetch_ = (p = 1, q = '', type = '') => {
    setLoading(true)
    const params: Record<string, string> = { page: String(p) }
    if (q) params.search = q
    if (type) params.type = type
    api.get<TxResponse>('/transactions/', params)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetch_() }, [])

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault()
    setPage(1)
    fetch_(1, search, typeFilter)
  }

  const totalPages = data ? Math.ceil(data.count / 25) : 0

  return (
    <>
      <Topbar title="Transactions" />
      <div className="p-6 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <form onSubmit={handleSearch} className="flex items-center gap-2">
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <Input placeholder="Search by phone or ref..." value={search} onChange={e => setSearch(e.target.value)} className="pl-9 w-64" />
            </div>
            <select
              value={typeFilter}
              onChange={e => { setTypeFilter(e.target.value); setPage(1); fetch_(1, search, e.target.value) }}
              className="rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white"
            >
              <option value="">All Types</option>
              <option value="deposit">Deposits</option>
              <option value="withdrawal">Withdrawals</option>
              <option value="bonus">Bonuses</option>
            </select>
            <Button type="submit" variant="secondary" size="sm">Search</Button>
          </form>
          <span className="text-sm text-muted">{data?.count ?? 0} transactions</span>
        </div>

        <Card className="p-0">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Player</TableHead>
                  <TableHead>Amount</TableHead>
                  <TableHead>Provider</TableHead>
                  <TableHead>Reference</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Date</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  [...Array(5)].map((_, i) => (
                    <TableRow key={i}>
                      {[...Array(7)].map((_, j) => (
                        <TableCell key={j}><div className="h-4 bg-surface rounded animate-pulse w-16" /></TableCell>
                      ))}
                    </TableRow>
                  ))
                ) : !data?.results.length ? (
                  <TableRow>
                    <TableCell colSpan={7} className="text-center py-12">
                      <div className="text-muted">
                        <div className="text-lg mb-1">No transactions found</div>
                        <div className="text-sm">{search || typeFilter ? 'Try adjusting your filters' : 'Transactions will appear here once players make deposits or withdrawals'}</div>
                      </div>
                    </TableCell>
                  </TableRow>
                ) : data?.results.map(tx => (
                  <TableRow key={tx.id}>
                    <TableCell>
                      <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${tx.type === 'deposit' ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'}`}>
                        {tx.type === 'deposit' ? <ArrowDownRight size={16} /> : <ArrowUpRight size={16} />}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div>
                        <div className="text-white font-medium text-sm">{tx.player_name}</div>
                        <div className="text-xs text-muted">{tx.player_phone}</div>
                      </div>
                    </TableCell>
                    <TableCell className={`font-semibold ${tx.type === 'deposit' ? 'text-success' : 'text-warning'}`}>
                      {tx.type === 'deposit' ? '+' : '-'}{formatCurrency(tx.amount, tx.currency)}
                    </TableCell>
                    <TableCell className="capitalize text-sm">{tx.provider}</TableCell>
                    <TableCell className="text-xs font-mono text-muted">{tx.reference}</TableCell>
                    <TableCell>
                      <Badge variant={tx.status === 'completed' ? 'success' : tx.status === 'pending' ? 'warning' : 'danger'}>
                        {tx.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-muted text-xs">{formatDateTime(tx.created_at)}</TableCell>
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
              <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => { setPage(p => p - 1); fetch_(page - 1, search, typeFilter) }}>
                <ChevronLeft size={14} /> Previous
              </Button>
              <Button variant="outline" size="sm" disabled={!data?.next} onClick={() => { setPage(p => p + 1); fetch_(page + 1, search, typeFilter) }}>
                Next <ChevronRight size={14} />
              </Button>
            </div>
          </div>
        )}
      </div>
    </>
  )
}
