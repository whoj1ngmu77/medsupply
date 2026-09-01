import { useState } from 'react'
import { api } from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useFetch } from '../hooks/useFetch'
import { Badge, Card, ErrorBox, Spinner, Table } from '../components/ui'
import { Btn, Field, FilterSelect, FormError, Input, Modal, PageHeader,
         SearchInput, Select, Toolbar, useForm } from '../components/form'

const TYPES = ['FLOOD', 'CHEMICAL_SPILL', 'MASS_CASUALTY',
               'DISEASE_OUTBREAK', 'FIRE', 'EARTHQUAKE', 'OTHER']
const SEVERITIES = ['LOW', 'MODERATE', 'HIGH', 'SEVERE', 'CATASTROPHIC']
const EMPTY = { incident_type: 'FLOOD', title: '', severity: 'MODERATE',
                city: '', details_json: '{\n  "field": "value"\n}' }

export default function Incidents() {
  const { can } = useAuth()
  const [type, setType] = useState('')
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState(false)
  const [detail, setDetail] = useState(null)

  const qs = new URLSearchParams({ limit: 50 })
  if (type) qs.set('incident_type', type)
  if (search) qs.set('search', search)

  const list = useFetch(`/incidents?${qs}`, [type, search])
  const variation = useFetch('/incidents/schema-variation')
  const form = useForm(EMPTY)

  const create = form.submit(async (v) => {
    let details = {}
    try { details = JSON.parse(v.details_json) }
    catch { throw new Error('Details must be valid JSON') }

    await api.post('/incidents', {
      incident_type: v.incident_type,
      title: v.title,
      severity: v.severity,
      location: v.city ? { city: v.city } : {},
      affected_hospital_ids: [],
      details,
      tags: [],
    })
    setModal(false)
    form.reset()
    list.reload()
    variation.reload()
  })

  const openDetail = async (id) => {
    setDetail({ id, loading: true })
    try {
      const [doc, timeline, linked] = await Promise.all([
        api.get(`/incidents/${id}`),
        api.get(`/incidents/${id}/timeline`),
        api.get(`/incidents/${id}/linked-requests`),
      ])
      setDetail({ id, doc, timeline, linked })
    } catch (e) {
      setDetail({ id, error: e.message })
    }
  }

  const columns = [
    { key: 'title', label: 'Title' },
    { key: 'incident_type', label: 'Type',
      render: (r) => (
        <span className="rounded bg-slate-800 px-2 py-0.5 text-xs text-slate-300">
          {r.incident_type.replace(/_/g, ' ')}
        </span>
      ) },
    { key: 'severity', label: 'Severity',
      render: (r) => <Badge value={r.severity === 'CATASTROPHIC' ? 'CRITICAL'
        : r.severity === 'SEVERE' ? 'HIGH' : r.severity} /> },
    { key: 'city', label: 'City', render: (r) => r.location?.city || '—' },
    { key: 'fields', label: 'Detail fields',
      render: (r) => (
        <span className="text-xs text-slate-500">
          {Object.keys(r.details || {}).length} fields
        </span>
      ) },
    { key: 'created_at', label: 'Reported',
      render: (r) => String(r.created_at).slice(0, 10) },
    { key: 'actions', label: '',
      render: (r) => (
        <button onClick={() => openDetail(r.id)}
          className="text-xs text-sky-400 hover:underline">View</button>
      ) },
  ]

  return (
    <div>
      <PageHeader title="Emergency Incidents"
        subtitle="Stored in MongoDB — document shape varies by incident type"
        action={can('ADMIN', 'EMERGENCY_COORDINATOR') && (
          <Btn onClick={() => setModal(true)}>+ Report incident</Btn>
        )} />

      {variation.data && (
        <Card className="mb-4">
          <h3 className="mb-3 text-sm font-medium text-slate-300">
            Schema variation across types
          </h3>
          <div className="grid gap-2 md:grid-cols-2 lg:grid-cols-3">
            {Object.entries(variation.data.samples).map(([t, s]) => (
              <div key={t} className="rounded-lg bg-slate-800/40 p-3">
                <p className="text-xs font-medium text-emerald-300">
                  {t.replace(/_/g, ' ')}
                </p>
                <p className="mt-1 text-[11px] leading-relaxed text-slate-500">
                  {s.detail_fields.join(', ')}
                </p>
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            No two types share a field set — the architectural reason for MongoDB.
          </p>
        </Card>
      )}

      <Card>
        <Toolbar>
          <SearchInput value={search} placeholder="Text search"
            onChange={(e) => setSearch(e.target.value)} />
          <FilterSelect value={type} options={TYPES} placeholder="All types"
            onChange={(e) => setType(e.target.value)} />
        </Toolbar>

        {list.loading ? <Spinner /> : list.error
          ? <ErrorBox message={list.error} onRetry={list.reload} />
          : <Table columns={columns} rows={list.data.items} empty="No incidents" />}
      </Card>

      <Modal open={modal} onClose={() => setModal(false)} title="Report incident">
        <form onSubmit={create} className="space-y-4">
          <FormError message={form.error} />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Type">
              <Select options={TYPES} value={form.values.incident_type}
                onChange={form.set('incident_type')} />
            </Field>
            <Field label="Severity">
              <Select options={SEVERITIES} value={form.values.severity}
                onChange={form.set('severity')} />
            </Field>
          </div>
          <Field label="Title">
            <Input value={form.values.title} onChange={form.set('title')} required />
          </Field>
          <Field label="City">
            <Input value={form.values.city} onChange={form.set('city')} />
          </Field>
          <Field label="Details (JSON)"
            hint="Any shape you like — this is why the data lives in MongoDB">
            <textarea value={form.values.details_json}
              onChange={form.set('details_json')} rows={6}
              className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 font-mono text-xs text-slate-100 outline-none focus:border-emerald-600" />
          </Field>
          <div className="flex justify-end gap-2 pt-2">
            <Btn type="button" variant="ghost" onClick={() => setModal(false)}>Cancel</Btn>
            <Btn type="submit" disabled={form.saving}>
              {form.saving ? 'Saving…' : 'Report'}
            </Btn>
          </div>
        </form>
      </Modal>

      <Modal open={!!detail} onClose={() => setDetail(null)} width="max-w-3xl"
        title="Incident detail">
        {detail?.loading ? <Spinner /> : detail?.error ? (
          <ErrorBox message={detail.error} />
        ) : detail?.doc && (
          <div className="space-y-5">
            <div>
              <h4 className="text-lg text-slate-100">{detail.doc.title}</h4>
              <div className="mt-1 flex gap-2 text-xs text-slate-500">
                <span>{detail.doc.incident_type.replace(/_/g, ' ')}</span>
                <span>·</span>
                <span>{detail.doc.severity}</span>
                <span>·</span>
                <span>{detail.doc.location?.city}</span>
              </div>
            </div>

            <div>
              <h5 className="mb-2 text-sm font-medium text-slate-300">
                Type-specific details
              </h5>
              <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-400">
                {JSON.stringify(detail.doc.details, null, 2)}
              </pre>
            </div>

            {detail.timeline?.length > 0 && (
              <div>
                <h5 className="mb-2 text-sm font-medium text-slate-300">Timeline</h5>
                <div className="space-y-2">
                  {detail.timeline.map((t) => (
                    <div key={t.id} className="rounded-lg bg-slate-800/40 px-3 py-2">
                      <p className="text-sm text-slate-300">{t.note}</p>
                      <p className="text-[11px] text-slate-500">
                        {t.author} · {String(t.at).slice(0, 19).replace('T', ' ')}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <h5 className="mb-2 text-sm font-medium text-slate-300">
                Linked requests
                <span className="ml-2 text-xs font-normal text-slate-500">
                  application-layer join — no FK across the database boundary
                </span>
              </h5>
              <Table empty="No linked requests" rows={detail.linked?.requests || []}
                columns={[
                  { key: 'request_id', label: 'ID' },
                  { key: 'hospital_name', label: 'Hospital' },
                  { key: 'medicine_name', label: 'Medicine' },
                  { key: 'qty_requested', label: 'Qty' },
                  { key: 'request_status', label: 'Status',
                    render: (r) => <Badge value={r.request_status} /> },
                ]} />
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
