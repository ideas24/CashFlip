import { Outlet } from 'react-router-dom'
import { Sidebar } from './sidebar'

export function AppLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <main className="ml-60 min-h-screen transition-all duration-300">
        <Outlet />
      </main>
    </div>
  )
}
