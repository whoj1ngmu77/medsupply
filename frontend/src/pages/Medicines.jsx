import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FilterSelect, FormError, Input, Modal, PageHeader,
         SearchInput, Select, Toolbar, useForm } from '../components/form'

const CRIT = ['ROUTINE', 'ESSENTIAL', 'LIFE_SAVING']
const EMPTY = { name: '', generic_name: '', category_id: 1, manufacturer_id: 1,
                unit: 'tablet', criticality: 'ROUTINE', is_controlled: false,
                storage_temp: '' }

export default function Medicines() {
  const { can } = useAuth()
  const [q, setQ] = useState('')
  const [crit, setCrit] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (q) qs.set('q', q)
  if (crit) qs.set('criticality', crit)

  const { data, loading, error, reload } = useFetch(
    `/medicines?${qs}`, [q, crit, offset])
  const cats = useFetch('/medicines/categories')
  const mfrs = useFetch('/medicines/manufacturers')
  const form = useForm(EMPTY)

  const catMap = {}
  ;(cats.data || []).forEach((c) => { catMap[c.category_id] = c.name })

  const open = (row) => {
    form.setValues(row ? { ...EMPTY, ...row } : EMPTY)
    setModal(row ? { mode: 'edit', id: row.medicine_id } : { mode: 'create' })
  }

  const save = form.submit(async (v) => {
    const body = { ...v }
    delete body.medicine_id
    if (modal.mode === 'create') await api.post('/medicines', body)
    else await api.patch(`/medicines/${modal.id}`, body)
    setModal(null)
    reload()
  })

  const columns = [
    { key: 'medicine_id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'generic_name', label: 'Generic' },
    { key: 'category', label: 'Category',
      render: (r) => catMap[r.category_id] || r.category_id },
    { key: 'unit', label: 'Unit' },
    { key: 'criticality', label: 'Criticality',
      render: (r) => <Badge value={r.criticality} /> },
    { key: 'is_controlled', label: 'Controlled',
      render: (r) => r.is_controlled ? 'Yes' : 'No' },
    { key: 'actions', label: '',
      render: (r) => can('ADMIN') && (
        <button onClick={() => open(r)}
          className="text-xs text-sky-400 hover:underline">Edit</button>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Medicines" subtitle="Catalogue and criticality tiers"
        action={can('ADMIN') && <Btn onClick={() => open(null)}>+ New medicine</Btn>} />

      <Card>
        <Toolbar>
          <SearchInput value={q} placeholder="Search medicines"
            onChange={(e) => { setQ(e.target.value); setOffset(0) }} />
          <FilterSelect value={crit} options={CRIT}
            placeholder="All criticalities"
            onChange={(e) => { setCrit(e.target.value); setOffset(0) }} />
        </Toolbar>

        {loading ? <Spinner /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
          <>
            <Table columns={columns} rows={data.items} empty="No medicines" />
            <Pagination total={data.total} limit={limit} offset={offset}
              onChange={setOffset} />
          </>
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)}
        title={modal?.mode === 'edit' ? 'Edit medicine' : 'New medicine'}>
        <form onSubmit={save} className="space-y-4">
          <FormError message={form.error} />
          <Field label="Name">
            <Input value={form.values.name} onChange={form.set('name')} required />
          </Field>
          <Field label="Generic name">
            <Input value={form.values.generic_name || ''}
              onChange={form.set('generic_name')} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Category">
              <Select value={form.values.category_id}
                onChange={form.set('category_id')}
                options={(cats.data || []).map((c) => ({
                  value: c.category_id, label: c.name }))} />
            </Field>
            <Field label="Manufacturer">
              <Select value={form.values.manufacturer_id}
                onChange={form.set('manufacturer_id')}
                options={(mfrs.data || []).map((m) => ({
                  value: m.manufacturer_id, label: m.name }))} />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Unit">
              <Input value={form.values.unit} onChange={form.set('unit')} required />
            </Field>
            <Field label="Criticality">
              <Select options={CRIT} value={form.values.criticality}
                onChange={form.set('criticality')} />
            </Field>
          </div>
          <label className="flex items-center gap-2 text-sm text-slate-300">
            <input type="checkbox" checked={form.values.is_controlled}
              onChange={form.set('is_controlled')}
              className="rounded border-slate-700 bg-slate-950" />
            Controlled substance
          </label>
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
