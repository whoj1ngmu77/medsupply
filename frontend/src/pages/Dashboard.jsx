import {
  Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Pie, PieChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Spinner } from '../components/ui'

const PRIORITY_COLORS = {
  CRITICAL: '#f43f5e', HIGH: '#f59e0b', MEDIUM: '#0ea5e9', LOW: '#64748b',
}

const Kpi = ({ label, value, sub, accent = 'emerald' }) => (
  <Card>
    <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`mt-1 text-2xl font-semibold text-${accent}-300`}>
      {typeof value === 'number' ? value.toLocaleString() : value ?? '—'}
    </p>
    {sub && <p className="mt-0.5 text-xs text-slate-500">{sub}</p>}
  </Card>
)

const tooltipStyle = {
  contentStyle: {
    background: '#0f172a', border: '1px solid #1e293b',
    borderRadius: 8, fontSize: 12,
  },
}

export default function Dashboard() {
  const { data, loading, error, reload } = useFetch('/analytics/overview')

  if (loading) return <Spinner label="Loading dashboard" />
  if (error) return <ErrorBox message={error} onRetry={reload} />

  const k = data.kpis

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold">Dashboard</h2>
        <p className="text-sm text-slate-400">
          Live figures from PostgreSQL views and MongoDB aggregation
        </p>
      </div>

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Hospitals" value={k.total_hospitals} />
        <Kpi label="Warehouses" value={k.total_warehouses} />
        <Kpi label="Units available" value={k.units_available} accent="cyan" />
        <Kpi label="Critical shortages" value={k.critical_shortages} accent="rose" />
        <Kpi label="Pending requests" value={k.pending_requests} accent="amber" />
        <Kpi label="Allocated" value={k.allocated_requests} accent="sky" />
        <Kpi label="In transit" value={k.in_transit_requests} accent="violet" />
        <Kpi label="Active incidents" value={k.active_incidents} accent="rose"
             sub="MongoDB" />
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Request volume · last 30 days
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <AreaChart data={data.request_trend}>
              <defs>
                <linearGradient id="g1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#10b981" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#10b981" stopOpacity={0} />
                </linearGradient>
                <linearGradient id="g2" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#f43f5e" stopOpacity={0.5} />
                  <stop offset="100%" stopColor="#f43f5e" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="day" stroke="#475569" fontSize={11}
                tickFormatter={(d) => String(d).slice(5)} />
              <YAxis stroke="#475569" fontSize={11} />
              <Tooltip {...tooltipStyle} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
              <Area type="monotone" dataKey="requests" stroke="#10b981"
                fill="url(#g1)" name="All requests" />
              <Area type="monotone" dataKey="critical" stroke="#f43f5e"
                fill="url(#g2)" name="Critical" />
            </AreaChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Requests by priority
          </h3>
          <ResponsiveContainer width="100%" height={240}>
            <PieChart>
              <Pie data={data.priority_breakdown} dataKey="total"
                nameKey="priority" cx="50%" cy="50%" outerRadius={80}
                label={(e) => e.priority}>
                {data.priority_breakdown.map((e) => (
                  <Cell key={e.priority} fill={PRIORITY_COLORS[e.priority]} />
                ))}
              </Pie>
              <Tooltip {...tooltipStyle} />
            </PieChart>
          </ResponsiveContainer>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Available stock by category
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={data.stock_by_category} layout="vertical"
              margin={{ left: 30 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis type="number" stroke="#475569" fontSize={11}
                tickFormatter={(v) => `${(v / 1e6).toFixed(0)}M`} />
              <YAxis type="category" dataKey="category_name" stroke="#475569"
                fontSize={11} width={100} />
              <Tooltip {...tooltipStyle}
                formatter={(v) => v.toLocaleString()} />
              <Bar dataKey="units_available" fill="#06b6d4" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Critical shortages
          </h3>
          {data.critical_shortages.length === 0 ? (
            <p className="py-12 text-center text-sm text-slate-500">
              No critical shortages
            </p>
          ) : (
            <div className="space-y-2">
              {data.critical_shortages.map((s) => (
                <div key={s.medicine_name}
                  className="flex items-center justify-between rounded-lg bg-slate-800/40 px-3 py-2">
                  <div>
                    <p className="text-sm text-slate-200">{s.medicine_name}</p>
                    <p className="text-xs text-slate-500">
                      {s.open_requests} open requests
                    </p>
                  </div>
                  <Badge value={s.total_available < 100 ? 'OUT_OF_STOCK' : 'LOW_STOCK'} />
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  )
}
