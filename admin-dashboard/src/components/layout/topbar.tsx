import { useAuth } from '@/lib/auth'
import { Bell, Search } from 'lucide-react'
import { useState } from 'react'

export function Topbar({ title }: { title: string }) {
  const { user } = useAuth()
  const [searchOpen, setSearchOpen] = useState(false)

  return (
    <header className="h-16 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-30">
      <h1 className="text-lg font-semibold text-white">{title}</h1>

      <div className="flex items-center gap-3">
        {searchOpen ? (
          <input
            autoFocus
            type="text"
            placeholder="Search players, sessions..."
            className="w-64 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-white placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/50"
            onBlur={() => setSearchOpen(false)}
          />
        ) : (
          <button
            onClick={() => setSearchOpen(true)}
            className="p-2 rounded-lg text-slate-400 hover:bg-surface-hover hover:text-white transition-colors cursor-pointer"
          >
            <Search size={18} />
          </button>
        )}

        <button className="p-2 rounded-lg text-slate-400 hover:bg-surface-hover hover:text-white transition-colors relative cursor-pointer">
          <Bell size={18} />
          <span className="absolute top-1.5 right-1.5 w-2 h-2 bg-primary rounded-full" />
        </button>

        <div className="flex items-center gap-2 pl-3 border-l border-border">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold">
            {user?.display_name?.[0]?.toUpperCase() || 'A'}
          </div>
          <div className="hidden md:block">
            <div className="text-sm font-medium text-white">{user?.display_name}</div>
          </div>
        </div>
      </div>
    </header>
  )
}
