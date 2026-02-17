import { NavLink } from 'react-router-dom'
import { useAuth } from '@/lib/auth'
import {
  LayoutDashboard, Users, Gamepad2, ArrowLeftRight,
  Wallet, Building2, Settings, Shield, LogOut,
  ChevronLeft, ChevronRight, TrendingUp,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useState } from 'react'

const navItems = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, perm: null },
  { to: '/players', label: 'Players', icon: Users, perm: 'view_players' },
  { to: '/sessions', label: 'Game Sessions', icon: Gamepad2, perm: 'view_sessions' },
  { to: '/transactions', label: 'Transactions', icon: ArrowLeftRight, perm: 'view_transactions' },
  { to: '/finance', label: 'Finance', icon: Wallet, perm: 'view_finance' },
  { to: '/partners', label: 'Partners', icon: Building2, perm: 'view_partners' },
  { to: '/analytics', label: 'Analytics', icon: TrendingUp, perm: 'view_analytics' },
  { to: '/roles', label: 'Roles & Access', icon: Shield, perm: 'manage_roles' },
  { to: '/settings', label: 'Settings', icon: Settings, perm: 'manage_settings' },
]

export function Sidebar() {
  const { user, logout, hasPermission } = useAuth()
  const [collapsed, setCollapsed] = useState(false)

  return (
    <aside className={cn(
      'fixed left-0 top-0 h-full bg-card border-r border-border flex flex-col transition-all duration-300 z-40',
      collapsed ? 'w-16' : 'w-60'
    )}>
      {/* Logo */}
      <div className="h-16 flex items-center px-4 border-b border-border gap-2">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center text-primary font-bold text-sm shrink-0">
          CF
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <span className="text-white font-bold text-sm">CASH</span>
            <span className="text-primary font-bold text-sm">FLIP</span>
            <span className="text-muted text-[10px] block -mt-0.5">Admin Console</span>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 py-4 px-2 space-y-1 overflow-y-auto">
        {navItems.map(item => {
          if (item.perm && !hasPermission(item.perm)) return null
          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) => cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary/15 text-primary'
                  : 'text-slate-400 hover:bg-surface-hover hover:text-white'
              )}
            >
              <item.icon size={20} className="shrink-0" />
              {!collapsed && <span>{item.label}</span>}
            </NavLink>
          )
        })}
      </nav>

      {/* Bottom */}
      <div className="p-3 border-t border-border">
        {!collapsed && user && (
          <div className="flex items-center gap-2 mb-3 px-2">
            <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold shrink-0">
              {user.display_name?.[0]?.toUpperCase() || 'A'}
            </div>
            <div className="overflow-hidden">
              <div className="text-sm font-medium text-white truncate">{user.display_name}</div>
              <div className="text-[11px] text-muted truncate capitalize">{user.role?.replace('_', ' ')}</div>
            </div>
          </div>
        )}
        <div className="flex items-center gap-1">
          <button
            onClick={logout}
            className={cn(
              'flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-slate-400 hover:bg-danger/10 hover:text-danger transition-colors cursor-pointer',
              collapsed ? 'justify-center w-full' : ''
            )}
          >
            <LogOut size={18} />
            {!collapsed && <span>Logout</span>}
          </button>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto p-2 rounded-lg text-slate-400 hover:bg-surface-hover hover:text-white transition-colors cursor-pointer"
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>
      </div>
    </aside>
  )
}
