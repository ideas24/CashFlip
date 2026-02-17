import { createContext, useContext, useState, useEffect, type ReactNode } from 'react'
import { api } from './api'

interface User {
  id: string
  phone: string
  display_name: string
  role: string
  permissions: string[]
}

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (phone: string, password: string) => Promise<void>
  logout: () => void
  hasPermission: (perm: string) => boolean
  hasRole: (role: string) => boolean
}

const AuthContext = createContext<AuthContextType | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = api.getToken()
    if (token) {
      api.get<User>('/me/')
        .then(setUser)
        .catch(() => api.setToken(null))
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = async (phone: string, password: string) => {
    const data = await api.post<{ access_token: string; user: User }>('/auth/login/', { phone, password })
    api.setToken(data.access_token)
    setUser(data.user)
  }

  const logout = () => {
    api.setToken(null)
    setUser(null)
    window.location.href = '/login'
  }

  const hasPermission = (perm: string) => {
    if (!user) return false
    if (user.role === 'super_admin') return true
    return user.permissions.includes(perm)
  }

  const hasRole = (role: string) => {
    return user?.role === role || user?.role === 'super_admin'
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout, hasPermission, hasRole }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
