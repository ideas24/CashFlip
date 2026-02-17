import { useAuth } from '@/lib/auth'
import { api } from '@/lib/api'
import { Bell, Search, X, Users, Gamepad2, ArrowRightLeft, Building2, AlertTriangle, Info, CheckCircle, AlertCircle, LogOut, ChevronRight } from 'lucide-react'
import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { timeAgo } from '@/lib/utils'

interface SearchResult {
  type: string
  id: string
  title: string
  subtitle: string
  meta: string
  url: string
}

interface Notification {
  id: string
  type: string
  title: string
  message: string
  url: string
  created_at: string
  read: boolean
}

const typeIcons: Record<string, typeof Users> = {
  player: Users,
  session: Gamepad2,
  transaction: ArrowRightLeft,
  partner: Building2,
}

const notifIcons: Record<string, { icon: typeof AlertTriangle; color: string }> = {
  warning: { icon: AlertTriangle, color: 'text-warning' },
  info: { icon: Info, color: 'text-blue-400' },
  alert: { icon: AlertCircle, color: 'text-orange-400' },
  danger: { icon: AlertCircle, color: 'text-danger' },
  success: { icon: CheckCircle, color: 'text-success' },
}

export function Topbar({ title }: { title: string }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  // Search state
  const [searchOpen, setSearchOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [searching, setSearching] = useState(false)
  const [selectedIdx, setSelectedIdx] = useState(-1)
  const searchRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Notifications state
  const [notifOpen, setNotifOpen] = useState(false)
  const [notifications, setNotifications] = useState<Notification[]>([])
  const [unreadCount, setUnreadCount] = useState(0)
  const [notifLoading, setNotifLoading] = useState(false)
  const notifRef = useRef<HTMLDivElement>(null)
  const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => {
    try { return new Set(JSON.parse(localStorage.getItem('cf_dismissed_notifs') || '[]')) }
    catch { return new Set() }
  })

  // Search debounce
  const doSearch = useCallback((q: string) => {
    if (q.length < 2) { setResults([]); setSearching(false); return }
    setSearching(true)
    api.get<{ results: SearchResult[] }>('/search/', { q })
      .then(d => { setResults(d.results); setSelectedIdx(-1) })
      .catch(() => setResults([]))
      .finally(() => setSearching(false))
  }, [])

  useEffect(() => {
    if (searchTimer.current) clearTimeout(searchTimer.current)
    searchTimer.current = setTimeout(() => doSearch(query), 250)
    return () => { if (searchTimer.current) clearTimeout(searchTimer.current) }
  }, [query, doSearch])

  // Fetch notifications
  const fetchNotifications = useCallback(() => {
    setNotifLoading(true)
    api.get<{ notifications: Notification[]; unread_count: number }>('/notifications/')
      .then(d => {
        const filtered = d.notifications.filter(n => !dismissedIds.has(n.id))
        setNotifications(filtered)
        setUnreadCount(filtered.length)
      })
      .catch(() => {})
      .finally(() => setNotifLoading(false))
  }, [dismissedIds])

  useEffect(() => {
    fetchNotifications()
    const interval = setInterval(fetchNotifications, 60000)
    return () => clearInterval(interval)
  }, [fetchNotifications])

  // Click outside to close
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setSearchOpen(false)
        setQuery('')
        setResults([])
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        setSearchOpen(true)
        setTimeout(() => inputRef.current?.focus(), 50)
      }
      if (e.key === 'Escape') {
        setSearchOpen(false)
        setNotifOpen(false)
        setQuery('')
        setResults([])
      }
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setSelectedIdx(i => Math.min(i + 1, results.length - 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setSelectedIdx(i => Math.max(i - 1, 0)) }
    else if (e.key === 'Enter' && selectedIdx >= 0 && results[selectedIdx]) {
      e.preventDefault()
      navigate(results[selectedIdx].url)
      setSearchOpen(false)
      setQuery('')
      setResults([])
    }
  }

  const navigateResult = (result: SearchResult) => {
    navigate(result.url)
    setSearchOpen(false)
    setQuery('')
    setResults([])
  }

  const dismissNotif = (id: string) => {
    const newDismissed = new Set(dismissedIds)
    newDismissed.add(id)
    setDismissedIds(newDismissed)
    localStorage.setItem('cf_dismissed_notifs', JSON.stringify([...newDismissed]))
    setNotifications(prev => prev.filter(n => n.id !== id))
    setUnreadCount(prev => Math.max(prev - 1, 0))
  }

  const clearAllNotifs = () => {
    const allIds = new Set([...dismissedIds, ...notifications.map(n => n.id)])
    setDismissedIds(allIds)
    localStorage.setItem('cf_dismissed_notifs', JSON.stringify([...allIds]))
    setNotifications([])
    setUnreadCount(0)
  }

  const navigateNotif = (notif: Notification) => {
    navigate(notif.url)
    setNotifOpen(false)
  }

  return (
    <header className="h-16 border-b border-border bg-card/80 backdrop-blur-sm flex items-center justify-between px-6 sticky top-0 z-30">
      <h1 className="text-lg font-semibold text-white">{title}</h1>

      <div className="flex items-center gap-2">
        {/* === SEARCH === */}
        <div ref={searchRef} className="relative">
          {searchOpen ? (
            <div className="relative">
              <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted" />
              <input
                ref={inputRef}
                autoFocus
                type="text"
                value={query}
                onChange={e => setQuery(e.target.value)}
                onKeyDown={handleSearchKeyDown}
                placeholder="Search players, sessions, transactions..."
                className="w-80 rounded-lg border border-border bg-surface pl-9 pr-8 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:ring-2 focus:ring-primary/50"
              />
              <button onClick={() => { setSearchOpen(false); setQuery(''); setResults([]) }}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white cursor-pointer">
                <X size={14} />
              </button>

              {/* Results dropdown */}
              {(query.length >= 2) && (
                <div className="absolute top-full left-0 right-0 mt-1 bg-card border border-border rounded-xl shadow-xl max-h-[420px] overflow-y-auto z-50">
                  {searching ? (
                    <div className="p-4 text-center text-sm text-muted">Searching...</div>
                  ) : results.length === 0 ? (
                    <div className="p-4 text-center text-sm text-muted">No results for "{query}"</div>
                  ) : (
                    <div className="py-1">
                      {results.map((r, i) => {
                        const Icon = typeIcons[r.type] || Search
                        return (
                          <button key={`${r.type}-${r.id}`}
                            onClick={() => navigateResult(r)}
                            onMouseEnter={() => setSelectedIdx(i)}
                            className={`w-full flex items-center gap-3 px-4 py-2.5 text-left transition-colors cursor-pointer ${
                              i === selectedIdx ? 'bg-surface-hover' : 'hover:bg-surface-hover/50'
                            }`}>
                            <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center text-primary shrink-0">
                              <Icon size={16} />
                            </div>
                            <div className="flex-1 min-w-0">
                              <div className="text-sm font-medium text-white truncate">{r.title}</div>
                              <div className="text-xs text-muted truncate">{r.subtitle}</div>
                            </div>
                            <div className="text-xs text-muted shrink-0">{r.meta}</div>
                            <ChevronRight size={14} className="text-muted shrink-0" />
                          </button>
                        )
                      })}
                    </div>
                  )}
                  <div className="border-t border-border px-4 py-2 flex items-center justify-between text-xs text-muted">
                    <span>{results.length} result{results.length !== 1 ? 's' : ''}</span>
                    <span className="flex items-center gap-1">
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px]">↑↓</kbd> navigate
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] ml-2">↵</kbd> select
                      <kbd className="px-1.5 py-0.5 bg-surface rounded text-[10px] ml-2">esc</kbd> close
                    </span>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <button
              onClick={() => { setSearchOpen(true); setTimeout(() => inputRef.current?.focus(), 50) }}
              className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-border bg-surface text-muted hover:text-white hover:border-slate-600 transition-colors cursor-pointer"
            >
              <Search size={15} />
              <span className="text-sm hidden md:inline">Search...</span>
              <kbd className="hidden md:inline px-1.5 py-0.5 bg-card rounded text-[10px] border border-border ml-2">⌘K</kbd>
            </button>
          )}
        </div>

        {/* === NOTIFICATIONS === */}
        <div ref={notifRef} className="relative">
          <button
            onClick={() => { setNotifOpen(!notifOpen); if (!notifOpen) fetchNotifications() }}
            className="p-2 rounded-lg text-slate-400 hover:bg-surface-hover hover:text-white transition-colors relative cursor-pointer"
          >
            <Bell size={18} />
            {unreadCount > 0 && (
              <span className="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] rounded-full bg-danger text-white text-[10px] font-bold flex items-center justify-center px-1">
                {unreadCount > 9 ? '9+' : unreadCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute top-full right-0 mt-1 w-96 bg-card border border-border rounded-xl shadow-xl z-50 overflow-hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                <h3 className="text-sm font-semibold text-white">Notifications</h3>
                {notifications.length > 0 && (
                  <button onClick={clearAllNotifs} className="text-xs text-muted hover:text-white cursor-pointer">Clear all</button>
                )}
              </div>

              <div className="max-h-[400px] overflow-y-auto">
                {notifLoading && notifications.length === 0 ? (
                  <div className="p-6 text-center text-sm text-muted">Loading...</div>
                ) : notifications.length === 0 ? (
                  <div className="p-8 text-center">
                    <Bell size={28} className="mx-auto mb-2 text-muted opacity-40" />
                    <div className="text-sm text-muted">All caught up!</div>
                    <div className="text-xs text-muted mt-0.5">No new notifications</div>
                  </div>
                ) : (
                  <div>
                    {notifications.map(n => {
                      const iconInfo = notifIcons[n.type] || notifIcons.info
                      const Icon = iconInfo.icon
                      return (
                        <div key={n.id} className="flex items-start gap-3 px-4 py-3 hover:bg-surface-hover/50 transition-colors border-b border-border/30 last:border-0">
                          <div className={`mt-0.5 shrink-0 ${iconInfo.color}`}>
                            <Icon size={18} />
                          </div>
                          <button onClick={() => navigateNotif(n)} className="flex-1 text-left min-w-0 cursor-pointer">
                            <div className="text-sm font-medium text-white">{n.title}</div>
                            <div className="text-xs text-muted mt-0.5">{n.message}</div>
                            <div className="text-[10px] text-muted mt-1">{timeAgo(n.created_at)}</div>
                          </button>
                          <button onClick={(e) => { e.stopPropagation(); dismissNotif(n.id) }}
                            className="shrink-0 p-1 text-muted hover:text-white cursor-pointer" title="Dismiss">
                            <X size={12} />
                          </button>
                        </div>
                      )
                    })}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* === USER MENU === */}
        <div className="flex items-center gap-2 pl-3 border-l border-border">
          <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-primary text-xs font-bold">
            {user?.display_name?.[0]?.toUpperCase() || 'A'}
          </div>
          <div className="hidden md:block">
            <div className="text-sm font-medium text-white leading-tight">{user?.display_name}</div>
            <div className="text-[10px] text-muted leading-tight capitalize">{user?.role?.replace('_', ' ')}</div>
          </div>
          <button onClick={logout} title="Logout"
            className="p-1.5 rounded-lg text-muted hover:text-danger hover:bg-surface-hover transition-colors cursor-pointer ml-1">
            <LogOut size={15} />
          </button>
        </div>
      </div>
    </header>
  )
}
