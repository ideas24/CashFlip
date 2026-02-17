import { type ReactNode } from 'react'
import { cn } from '@/lib/utils'

interface StatCardProps {
  title: string
  value: string | number
  icon: ReactNode
  change?: string
  changeType?: 'up' | 'down' | 'neutral'
  className?: string
}

export function StatCard({ title, value, icon, change, changeType = 'neutral', className }: StatCardProps) {
  return (
    <div className={cn('rounded-xl border border-border bg-card p-5', className)}>
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-muted">{title}</span>
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
          {icon}
        </div>
      </div>
      <div className="text-2xl font-bold text-white mb-1">{value}</div>
      {change && (
        <span className={cn('text-xs font-medium', {
          'text-success': changeType === 'up',
          'text-danger': changeType === 'down',
          'text-muted': changeType === 'neutral',
        })}>
          {changeType === 'up' ? '↑' : changeType === 'down' ? '↓' : ''} {change}
        </span>
      )}
    </div>
  )
}
