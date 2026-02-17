import { useEffect, useState } from 'react'
import { Topbar } from '@/components/layout/topbar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { api } from '@/lib/api'
import { Shield, Plus, Pencil, Trash2, Check, X, UserPlus } from 'lucide-react'

interface Role {
  id: string
  name: string
  codename: string
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
  const [error, setError] = useState('')
  const [editingRole, setEditingRole] = useState<string | null>(null)
  const [editPerms, setEditPerms] = useState<string[]>([])

  // Add staff form
  const [showAddStaff, setShowAddStaff] = useState(false)
  const [staffPhone, setStaffPhone] = useState('')
  const [staffRole, setStaffRole] = useState('')
  const [staffError, setStaffError] = useState('')
  const [staffSaving, setStaffSaving] = useState(false)

  // Add role form
  const [showAddRole, setShowAddRole] = useState(false)
  const [newRoleName, setNewRoleName] = useState('')
  const [newRoleCodename, setNewRoleCodename] = useState('')
  const [newRolePerms, setNewRolePerms] = useState<string[]>([])
  const [roleError, setRoleError] = useState('')
  const [roleSaving, setRoleSaving] = useState(false)

  const refresh = () => {
    api.get<RolesResponse>('/roles/')
      .then(d => { setData(d); setError('') })
      .catch(e => setError(e.message || 'Failed to load roles'))
      .finally(() => setLoading(false))
  }

  useEffect(() => { refresh() }, [])

  const startEdit = (role: Role) => {
    setEditingRole(role.id)
    setEditPerms([...role.permissions])
  }

  const togglePerm = (perm: string) => {
    setEditPerms(prev => prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm])
  }

  const toggleNewRolePerm = (perm: string) => {
    setNewRolePerms(prev => prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm])
  }

  const saveRole = async (roleId: string) => {
    try {
      await api.patch(`/roles/${roleId}/`, { permissions: editPerms })
      setEditingRole(null)
      refresh()
    } catch {}
  }

  const updateStaffRole = async (userId: string, role: string) => {
    try {
      await api.patch(`/roles/staff/${userId}/`, { role })
      refresh()
    } catch {}
  }

  const handleAddStaff = async (e: React.FormEvent) => {
    e.preventDefault()
    setStaffError('')
    if (!staffPhone || !staffRole) { setStaffError('Phone and role are required'); return }
    setStaffSaving(true)
    try {
      await api.post('/roles/staff/create/', { phone: staffPhone, role: staffRole })
      setShowAddStaff(false)
      setStaffPhone('')
      setStaffRole('')
      refresh()
    } catch (err: any) {
      setStaffError(err.message || 'Failed to add staff')
    }
    setStaffSaving(false)
  }

  const handleDeleteStaff = async (userId: string, name: string) => {
    if (!confirm(`Remove ${name} from staff?`)) return
    try {
      await api.delete(`/roles/staff/${userId}/delete/`)
      refresh()
    } catch {}
  }

  const handleAddRole = async (e: React.FormEvent) => {
    e.preventDefault()
    setRoleError('')
    if (!newRoleName) { setRoleError('Role name is required'); return }
    const codename = newRoleCodename || newRoleName.toLowerCase().replace(/\s+/g, '_')
    setRoleSaving(true)
    try {
      await api.post('/roles/create/', { name: newRoleName, codename, permissions: newRolePerms })
      setShowAddRole(false)
      setNewRoleName('')
      setNewRoleCodename('')
      setNewRolePerms([])
      refresh()
    } catch (err: any) {
      setRoleError(err.message || 'Failed to create role')
    }
    setRoleSaving(false)
  }

  if (loading) {
    return (
      <>
        <Topbar title="Roles & Access" />
        <div className="p-6"><div className="h-64 rounded-xl border border-border bg-card animate-pulse" /></div>
      </>
    )
  }

  if (error && !data) {
    return (
      <>
        <Topbar title="Roles & Access" />
        <div className="p-6">
          <Card><CardContent className="py-12 text-center text-danger">{error}</CardContent></Card>
        </div>
      </>
    )
  }

  const d = data!

  const permGroups: Record<string, { key: string; label: string }[]> = {}
  d.all_permissions.forEach(p => {
    if (!permGroups[p.group]) permGroups[p.group] = []
    permGroups[p.group].push(p)
  })

  return (
    <>
      <Topbar title="Roles & Access" />
      <div className="p-6 space-y-6">
        {/* Action Buttons */}
        <div className="flex items-center gap-3">
          <Button onClick={() => setShowAddRole(true)}>
            <Plus size={16} /> Add Role
          </Button>
          <Button variant="secondary" onClick={() => { setShowAddStaff(true); if (d.roles.length && !staffRole) setStaffRole(d.roles[0].codename) }}>
            <UserPlus size={16} /> Add Staff Member
          </Button>
        </div>

        {/* Add Role Form */}
        {showAddRole && (
          <Card className="border-primary/30">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Create New Role</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setShowAddRole(false)}><X size={16} /></Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAddRole} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Role Name</label>
                    <Input placeholder="e.g. Content Manager" value={newRoleName} onChange={e => setNewRoleName(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Codename (auto-generated if blank)</label>
                    <Input placeholder="e.g. content_manager" value={newRoleCodename} onChange={e => setNewRoleCodename(e.target.value)} />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-300 mb-2">Permissions</label>
                  <div className="space-y-3">
                    {Object.entries(permGroups).map(([group, perms]) => (
                      <div key={group}>
                        <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-1.5">{group}</h4>
                        <div className="flex flex-wrap gap-2">
                          {perms.map(p => (
                            <button type="button" key={p.key} onClick={() => toggleNewRolePerm(p.key)}
                              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                                newRolePerms.includes(p.key)
                                  ? 'bg-primary/15 text-primary border border-primary/30'
                                  : 'bg-surface text-muted border border-border hover:text-white'
                              }`}>{p.label}</button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
                {roleError && <p className="text-sm text-danger">{roleError}</p>}
                <Button type="submit" disabled={roleSaving}>{roleSaving ? 'Creating...' : 'Create Role'}</Button>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Add Staff Form */}
        {showAddStaff && (
          <Card className="border-primary/30">
            <CardHeader className="flex flex-row items-center justify-between">
              <CardTitle className="text-base">Add Staff Member</CardTitle>
              <Button variant="ghost" size="sm" onClick={() => setShowAddStaff(false)}><X size={16} /></Button>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleAddStaff} className="space-y-4">
                <p className="text-sm text-muted">Enter the phone number of an existing player account to promote to staff.</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Phone Number</label>
                    <Input placeholder="e.g. 0241234567" value={staffPhone} onChange={e => setStaffPhone(e.target.value)} />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-300 mb-1.5">Assign Role</label>
                    <select value={staffRole} onChange={e => setStaffRole(e.target.value)}
                      className="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-white">
                      {d.roles.map(r => <option key={r.id} value={r.codename}>{r.display_name}</option>)}
                    </select>
                  </div>
                </div>
                {staffError && <p className="text-sm text-danger">{staffError}</p>}
                <Button type="submit" disabled={staffSaving}>{staffSaving ? 'Adding...' : 'Add Staff Member'}</Button>
              </form>
            </CardContent>
          </Card>
        )}

        {/* Roles Grid */}
        {d.roles.length === 0 ? (
          <Card><CardContent className="py-12 text-center text-muted">
            <Shield size={40} className="mx-auto mb-3 opacity-40" />
            <div className="text-lg mb-1">No roles defined</div>
            <div className="text-sm">Click "Add Role" above to create your first admin role</div>
          </CardContent></Card>
        ) : (
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
                      <p className="text-xs text-muted">{role.user_count} staff member{role.user_count !== 1 ? 's' : ''} &middot; {role.codename}</p>
                    </div>
                  </div>
                  {editingRole === role.id ? (
                    <div className="flex gap-2">
                      <Button variant="ghost" size="sm" onClick={() => setEditingRole(null)}><X size={14} /></Button>
                      <Button variant="primary" size="sm" onClick={() => saveRole(role.id)}>
                        <Check size={14} /> Save
                      </Button>
                    </div>
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
                              <button key={p.key} onClick={() => togglePerm(p.key)}
                                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                                  editPerms.includes(p.key)
                                    ? 'bg-primary/15 text-primary border border-primary/30'
                                    : 'bg-surface text-muted border border-border hover:text-white'
                                }`}>{p.label}</button>
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
        )}

        {/* Staff Members */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Staff Members ({d.staff.length})</CardTitle>
            {!showAddStaff && (
              <Button variant="secondary" size="sm" onClick={() => { setShowAddStaff(true); if (d.roles.length && !staffRole) setStaffRole(d.roles[0].codename) }}>
                <UserPlus size={14} /> Add
              </Button>
            )}
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
                        <option key={r.id} value={r.codename}>{r.display_name}</option>
                      ))}
                    </select>
                    <Badge variant={user.is_active ? 'success' : 'danger'}>
                      {user.is_active ? 'Active' : 'Disabled'}
                    </Badge>
                    <Button variant="ghost" size="sm" title="Remove staff member"
                      onClick={() => handleDeleteStaff(user.id, user.display_name)}>
                      <Trash2 size={14} className="text-danger" />
                    </Button>
                  </div>
                </div>
              ))}
              {d.staff.length === 0 && (
                <div className="text-center py-8 text-muted">
                  <UserPlus size={32} className="mx-auto mb-2 opacity-40" />
                  <div className="text-sm">No staff members yet. Click "Add Staff Member" to get started.</div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
