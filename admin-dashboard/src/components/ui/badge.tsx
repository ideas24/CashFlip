import { type HTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'success' | 'warning' | 'danger' | 'info'
}

export function Badge({ className, variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        {
          'bg-surface text-slate-300': variant === 'default',
          'bg-success/15 text-success': variant === 'success',
          'bg-warning/15 text-warning': variant === 'warning',
          'bg-danger/15 text-danger': variant === 'danger',
          'bg-primary/15 text-primary': variant === 'info',
        },
        className
      )}
      {...props}
    />
  )
}
