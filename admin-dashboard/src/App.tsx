import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from '@/lib/auth'
import { AppLayout } from '@/components/layout/app-layout'
import LoginPage from '@/pages/login'
import DashboardPage from '@/pages/dashboard'
import PlayersPage from '@/pages/players'
import SessionsPage from '@/pages/sessions'
import TransactionsPage from '@/pages/transactions'
import FinancePage from '@/pages/finance'
import PartnersPage from '@/pages/partners'
import AnalyticsPage from '@/pages/analytics'
import RolesPage from '@/pages/roles'
import SettingsPage from '@/pages/settings'
import LiveActivityPage from '@/pages/live'

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="w-12 h-12 rounded-xl bg-primary/20 flex items-center justify-center text-primary font-bold text-xl mx-auto mb-3">
            CF
          </div>
          <p className="text-muted text-sm animate-pulse">Loading...</p>
        </div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route
            element={
              <ProtectedRoute>
                <AppLayout />
              </ProtectedRoute>
            }
          >
            <Route index element={<DashboardPage />} />
            <Route path="live" element={<LiveActivityPage />} />
            <Route path="players" element={<PlayersPage />} />
            <Route path="sessions" element={<SessionsPage />} />
            <Route path="transactions" element={<TransactionsPage />} />
            <Route path="finance" element={<FinancePage />} />
            <Route path="partners" element={<PartnersPage />} />
            <Route path="analytics" element={<AnalyticsPage />} />
            <Route path="roles" element={<RolesPage />} />
            <Route path="settings" element={<SettingsPage />} />
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  )
}
