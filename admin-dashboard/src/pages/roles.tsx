import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { Shield, Plus, Pencil, Trash2, Check } from 'lucide-react'

interface Role {
  id: string
  name: string
  display_name: string
  permissions: string[]
  user_count: number
}

interface StaffUser {
  id: string
  phone: string
  display_name: string
  role: string
  role_display: string
  is_active: boolean
  last_login: string
}

interface RolesResponse {
  roles: Role[]
  staff: StaffUser[]
  all_permissions: { key: string; label: string; group: string }[]
}

export default function RolesPage() {
  const [data, setData] = useState<RolesResponse | null>(null)
  const [loading, setLoading] = useState(true)
  const [editingRole, setEditingRole] = useState<string | null>(null)
  const [editPerms, setEditPerms] = useState<string[]>([])

  useEffect(() => {
    api.get<RolesResponse>('/roles/')
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [])

  const startEdit = (role: Role) => {
    setEditingRole(role.id)
    setEditPerms([...role.permissions])
  }

  const togglePerm = (perm: string) => {
    setEditPerms(prev => prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm])
  }

  const saveRole = async (roleId: string) => {
    try {
      await api.patch(`/roles/${roleId}/`, { permissions: editPerms })
      setEditingRole(null)
      api.get<RolesResponse>('/roles/').then(setData)
    } catch {}
  }

  const updateStaffRole = async (userId: string, role: string) => {
    try {
      await api.patch(`/roles/staff/${userId}/`, { role })
      api.get<RolesResponse>('/roles/').then(setData)
    } catch {}
  }

  if (loading) {
    return (
      <>
        <Topbar title="Roles & Access" />
        <div className="p-6"><div className="h-64 rounded-xl border border-border bg-card animate-pulse" /></div>
      </>
    )
  }

  const d = data!

  // Group permissions by category
  const permGroups: Record<string, { key: string; label: string }[]> = {}
  d.all_permissions.forEach(p => {
    if (!permGroups[p.group]) permGroups[p.group] = []
    permGroups[p.group].push(p)
  })

  return (
    <>
      <Topbar title="Roles & Access" />
      <div className="p-6 space-y-6">
        {/* Roles */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {d.roles.map(role => (
            <Card key={role.id}>
              <CardHeader className="flex flex-row items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center text-primary">
                    <Shield size={20} />
                  </div>
                  <div>
                    <CardTitle className="text-base">{role.display_name}</CardTitle>
                    <p className="text-xs text-muted">{role.user_count} staff member{role.user_count !== 1 ? 's' : ''}</p>
                  </div>
                </div>
                {editingRole === role.id ? (
                  <Button variant="primary" size="sm" onClick={() => saveRole(role.id)}>
                    <Check size={14} /> Save
                  </Button>
                ) : (
                  <Button variant="ghost" size="sm" onClick={() => startEdit(role)}>
                    <Pencil size={14} /> Edit
                  </Button>
                )}
              </CardHeader>
              <CardContent>
                {editingRole === role.id ? (
                  <div className="space-y-4">
                    {Object.entries(permGroups).map(([group, perms]) => (
                      <div key={group}>
                        <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-2">{group}</h4>
                        <div className="flex flex-wrap gap-2">
                          {perms.map(p => (
                            <button
                              key={p.key}
                              onClick={() => togglePerm(p.key)}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                                editPerms.includes(p.key)
                                  ? 'bg-primary/15 text-primary border border-primary/30'
                                  : 'bg-surface text-muted border border-border hover:text-white'
                              }`}
                            >
                              {p.label}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {role.permissions.map(p => (
                      <Badge key={p} variant="info">{p.replace(/_/g, ' ')}</Badge>
                    ))}
                    {role.permissions.length === 0 && (
                      <span className="text-xs text-muted">No permissions assigned</span>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Staff Members */}
        <Card>
          <CardHeader>
            <CardTitle>Staff Members</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {d.staff.map(user => (
                <div key={user.id} className="flex items-center justify-between py-3 border-b border-border/50 last:border-0">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-primary/15 flex items-center justify-center text-primary font-bold text-sm">
                      {user.display_name?.[0]?.toUpperCase() || '?'}
                    </div>
                    <div>
                      <div className="text-sm font-medium text-white">{user.display_name}</div>
                      <div className="text-xs text-muted">{user.phone}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <select
                      value={user.role}
                      onChange={e => updateStaffRole(user.id, e.target.value)}
                      className="rounded-lg border border-border bg-surface px-3 py-1.5 text-sm text-white"
                    >
                      {d.roles.map(r => (
                        <option key={r.id} value={r.name}>{r.display_name}</option>
                      ))}
                    </select>
                    <Badge variant={user.is_active ? 'success' : 'danger'}>
                      {user.is_active ? 'Active' : 'Disabled'}
                    </Badge>
                  </div>
                </div>
              ))}
              {d.staff.length === 0 && (
                <p className="text-sm text-muted text-center py-4">No staff members</p>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
