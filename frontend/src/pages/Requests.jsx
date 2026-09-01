import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FilterSelect, FormError, Input, Modal, PageHeader,
         Select, Toolbar, useForm } from '../components/form'

const PRIORITIES = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
const STATUSES = ['PENDING', 'PARTIAL', 'ALLOCATED', 'DISPATCHED',
                  'DELIVERED', 'REJECTED']
const EMPTY = { hospital_id: 1, medicine_id: 1, qty_requested: 100,
                priority: 'MEDIUM', required_by: '' }

export default function Requests() {
  const { can, user } = useAuth()
  const [tab, setTab] = useState('queue')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const [detail, setDetail] = useState(null)
  const [result, setResult] = useState(null)
  const [allocating, setAllocating] = useState(null)
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (status) qs.set('request_status', status)
  if (priority) qs.set('priority', priority)

  const list = useFetch(`/requests?${qs}`, [status, priority, offset])
  const queue = useFetch('/requests/queue?limit=50')
  const hosps = useFetch('/hospitals?limit=200')
  const meds = useFetch('/medicines?limit=200')
  const form = useForm(EMPTY)

  const hospMap = {}
  ;(hosps.data?.items || []).forEach((h) => { hospMap[h.hospital_id] = h.name })
  const medMap = {}
  ;(meds.data?.items || []).forEach((m) => { medMap[m.medicine_id] = m.name })

  const create = form.submit(async (v) => {
    const body = { ...v }
    if (!body.required_by) delete body.required_by
    await api.post('/requests', body)
    setModal(false)
    form.reset()
    list.reload()
    queue.reload()
  })

  const allocate = async (id) => {
    setAllocating(id)
    setResult(null)
    try {
      const r = await api.post(`/requests/${id}/allocate`)
      setResult({ ok: true, ...r })
      list.reload()
      queue.reload()
    } catch (e) {
      setResult({ ok: false, message: e.message })
    } finally {
      setAllocating(null)
    }
  }

  const openDetail = async (id) => {
    setDetail({ id, loading: true })
    try {
      const [allocations, events] = await Promise.all([
        api.get(`/requests/${id}/allocations`),
        api.get(`/requests/${id}/events`),
      ])
      setDetail({ id, allocations, events })
    } catch (e) {
      setDetail({ id, error: e.message })
    }
  }

  const queueCols = [
    { key: 'request_id', label: 'ID' },
    { key: 'hospital_name', label: 'Hospital' },
    { key: 'medicine_name', label: 'Medicine' },
    { key: 'qty_outstanding', label: 'Outstanding',
      render: (r) => Number(r.qty_outstanding).toLocaleString() },
    { key: 'priority', label: 'Priority',
      render: (r) => <Badge value={r.priority} /> },
    { key: 'request_status', label: 'Status',
      render: (r) => <Badge value={r.request_status} /> },
    { key: 'required_by', label: 'Required by',
      render: (r) => r.required_by ? String(r.required_by).slice(0, 10) : '—' },
    { key: 'actions', label: '',
      render: (r) => (
        <div className="flex gap-2">
          {can('ADMIN', 'EMERGENCY_COORDINATOR') && (
            <button onClick={() => allocate(r.request_id)}
              disabled={allocating === r.request_id}
              className="rounded bg-emerald-500/15 px-2 py-1 text-xs text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40">
              {allocating === r.request_id ? 'Allocating…' : 'Allocate'}
            </button>
          )}
          <button onClick={() => openDetail(r.request_id)}
            className="text-xs text-sky-400 hover:underline">Detail</button>
        </div>
      ) },
  ]

  const listCols = [
    { key: 'request_id', label: 'ID' },
    { key: 'hospital', label: 'Hospital',
      render: (r) => hospMap[r.hospital_id] || r.hospital_id },
    { key: 'medicine', label: 'Medicine',
      render: (r) => medMap[r.medicine_id] || r.medicine_id },
    { key: 'qty_requested', label: 'Requested',
      render: (r) => r.qty_requested.toLocaleString() },
    { key: 'qty_fulfilled', label: 'Fulfilled',
      render: (r) => r.qty_fulfilled.toLocaleString() },
    { key: 'priority', label: 'Priority',
      render: (r) => <Badge value={r.priority} /> },
    { key: 'request_status', label: 'Status',
      render: (r) => <Badge value={r.request_status} /> },
    { key: 'actions', label: '',
      render: (r) => (
        <button onClick={() => openDetail(r.request_id)}
          className="text-xs text-sky-400 hover:underline">Detail</button>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Emergency Requests"
        subtitle="Allocation runs as a single ACID transaction with row-level locking"
        action={can('ADMIN', 'EMERGENCY_COORDINATOR', 'HOSPITAL_STAFF') && (
          <Btn onClick={() => setModal(true)}>+ New request</Btn>
        )} />

      {result && (
        <div className={`mb-4 rounded-lg border p-4 text-sm ${
          result.ok ? 'border-emerald-800 bg-emerald-950/30 text-emerald-300'
                    : 'border-rose-800 bg-rose-950/30 text-rose-300'}`}>
          <div className="flex items-start justify-between">
            <div>
              <p className="font-medium">{result.message}</p>
              {result.ok && result.lines && (
                <ul className="mt-2 space-y-0.5 text-xs text-slate-400">
                  {result.lines.map((l) => (
                    <li key={l.batch_id}>
                      Batch {l.batch_number} (warehouse {l.warehouse_id}) ·
                      {' '}{l.qty_allocated} units · expires {l.expiry_date}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <button onClick={() => setResult(null)} className="text-slate-500">✕</button>
          </div>
        </div>
      )}

      <div className="mb-4 flex gap-2">
        {[['queue', 'Allocation queue'], ['all', 'All requests']].map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`rounded-lg px-4 py-1.5 text-sm ${
              tab === k ? 'bg-emerald-500/10 text-emerald-300'
                        : 'text-slate-400 hover:bg-slate-800'}`}>
            {l}
          </button>
        ))}
      </div>

      <Card>
        {tab === 'queue' ? (
          <>
            <p className="mb-3 text-xs text-slate-500">
              Open requests ordered by priority, then deadline. Allocation is FEFO.
            </p>
            {queue.loading ? <Spinner /> : queue.error
              ? <ErrorBox message={queue.error} onRetry={queue.reload} />
              : <Table columns={queueCols} rows={queue.data} empty="Queue is empty" />}
          </>
        ) : (
          <>
            <Toolbar>
              <FilterSelect value={status} options={STATUSES}
                placeholder="All statuses"
                onChange={(e) => { setStatus(e.target.value); setOffset(0) }} />
              <FilterSelect value={priority} options={PRIORITIES}
                placeholder="All priorities"
                onChange={(e) => { setPriority(e.target.value); setOffset(0) }} />
            </Toolbar>
            {list.loading ? <Spinner /> : list.error
              ? <ErrorBox message={list.error} onRetry={list.reload} /> : (
              <>
                <Table columns={listCols} rows={list.data.items} empty="No requests" />
                <Pagination total={list.data.total} limit={limit} offset={offset}
                  onChange={setOffset} />
              </>
            )}
          </>
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(false)} title="New emergency request">
        <form onSubmit={create} className="space-y-4">
          <FormError message={form.error} />
          <Field label="Hospital"
            hint={user?.role === 'HOSPITAL_STAFF'
              ? 'You may only raise requests for your own hospital' : undefined}>
            <Select value={form.values.hospital_id} onChange={form.set('hospital_id')}
              options={(hosps.data?.items || []).map((h) => ({
                value: h.hospital_id, label: h.name }))} />
          </Field>
          <Field label="Medicine">
            <Select value={form.values.medicine_id} onChange={form.set('medicine_id')}
              options={(meds.data?.items || []).map((m) => ({
                value: m.medicine_id, label: m.name }))} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Quantity">
              <Input type="number" min="1" value={form.values.qty_requested}
                onChange={form.set('qty_requested')} required />
            </Field>
            <Field label="Priority">
              <Select options={PRIORITIES} value={form.values.priority}
                onChange={form.set('priority')} />
            </Field>
          </div>
          <Field label="Required by">
            <Input type="datetime-local" value={form.values.required_by}
              onChange={form.set('required_by')} />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Btn type="button" variant="ghost" onClick={() => setModal(false)}>Cancel</Btn>
            <Btn type="submit" disabled={form.saving}>
              {form.saving ? 'Creating…' : 'Create request'}
            </Btn>
          </div>
        </form>
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} width="max-w-3xl"
        title={`Request #${detail?.id}`}>
        {detail?.loading ? <Spinner /> : detail?.error ? (
          <ErrorBox message={detail.error} />
        ) : detail && (
          <div className="space-y-5">
            <div>
              <h4 className="mb-2 text-sm font-medium text-slate-300">Allocations</h4>
              <Table empty="No allocations yet" rows={detail.allocations}
                columns={[
                  { key: 'allocation_id', label: 'ID' },
                  { key: 'batch_number', label: 'Batch' },
                  { key: 'warehouse_name', label: 'Warehouse' },
                  { key: 'qty_allocated', label: 'Qty' },
                  { key: 'expiry_date', label: 'Expiry' },
                  { key: 'allocation_status', label: 'Status',
                    render: (r) => <Badge value={r.allocation_status} /> },
                ]} />
            </div>
            <div>
              <h4 className="mb-2 text-sm font-medium text-slate-300">
                Audit trail
                <span className="ml-2 text-xs font-normal text-slate-500">
                  application-level log, not the WAL
                </span>
              </h4>
              <Table empty="No events" rows={detail.events}
                columns={[
                  { key: 'event_type', label: 'Event' },
                  { key: 'batch_id', label: 'Batch' },
                  { key: 'old_value', label: 'Before' },
                  { key: 'new_value', label: 'After' },
                  { key: 'txn_note', label: 'Note' },
                  { key: 'occurred_at', label: 'At',
                    render: (r) => String(r.occurred_at).slice(0, 19).replace('T', ' ') },
                ]} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
