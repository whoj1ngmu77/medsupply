import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FormError, Input, Modal, PageHeader, Toolbar,
         SearchInput, useForm } from '../components/form'

const EMPTY = { name: '', address: '', city: '', storage_capacity: 1000000 }

export default function Warehouses() {
  const { can } = useAuth()
  const [city, setCity] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (city) qs.set('city', city)

  const { data, loading, error, reload } = useFetch(
    `/warehouses?${qs}`, [city, offset])
  const util = useFetch('/warehouses/utilisation')
  const form = useForm(EMPTY)

  const utilMap = {}
  ;(util.data || []).forEach((u) => { utilMap[u.warehouse_id] = u })

  const open = (row) => {
    form.setValues(row ? { ...EMPTY, ...row } : EMPTY)
    setModal(row ? { mode: 'edit', id: row.warehouse_id } : { mode: 'create' })
  }

  const save = form.submit(async (v) => {
    const body = { ...v }
    delete body.warehouse_id
    if (modal.mode === 'create') await api.post('/warehouses', body)
    else await api.patch(`/warehouses/${modal.id}`, body)
    setModal(null)
    reload()
    util.reload()
  })

  const columns = [
    { key: 'warehouse_id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'city', label: 'City' },
    { key: 'storage_capacity', label: 'Capacity',
      render: (r) => r.storage_capacity.toLocaleString() },
    { key: 'util', label: 'Utilisation',
      render: (r) => {
        const u = utilMap[r.warehouse_id]
        if (!u) return '—'
        const pct = Number(u.utilisation_pct)
        const color = pct > 90 ? 'bg-rose-500' : pct > 70 ? 'bg-amber-500' : 'bg-emerald-500'
        return (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-20 overflow-hidden rounded-full bg-slate-800">
              <div className={`h-full ${color}`}
                style={{ width: `${Math.min(pct, 100)}%` }} />
            </div>
            <span className="text-xs text-slate-400">{pct}%</span>
          </div>
        )
      } },
    { key: 'batches', label: 'Batches',
      render: (r) => utilMap[r.warehouse_id]?.batch_count ?? '—' },
    { key: 'actions', label: '',
      render: (r) => can('ADMIN', 'WAREHOUSE_STAFF') && (
        <button onClick={() => open(r)}
          className="text-xs text-sky-400 hover:underline">Edit</button>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Warehouses" subtitle="Storage facilities and capacity"
        action={can('ADMIN') && <Btn onClick={() => open(null)}>+ New warehouse</Btn>} />

      <Card>
        <Toolbar>
          <SearchInput value={city} placeholder="Filter by city"
            onChange={(e) => { setCity(e.target.value); setOffset(0) }} />
        </Toolbar>

        {loading ? <Spinner /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
          <>
            <Table columns={columns} rows={data.items} empty="No warehouses" />
            <Pagination total={data.total} limit={limit} offset={offset}
              onChange={setOffset} />
          </>
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)}
        title={modal?.mode === 'edit' ? 'Edit warehouse' : 'New warehouse'}>
        <form onSubmit={save} className="space-y-4">
          <FormError message={form.error} />
          <Field label="Name">
            <Input value={form.values.name} onChange={form.set('name')} required />
          </Field>
          <Field label="City">
            <Input value={form.values.city} onChange={form.set('city')} required />
          </Field>
          <Field label="Address">
            <Input value={form.values.address || ''} onChange={form.set('address')} />
          </Field>
          <Field label="Storage capacity (units)">
            <Input type="number" min="1" value={form.values.storage_capacity}
              onChange={form.set('storage_capacity')} required />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Btn type="button" variant="ghost" onClick={() => setModal(null)}>Cancel</Btn>
            <Btn type="submit" disabled={form.saving}>
              {form.saving ? 'Saving…' : 'Save'}
            </Btn>
          </div>
        </form>
      </Modal>
    </div>
  )
}
