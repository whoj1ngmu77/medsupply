import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FormError, Input, Modal, PageHeader, Select,
         Toolbar, useForm } from '../components/form'

const EMPTY = { warehouse_id: 1, medicine_id: 1, batch_number: '',
                qty_on_hand: 0, mfg_date: '', expiry_date: '', unit_cost: '' }

export default function Inventory() {
  const { can } = useAuth()
  const [tab, setTab] = useState('batches')
  const [wh, setWh] = useState('')
  const [med, setMed] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (wh) qs.set('warehouse_id', wh)
  if (med) qs.set('medicine_id', med)

  const { data, loading, error, reload } = useFetch(
    `/inventory?${qs}`, [wh, med, offset])
  const expiring = useFetch('/inventory/expiring?limit=50')
  const available = useFetch(
    `/inventory/available?limit=50${med ? `&medicine_id=${med}` : ''}`, [med])
  const meds = useFetch('/medicines?limit=200')
  const whs = useFetch('/warehouses?limit=200')
  const form = useForm(EMPTY)

  const medMap = {}
  ;(meds.data?.items || []).forEach((m) => { medMap[m.medicine_id] = m.name })
  const whMap = {}
  ;(whs.data?.items || []).forEach((w) => { whMap[w.warehouse_id] = w.name })

  const save = form.submit(async (v) => {
    const body = { ...v }
    if (!body.mfg_date) delete body.mfg_date
    if (body.unit_cost === '') delete body.unit_cost
    await api.post('/inventory', body)
    setModal(null)
    form.reset()
    reload()
  })

  const batchCols = [
    { key: 'batch_id', label: 'ID' },
    { key: 'batch_number', label: 'Batch' },
    { key: 'warehouse', label: 'Warehouse',
      render: (r) => whMap[r.warehouse_id] || r.warehouse_id },
    { key: 'medicine', label: 'Medicine',
      render: (r) => medMap[r.medicine_id] || r.medicine_id },
    { key: 'qty_on_hand', label: 'On hand',
      render: (r) => r.qty_on_hand.toLocaleString() },
    { key: 'qty_reserved', label: 'Reserved',
      render: (r) => (
        <span className={r.qty_reserved > 0 ? 'text-amber-400' : ''}>
          {r.qty_reserved.toLocaleString()}
        </span>
      ) },
    { key: 'available', label: 'Available',
      render: (r) => (
        <span className="text-emerald-400">
          {(r.qty_on_hand - r.qty_reserved).toLocaleString()}
        </span>
      ) },
    { key: 'expiry_date', label: 'Expiry' },
  ]

  const expiringCols = [
    { key: 'batch_number', label: 'Batch' },
    { key: 'medicine_name', label: 'Medicine' },
    { key: 'warehouse_name', label: 'Warehouse' },
    { key: 'qty_available', label: 'Available',
      render: (r) => Number(r.qty_available).toLocaleString() },
    { key: 'expiry_date', label: 'Expires' },
    { key: 'days_to_expiry', label: 'Days left',
      render: (r) => (
        <span className={r.days_to_expiry < 30 ? 'text-rose-400' : 'text-amber-400'}>
          {r.days_to_expiry}
        </span>
      ) },
  ]

  const availCols = [
    { key: 'batch_number', label: 'Batch' },
    { key: 'medicine_name', label: 'Medicine' },
    { key: 'criticality', label: 'Criticality',
      render: (r) => <Badge value={r.criticality} /> },
    { key: 'warehouse_name', label: 'Warehouse' },
    { key: 'qty_available', label: 'Available',
      render: (r) => Number(r.qty_available).toLocaleString() },
    { key: 'expiry_date', label: 'Expiry' },
  ]

  const TABS = [
    ['batches', 'All batches'],
    ['available', 'Available (FEFO order)'],
    ['expiring', 'Expiring soon'],
  ]

  return (
    <div>
      <PageHeader title="Inventory" subtitle="Batch-level stock across warehouses"
        action={can('ADMIN', 'WAREHOUSE_STAFF') && (
          <Btn onClick={() => setModal(true)}>+ New batch</Btn>
        )} />

      <div className="mb-4 flex gap-2">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`rounded-lg px-4 py-1.5 text-sm ${
              tab === k ? 'bg-emerald-500/10 text-emerald-300'
                        : 'text-slate-400 hover:bg-slate-800'}`}>
            {label}
          </button>
        ))}
      </div>

      <Card>
        {tab === 'batches' && (
          <>
            <Toolbar>
              <Select value={wh} onChange={(e) => { setWh(e.target.value); setOffset(0) }}
                options={[{ value: '', label: 'All warehouses' },
                  ...(whs.data?.items || []).map((w) => ({
                    value: w.warehouse_id, label: w.name }))]} />
              <Select value={med} onChange={(e) => { setMed(e.target.value); setOffset(0) }}
                options={[{ value: '', label: 'All medicines' },
                  ...(meds.data?.items || []).map((m) => ({
                    value: m.medicine_id, label: m.name }))]} />
            </Toolbar>
            {loading ? <Spinner /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
              <>
                <Table columns={batchCols} rows={data.items} empty="No batches" />
                <Pagination total={data.total} limit={limit} offset={offset}
                  onChange={setOffset} />
              </>
            )}
          </>
        )}

        {tab === 'available' && (
          <>
            <p className="mb-3 text-xs text-slate-500">
              Ordered by soonest expiry — the order the allocation engine consumes batches in.
            </p>
            <Toolbar>
              <Select value={med} onChange={(e) => setMed(e.target.value)}
                options={[{ value: '', label: 'All medicines' },
                  ...(meds.data?.items || []).map((m) => ({
                    value: m.medicine_id, label: m.name }))]} />
            </Toolbar>
            {available.loading ? <Spinner /> : (
              <Table columns={availCols} rows={available.data} empty="No available stock" />
            )}
          </>
        )}

        {tab === 'expiring' && (
          expiring.loading ? <Spinner /> : (
            <Table columns={expiringCols} rows={expiring.data}
              empty="Nothing expiring within 90 days" />
          )
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)} title="New inventory batch">
        <form onSubmit={save} className="space-y-4">
          <FormError message={form.error} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Warehouse">
              <Select value={form.values.warehouse_id}
                onChange={form.set('warehouse_id')}
                options={(whs.data?.items || []).map((w) => ({
                  value: w.warehouse_id, label: w.name }))} />
            </Field>
            <Field label="Medicine">
              <Select value={form.values.medicine_id}
                onChange={form.set('medicine_id')}
                options={(meds.data?.items || []).map((m) => ({
                  value: m.medicine_id, label: m.name }))} />
            </Field>
          </div>
          <Field label="Batch number" hint="Unique within the warehouse">
            <Input value={form.values.batch_number}
              onChange={form.set('batch_number')} required />
          </Field>
          <Field label="Quantity on hand">
            <Input type="number" min="0" value={form.values.qty_on_hand}
              onChange={form.set('qty_on_hand')} required />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Manufacture date">
              <Input type="date" value={form.values.mfg_date}
                onChange={form.set('mfg_date')} />
            </Field>
            <Field label="Expiry date">
              <Input type="date" value={form.values.expiry_date}
                onChange={form.set('expiry_date')} required />
            </Field>
          </div>
          <Field label="Unit cost">
            <Input type="number" step="0.01" min="0" value={form.values.unit_cost}
              onChange={form.set('unit_cost')} />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Btn type="button" variant="ghost" onClick={() => setModal(null)}>Cancel</Btn>
            <Btn type="submit" disabled={form.saving}>
              {form.saving ? 'Saving…' : 'Create batch'}
            </Btn>
          </div>
        </form>
      </Modal>
    </div>
  )
}
