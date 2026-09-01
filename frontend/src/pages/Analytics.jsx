import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart,
         Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Spinner, Table } from '../components/ui'
import { PageHeader } from '../components/form'

const tip = { contentStyle: { background: '#0f172a', border: '1px solid #1e293b',
                              borderRadius: 8, fontSize: 12 } }
const EXPIRY_COLORS = ['#f43f5e', '#f97316', '#f59e0b', '#eab308',
                       '#84cc16', '#10b981']

export default function Analytics() {
  const demand = useFetch('/analytics/medicine-demand')
  const expiry = useFetch('/analytics/expiry-timeline')
  const hospitals = useFetch('/analytics/hospital-activity?limit=10')
  const trend = useFetch('/analytics/requests-by-day?days=90')
  const incidents = useFetch('/analytics/incident-summary')

  if (demand.loading) return <Spinner label="Loading analytics" />
  if (demand.error) return <ErrorBox message={demand.error} onRetry={demand.reload} />

  return (
    <div className="space-y-6">
      <PageHeader title="Analytics"
        subtitle="Aggregations over PostgreSQL views and MongoDB pipelines" />

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Batches by time to expiry
          </h3>
          <ResponsiveContainer width="100%" height={260}>
            <BarChart data={expiry.data || []}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
              <XAxis dataKey="bucket" stroke="#475569" fontSize={11} />
              <YAxis stroke="#475569" fontSize={11} />
              <Tooltip {...tip} formatter={(v) => Number(v).toLocaleString()} />
              <Bar dataKey="batches" radius={[4, 4, 0, 0]}>
                {(expiry.data || []).map((e, i) => (
                  <Cell key={e.bucket} fill={EXPIRY_COLORS[i % EXPIRY_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Card>

        <Card>
          <h3 className="mb-4 text-sm font-medium text-slate-300">
            Incidents by type · MongoDB
          </h3>
          {incidents.loading ? <Spinner /> : (
            <ResponsiveContainer width="100%" height={260}>
              <PieChart>
                <Pie data={incidents.data.by_type} dataKey="count" nameKey="type"
                  cx="50%" cy="50%" outerRadius={85}
                  label={(e) => e.type.replace(/_/g, ' ')}>
                  {incidents.data.by_type.map((e, i) => (
                    <Cell key={e.type} fill={EXPIRY_COLORS[i % EXPIRY_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip {...tip} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      <Card>
        <h3 className="mb-4 text-sm font-medium text-slate-300">
          Request volume · last 90 days
        </h3>
        <ResponsiveContainer width="100%" height={240}>
          <LineChart data={trend.data || []}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis dataKey="day" stroke="#475569" fontSize={11}
              tickFormatter={(d) => String(d).slice(5)} />
            <YAxis stroke="#475569" fontSize={11} />
            <Tooltip {...tip} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Line type="monotone" dataKey="requests" stroke="#10b981" dot={false}
              name="All requests" />
            <Line type="monotone" dataKey="critical" stroke="#f43f5e" dot={false}
              name="Critical" />
            <Line type="monotone" dataKey="delivered" stroke="#0ea5e9" dot={false}
              name="Delivered" />
          </LineChart>
        </ResponsiveContainer>
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-medium text-slate-300">
          Demand vs supply by medicine
        </h3>
        <Table rows={demand.data} empty="No data"
          columns={[
            { key: 'medicine_name', label: 'Medicine' },
            { key: 'criticality', label: 'Criticality',
              render: (r) => <Badge value={r.criticality} /> },
            { key: 'request_count', label: 'Requests' },
            { key: 'total_requested', label: 'Requested',
              render: (r) => Number(r.total_requested).toLocaleString() },
            { key: 'total_fulfilled', label: 'Fulfilled',
              render: (r) => Number(r.total_fulfilled).toLocaleString() },
            { key: 'fulfilment_rate_pct', label: 'Fulfilment',
              render: (r) => r.fulfilment_rate_pct != null
                ? `${r.fulfilment_rate_pct}%` : '—' },
            { key: 'available', label: 'Available',
              render: (r) => Number(r.available).toLocaleString() },
            { key: 'stock_status', label: 'Stock',
              render: (r) => <Badge value={r.stock_status === 'HEALTHY' ? 'HEALTHY'
                : r.stock_status === 'OUT_OF_STOCK' ? 'OUT_OF_STOCK' : 'LOW_STOCK'} /> },
          ]} />
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-medium text-slate-300">
          Most active hospitals
          <span className="ml-2 text-xs font-normal text-slate-500">
            ranked with RANK() — ties share a rank
          </span>
        </h3>
        {hospitals.loading ? <Spinner /> : (
          <Table rows={hospitals.data} empty="No data"
            columns={[
              { key: 'activity_rank', label: 'Rank' },
              { key: 'hospital_name', label: 'Hospital' },
              { key: 'city', label: 'City' },
              { key: 'emergency_level', label: 'Level',
                render: (r) => <Badge value={r.emergency_level} /> },
              { key: 'total_requests', label: 'Requests' },
              { key: 'open_requests', label: 'Open' },
              { key: 'units_received', label: 'Units received',
                render: (r) => Number(r.units_received).toLocaleString() },
            ]} />
        )}
      </Card>
    </div>
  )
}
