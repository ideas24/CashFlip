import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { api } from '@/lib/api'
import { formatCurrency, formatDateTime } from '@/lib/utils'
import { Building2, Eye, Key, Globe } from 'lucide-react'

interface Partner {
  id: string
  name: string
  slug: string
  website: string
  status: string
  commission_percent: string
  settlement_frequency: string
  total_sessions: number
  total_revenue: string
  api_keys_count: number
  created_at: string
}

interface PartnersResponse {
  results: Partner[]
  count: number
}

export default function PartnersPage() {
  const [data, setData] = useState<PartnersResponse | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get<PartnersResponse>('/partners/')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  return (
    <>
      <Topbar title="Partners" />
      <div className="p-6 space-y-6">
        <div className="flex items-center justify-between">
          <p className="text-sm text-muted">{data?.count ?? 0} operators registered</p>
          <Button variant="primary" size="sm">
            <Building2 size={14} /> Add Partner
          </Button>
        </div>

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
                ) : data?.results.map(p => (
                  <TableRow key={p.id}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center text-primary font-bold text-xs">
                          {p.name.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <div className="text-white font-medium">{p.name}</div>
                          <div className="text-xs text-muted flex items-center gap-1"><Globe size={10} /> {p.website}</div>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={p.status === 'active' ? 'success' : p.status === 'sandbox' ? 'info' : 'danger'}>
                        {p.status}
                      </Badge>
                    </TableCell>
                    <TableCell className="font-medium">{p.commission_percent}%</TableCell>
                    <TableCell className="capitalize text-sm">{p.settlement_frequency}</TableCell>
                    <TableCell>{p.total_sessions.toLocaleString()}</TableCell>
                    <TableCell className="font-medium text-accent">{formatCurrency(p.total_revenue)}</TableCell>
                    <TableCell>
                      <div className="flex items-center gap-1 text-muted">
                        <Key size={12} /> {p.api_keys_count}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted text-xs">{formatDateTime(p.created_at)}</TableCell>
                    <TableCell>
                      <Button variant="ghost" size="sm"><Eye size={14} /></Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
