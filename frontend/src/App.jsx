import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Hospitals from './pages/Hospitals'
import Medicines from './pages/Medicines'
import Warehouses from './pages/Warehouses'
import Inventory from './pages/Inventory'
import Requests from './pages/Requests'
import Shipments from './pages/Shipments'
import Suppliers from './pages/Suppliers'
import Incidents from './pages/Incidents'
import Overview from './pages/Overview'
import Replenishment from './pages/Replenishment'
import Analytics from './pages/Analytics'
import DbmsDemos from './pages/DbmsDemos'

function Shell() {
  const { user } = useAuth()
  if (!user) return <Login />

  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="overview" element={<Overview />} />
          <Route path="hospitals" element={<Hospitals />} />
          <Route path="medicines" element={<Medicines />} />
          <Route path="warehouses" element={<Warehouses />} />
          <Route path="inventory" element={<Inventory />} />
          <Route path="requests" element={<Requests />} />
          <Route path="shipments" element={<Shipments />} />
          <Route path="suppliers" element={<Suppliers />} />
          <Route path="replenishment" element={<Replenishment />} />
          <Route path="incidents" element={<Incidents />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="dbms" element={<DbmsDemos />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <Shell />
    </AuthProvider>
  )
}
