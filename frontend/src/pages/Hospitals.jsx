import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Pagination, Spinner, Table } from '../components/ui'
import { Btn, Field, FilterSelect, FormError, Input, Modal, PageHeader,
         SearchInput, Select, Toolbar, useForm } from '../components/form'

const LEVELS = ['NORMAL', 'ELEVATED', 'HIGH', 'CRITICAL']
const EMPTY = { name: '', reg_number: '', address: '', city: '', state: '',
                bed_capacity: 100, emergency_level: 'NORMAL', contact_phone: '' }

export default function Hospitals() {
  const { can } = useAuth()
  const [q, setQ] = useState('')
  const [level, setLevel] = useState('')
  const [offset, setOffset] = useState(0)
  const [modal, setModal] = useState(null)
  const limit = 25

  const qs = new URLSearchParams({ limit, offset })
  if (q) qs.set('q', q)
  if (level) qs.set('emergency_level', level)

  const { data, loading, error, reload } = useFetch(
    `/hospitals?${qs}`, [q, level, offset])
  const form = useForm(EMPTY)

  const open = (row) => {
    form.setValues(row ? { ...EMPTY, ...row } : EMPTY)
    setModal(row ? { mode: 'edit', id: row.hospital_id } : { mode: 'create' })
  }

  const save = form.submit(async (v) => {
    const body = { ...v }
    if (modal.mode === 'create') await api.post('/hospitals', body)
    else {
      delete body.reg_number
      delete body.hospital_id
      await api.patch(`/hospitals/${modal.id}`, body)
    }
    setModal(null)
    reload()
  })

  const remove = async (id) => {
    if (!confirm('Delete this hospital?')) return
    try { await api.del(`/hospitals/${id}`); reload() }
    catch (e) { alert(e.message) }
  }

  const columns = [
    { key: 'hospital_id', label: 'ID' },
    { key: 'name', label: 'Name' },
    { key: 'reg_number', label: 'Registration' },
    { key: 'city', label: 'City' },
    { key: 'bed_capacity', label: 'Beds',
      render: (r) => r.bed_capacity.toLocaleString() },
    { key: 'emergency_level', label: 'Level',
      render: (r) => <Badge value={r.emergency_level} /> },
    { key: 'actions', label: '',
      render: (r) => can('ADMIN', 'EMERGENCY_COORDINATOR', 'HOSPITAL_STAFF') && (
        <div className="flex gap-2">
          <button onClick={() => open(r)}
            className="text-xs text-sky-400 hover:underline">Edit</button>
          {can('ADMIN') && (
            <button onClick={() => remove(r.hospital_id)}
              className="text-xs text-rose-400 hover:underline">Delete</button>
          )}
        </div>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Hospitals" subtitle="Registered facilities"
        action={can('ADMIN') && (
          <Btn onClick={() => open(null)}>+ New hospital</Btn>
        )} />

      <Card>
        <Toolbar>
          <SearchInput value={q} placeholder="Search by name"
            onChange={(e) => { setQ(e.target.value); setOffset(0) }} />
          <FilterSelect value={level} options={LEVELS}
            placeholder="All emergency levels"
            onChange={(e) => { setLevel(e.target.value); setOffset(0) }} />
        </Toolbar>

        {loading ? <Spinner /> : error ? <ErrorBox message={error} onRetry={reload} /> : (
          <>
            <Table columns={columns} rows={data.items} empty="No hospitals" />
            <Pagination total={data.total} limit={limit} offset={offset}
              onChange={setOffset} />
          </>
        )}
      </Card>

      <Modal open={!!modal} onClose={() => setModal(null)}
        title={modal?.mode === 'edit' ? 'Edit hospital' : 'New hospital'}>
        <form onSubmit={save} className="space-y-4">
          <FormError message={form.error} />
          <Field label="Name">
            <Input value={form.values.name} onChange={form.set('name')} required />
          </Field>
          {modal?.mode === 'create' && (
            <Field label="Registration number" hint="Must be unique">
              <Input value={form.values.reg_number}
                onChange={form.set('reg_number')} required />
            </Field>
          )}
          <div className="grid grid-cols-2 gap-3">
            <Field label="City">
              <Input value={form.values.city} onChange={form.set('city')} required />
            </Field>
            <Field label="State">
              <Input value={form.values.state || ''} onChange={form.set('state')} />
            </Field>
          </div>
          <Field label="Address">
            <Input value={form.values.address || ''} onChange={form.set('address')} />
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Bed capacity">
              <Input type="number" min="1" value={form.values.bed_capacity}
                onChange={form.set('bed_capacity')} required />
            </Field>
            <Field label="Emergency level">
              <Select options={LEVELS} value={form.values.emergency_level}
                onChange={form.set('emergency_level')} />
            </Field>
          </div>
          <Field label="Contact phone">
            <Input value={form.values.contact_phone || ''}
              onChange={form.set('contact_phone')} />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Btn type="button" variant="ghost" onClick={() => setModal(null)}>
              Cancel
            </Btn>
            <Btn type="submit" disabled={form.saving}>
              {form.saving ? 'Saving…' : 'Save'}
            </Btn>
          </div>
        </form>
      </Modal>
    </div>
  )
}
