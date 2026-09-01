import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Spinner, Table } from '../components/ui'
import { Btn, FilterSelect, PageHeader, Toolbar } from '../components/form'

const STATUSES = ['PREPARING', 'IN_TRANSIT', 'DELIVERED', 'FAILED']

export default function Shipments() {
  const { can } = useAuth()
  const [status, setStatus] = useState('')
  const [busy, setBusy] = useState(null)
  const [msg, setMsg] = useState(null)

  const tracking = useFetch('/shipments/tracking?limit=100')

  const act = async (id, action) => {
    setBusy(id)
    setMsg(null)
    try {
      const r = await api.post(`/shipments/${id}/${action}`)
      setMsg({ ok: true, text: r.message })
      tracking.reload()
    } catch (e) {
      setMsg({ ok: false, text: e.message })
    } finally {
      setBusy(null)
    }
  }

  const rows = (tracking.data || []).filter(
    (r) => !status || r.delivery_status === status)

  const columns = [
    { key: 'shipment_id', label: 'ID' },
    { key: 'medicine_name', label: 'Medicine' },
    { key: 'qty_allocated', label: 'Qty',
      render: (r) => Number(r.qty_allocated).toLocaleString() },
    { key: 'warehouse_name', label: 'From' },
    { key: 'hospital_name', label: 'To' },
    { key: 'priority', label: 'Priority',
      render: (r) => <Badge value={r.priority} /> },
    { key: 'delivery_status', label: 'Status',
      render: (r) => <Badge value={r.delivery_status} /> },
    { key: 'vehicle_number', label: 'Vehicle' },
    { key: 'actions', label: '',
      render: (r) => can('ADMIN', 'WAREHOUSE_STAFF', 'EMERGENCY_COORDINATOR') && (
        <div className="flex gap-2">
          {r.delivery_status === 'PREPARING' && (
            <button onClick={() => act(r.shipment_id, 'dispatch')}
              disabled={busy === r.shipment_id}
              className="rounded bg-violet-500/15 px-2 py-1 text-xs text-violet-300 hover:bg-violet-500/25 disabled:opacity-40">
              Dispatch
            </button>
          )}
          {r.delivery_status === 'IN_TRANSIT' && (
            <button onClick={() => act(r.shipment_id, 'deliver')}
              disabled={busy === r.shipment_id}
              className="rounded bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40">
              Confirm delivery
            </button>
          )}
        </div>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Shipments"
        subtitle="Stock leaves inventory only when delivery is confirmed" />

      {msg && (
        <div className={`mb-4 rounded-lg border p-3 text-sm ${
          msg.ok ? 'border-emerald-800 bg-emerald-950/30 text-emerald-300'
                 : 'border-rose-800 bg-rose-950/30 text-rose-300'}`}>
          {msg.text}
        </div>
      )}

      <Card>
        <Toolbar>
          <FilterSelect value={status} options={STATUSES}
            placeholder="All statuses"
            onChange={(e) => setStatus(e.target.value)} />
          <span className="text-xs text-slate-500">
            PREPARING → dispatch → IN_TRANSIT → deliver → DELIVERED
            (qty_on_hand and qty_reserved decrement together at delivery)
          </span>
        </Toolbar>

        {tracking.loading ? <Spinner /> : tracking.error
          ? <ErrorBox message={tracking.error} onRetry={tracking.reload} />
          : <Table columns={columns} rows={rows} empty="No shipments yet" />}
      </Card>
    </div>
  )
}
