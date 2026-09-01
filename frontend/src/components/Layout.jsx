import { NavLink, Outlet } from 'react-router-dom'
import {
  Activity, AlertTriangle, Boxes, Building2, Database, FlaskConical,
  LayoutDashboard, LogOut, Package, Send, Truck, Users,
} from 'lucide-react'
import { useAuth } from '../context/AuthContext'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/hospitals', label: 'Hospitals', icon: Building2 },
  { to: '/medicines', label: 'Medicines', icon: FlaskConical },
  { to: '/warehouses', label: 'Warehouses', icon: Boxes },
  { to: '/inventory', label: 'Inventory', icon: Package },
  { to: '/requests', label: 'Requests', icon: Send },
  { to: '/shipments', label: 'Shipments', icon: Truck },
  { to: '/suppliers', label: 'Suppliers', icon: Users },
  { to: '/incidents', label: 'Incidents', icon: AlertTriangle },
  { to: '/analytics', label: 'Analytics', icon: Activity },
  { to: '/dbms', label: 'DBMS Demos', icon: Database,
    roles: ['ADMIN', 'EMERGENCY_COORDINATOR'] },
]

export default function Layout() {
  const { user, logout, can } = useAuth()

  return (
    <div className="flex min-h-screen bg-slate-950 text-slate-100">
      <aside className="flex w-60 shrink-0 flex-col border-r border-slate-800 bg-slate-900/40">
        <div className="border-b border-slate-800 px-5 py-4">
          <h1 className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-xl font-bold text-transparent">
            MedSupply
          </h1>
          <p className="text-[11px] text-slate-500">BCSE302L</p>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto p-3">
          {NAV.filter((n) => !n.roles || can(...n.roles)).map(
            ({ to, label, icon: Icon, end }) => (
              <NavLink key={to} to={to} end={end}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                    isActive
                      ? 'bg-emerald-500/10 text-emerald-300'
                      : 'text-slate-400 hover:bg-slate-800/50 hover:text-slate-200'
                  }`}>
                <Icon size={16} />
                {label}
              </NavLink>
            ))}
        </nav>

        <div className="border-t border-slate-800 p-3">
          <div className="px-2 pb-2">
            <p className="text-sm text-slate-300">{user?.full_name || user?.username}</p>
            <p className="text-[11px] text-slate-500">
              {user?.role?.replace(/_/g, ' ')}
            </p>
          </div>
          <button onClick={logout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 hover:bg-slate-800/50 hover:text-rose-300">
            <LogOut size={16} /> Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-x-hidden p-8">
        <Outlet />
      </main>
    </div>
  )
}
