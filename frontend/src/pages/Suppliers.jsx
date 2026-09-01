import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FormError, Input, Modal, PageHeader, SearchInput,
         Toolbar, useForm } from '../components/form'

const EMPTY = { name: '', gst_number: '', contact_email: '',
                contact_phone: '', rating: 4.0 }

export default function Suppliers() {
  const { can } = useAuth()
  const [q, setQ] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const [tab, setTab] = useState('list')
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (q) qs.set('q', q)

  const { data, loading, error, reload } = useFetch(`/suppliers?${qs}`, [q, offset])
  const history = useFetch('/consignments/history?limit=20')
  const form = useForm(EMPTY)

  const open = (row) => {
    form.setValues(row ? { ...EMPTY, ...row } : EMPTY)
    setModal(row ? { mode: 'edit', id: row.supplier_id } : { mode: 'create' })
  }

  const save = form.submit(async (v) => {
    const body = { ...v }
    delete body.supplier_id
    if (modal.mode === 'create') await api.post('/suppliers', body)
    else { delete body.gst_number; await api.patch(`/suppliers/${modal.id}`, body) }
    setModal(null)
    reload()
  })

  const columns = [
    { key: 'supplier_id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'gst_number', label: 'GST' },
    { key: 'contact_email', label: 'Email' },
    { key: 'rating', label: 'Rating',
      render: (r) => r.rating ? `${'★'.repeat(Math.round(r.rating))} ${r.rating}` : '—' },
    { key: 'actions', label: '',
      render: (r) => can('ADMIN') && (
        <button onClick={() => open(r)}
          className="text-xs text-sky-400 hover:underline">Edit</button>
      ) },
  ]

  const histCols = [
    { key: 'supplier_name', label: 'Supplier' },
    { key: 'consignments', label: 'Consignments' },
    { key: 'total_units', label: 'Units supplied',
      render: (r) => Number(r.total_units).toLocaleString() },
    { key: 'avg_price', label: 'Avg price',
      render: (r) => `₹${r.avg_price}` },
    { key: 'last_supply', label: 'Last supply' },
  ]

  return (
    <div>
      <PageHeader title="Suppliers" subtitle="Vendors and supply performance"
        action={can('ADMIN') && <Btn onClick={() => open(null)}>+ New supplier</Btn>} />

      <div className="mb-4 flex gap-2">
        {['list', 'performance'].map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded-lg px-4 py-1.5 text-sm ${
              tab === t ? 'bg-emerald-500/10 text-emerald-300'
                        : 'text-slate-400 hover:bg-slate-800'}`}>
            {t === 'list' ? 'Suppliers' : 'Supply performance'}
          </button>
        ))}
      </div>

      <Card>
        {tab === 'list' ? (
          <>
            <Toolbar>
              <SearchInput value={q} placeholder="Search suppliers"
                onChange={(e) => { setQ(e.target.value); setOffset(0) }} />
            </Toolbar>
            {loading ? <Spinner /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
              <>
                <Table columns={columns} rows={data.items} empty="No suppliers" />
                <Pagination total={data.total} limit={limit} offset={offset}
                  onChange={setOffset} />
              </>
            )}
          </>
        ) : history.loading ? <Spinner /> : (
          <Table columns={histCols} rows={history.data} empty="No supply history" />
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)}
        title={modal?.mode === 'edit' ? 'Edit supplier' : 'New supplier'}>
        <form onSubmit={save} className="space-y-4">
          <FormError message={form.error} />
          <Field label="Name">
            <Input value={form.values.name} onChange={form.set('name')} required />
          </Field>
          {modal?.mode === 'create' && (
            <Field label="GST number" hint="15 characters, must be unique">
              <Input value={form.values.gst_number}
                onChange={form.set('gst_number')} required minLength={15} />
            </Field>
          )}
          <Field label="Contact email">
            <Input type="email" value={form.values.contact_email || ''}
              onChange={form.set('contact_email')} />
          </Field>
          <Field label="Contact phone">
            <Input value={form.values.contact_phone || ''}
              onChange={form.set('contact_phone')} />
          </Field>
          <Field label="Rating (0–5)">
            <Input type="number" step="0.1" min="0" max="5"
              value={form.values.rating ?? ''} onChange={form.set('rating')} />
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
