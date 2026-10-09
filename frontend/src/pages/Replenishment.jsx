import { useCallback, useEffect, useState } from 'react'
import { api } from '../api/client'
import { Card, Spinner, ErrorBox, Empty } from '../components/ui'

const STAGES = ['PENDING', 'SENT', 'CONFIRMED', 'SHIPPED', 'DELIVERED']

const STAGE_STYLE = {
  PENDING:   'bg-slate-500/15 text-slate-300 border-slate-500/30',
  SENT:      'bg-sky-500/15 text-sky-300 border-sky-500/30',
  CONFIRMED: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  SHIPPED:   'bg-amber-500/15 text-amber-300 border-amber-500/30',
  DELIVERED: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30',
  CANCELLED: 'bg-rose-500/15 text-rose-300 border-rose-500/30',
}

const DECISION_STYLE = {
  ORDERED: 'text-emerald-400',
  SKIPPED_ABOVE_THRESHOLD: 'text-slate-400',
  SKIPPED_ORDER_OPEN: 'text-sky-400',
  SKIPPED_NO_SUPPLIER: 'text-amber-400',
  SKIPPED_DISABLED: 'text-slate-500',
  FAILED: 'text-rose-400',
}

const num = (n) => (n ?? 0).toLocaleString()
const money = (n) => `₹${Math.round(n ?? 0).toLocaleString()}`
const clock = (t) => (t ? new Date(t).toLocaleTimeString() : '—')

const Pill = ({ status }) => (
  <span className={`inline-block rounded-md border px-2 py-0.5 text-[11px]
    font-medium tracking-wide ${STAGE_STYLE[status] || STAGE_STYLE.PENDING}`}>
    {status}
  </span>
)

const Kpi = ({ label, value, sub, accent = 'text-slate-100' }) => (
  <Card>
    <div className="text-[11px] uppercase tracking-widest text-slate-500">{label}</div>
    <div className={`mt-2 text-3xl font-semibold ${accent}`}>{value}</div>
    {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
  </Card>
)

export default function Replenishment() {
  const [tab, setTab] = useState('overview')
  const [live, setLive] = useState(true)
  const [busy, setBusy] = useState(null)
  const [flash, setFlash] = useState(null)

  const [stats, setStats] = useState(null)
  const [sched, setSched] = useState(null)
  const [orders, setOrders] = useState([])
  const [policies, setPolicies] = useState([])
  const [log, setLog] = useState([])
  const [notes, setNotes] = useState([])
  const [error, setError] = useState(null)
  const [loaded, setLoaded] = useState(false)

  const load = useCallback(async () => {
    try {
      const [s, sc, o, p, l, n] = await Promise.all([
        api.get('/replenishment/stats'),
        api.get('/replenishment/scheduler'),
        api.get('/replenishment/orders?limit=40'),
        api.get('/replenishment/policies?below_threshold_only=true&limit=40'),
        api.get('/replenishment/log?limit=40'),
        api.get('/replenishment/notifications?limit=25'),
      ])
      setStats(s); setSched(sc)
      setOrders(o.items || []); setPolicies(p.items || [])
      setLog(l.items || []); setNotes(n.items || [])
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoaded(true)
    }
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (!live) return
    const id = setInterval(load, 4000)
    return () => clearInterval(id)
  }, [live, load])

  const act = async (what, path) => {
    setBusy(what)
    try {
      const r = await api.post(path)
      setFlash(r.message ||
        `Advanced ${r.advanced} order(s), delivered ${r.delivered}`)
      await load()
    } catch (e) {
      setFlash(`Failed: ${e.message}`)
    } finally {
      setBusy(null)
      setTimeout(() => setFlash(null), 6000)
    }
  }

  if (!loaded) return <Spinner label="Loading replenishment" />
  if (error && !stats) return <ErrorBox message={error} onRetry={load} />

  const k = stats?.kpis || {}
  const byStatus = Object.fromEntries(
    (stats?.by_status || []).map((r) => [r.po_status, r.n]))

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold text-slate-100">
            Auto Stock-Up
          </h1>
          <p className="mt-1 text-sm text-slate-400">
            Warehouse stock below threshold raises purchase orders automatically
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setLive((v) => !v)}
            className={`rounded-lg border px-3 py-2 text-xs font-medium transition
              ${live ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300'
                     : 'border-slate-700 bg-slate-800/60 text-slate-400'}`}>
            <span className={`mr-2 inline-block h-2 w-2 rounded-full
              ${live ? 'animate-pulse bg-emerald-400' : 'bg-slate-600'}`} />
            {live ? 'Live' : 'Paused'}
          </button>
          <button
            disabled={busy}
            onClick={() => act('scan', '/replenishment/scan?limit=50')}
            className="rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2
              text-xs font-medium text-sky-300 transition hover:bg-sky-500/20
              disabled:opacity-40">
            {busy === 'scan' ? 'Scanning…' : 'Run scan now'}
          </button>
          <button
            disabled={busy}
            onClick={() => act('advance', '/replenishment/advance?limit=100')}
            className="rounded-lg border border-violet-500/40 bg-violet-500/10 px-3
              py-2 text-xs font-medium text-violet-300 transition
              hover:bg-violet-500/20 disabled:opacity-40">
            {busy === 'advance' ? 'Advancing…' : 'Advance orders'}
          </button>
        </div>
      </div>

      <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 px-4 py-2.5
        text-xs text-amber-300/90">
        <strong className="font-semibold">Simulated.</strong> No supplier is
        contacted — no email, no API call. Every order is flagged
        <code className="mx-1 rounded bg-amber-500/10 px-1">is_simulated</code>
        and moves through its lifecycle on simulated delays.
      </div>

      {flash && (
        <div className="rounded-lg border border-slate-700 bg-slate-800/60 px-4 py-2.5
          text-xs text-slate-300">{flash}</div>
      )}

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Kpi label="Active policies" value={num(k.active_policies)}
             sub="warehouse × medicine" />
        <Kpi label="Open orders" value={num(k.open_orders)}
             accent="text-amber-400" sub={`${num(k.total_orders)} total`} />
        <Kpi label="Auto-generated" value={num(k.auto_orders)}
             accent="text-emerald-400" sub="raised with no user action" />
        <Kpi label="Units replenished" value={num(k.units_replenished)}
             accent="text-sky-400" sub={money(k.total_value)} />
      </div>

      <Card>
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-200">Order pipeline</h2>
          <span className="text-xs text-slate-500">
            {num(k.delivered_orders)} delivered
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {STAGES.map((s, i) => (
            <div key={s} className="flex items-center gap-2">
              <div className={`min-w-[110px] rounded-lg border px-3 py-2
                ${STAGE_STYLE[s]}`}>
                <div className="text-[10px] uppercase tracking-wider opacity-70">{s}</div>
                <div className="text-xl font-semibold">{num(byStatus[s])}</div>
              </div>
              {i < STAGES.length - 1 && (
                <span className="text-slate-600">→</span>
              )}
            </div>
          ))}
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-sm font-semibold text-slate-200">
          Scheduler
          <span className="ml-2 text-xs font-normal text-slate-500">
            this is what makes it automatic
          </span>
        </h2>
        <div className="grid grid-cols-2 gap-4 text-sm md:grid-cols-4">
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-500">Status</div>
            <div className={sched?.enabled ? 'text-emerald-400' : 'text-slate-500'}>
              {sched?.enabled ? 'Running' : 'Disabled'}
            </div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-500">Scan every</div>
            <div className="text-slate-200">{sched?.scan_interval}s</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-500">Last scan</div>
            <div className="text-slate-200">{clock(sched?.last_scan_at)}</div>
          </div>
          <div>
            <div className="text-[11px] uppercase tracking-wider text-slate-500">Auto orders</div>
            <div className="text-emerald-400">{num(sched?.total_auto_orders)}</div>
          </div>
        </div>
      </Card>

      <div className="flex gap-1 border-b border-slate-800">
        {[
          ['overview', `Orders (${orders.length})`],
          ['policies', `Below threshold (${policies.length})`],
          ['log', `Scan log (${log.length})`],
          ['notes', `Notifications (${notes.length})`],
        ].map(([id, label]) => (
          <button key={id} onClick={() => setTab(id)}
            className={`px-4 py-2 text-sm transition
              ${tab === id
                ? 'border-b-2 border-emerald-400 font-medium text-emerald-300'
                : 'text-slate-500 hover:text-slate-300'}`}>
            {label}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        orders.length === 0 ? <Empty message="No purchase orders yet" /> : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="py-2 pr-4">PO</th>
                  <th className="py-2 pr-4">Status</th>
                  <th className="py-2 pr-4">Trigger</th>
                  <th className="py-2 pr-4">Medicine</th>
                  <th className="py-2 pr-4">Warehouse</th>
                  <th className="py-2 pr-4">Supplier</th>
                  <th className="py-2 pr-4 text-right">Qty</th>
                  <th className="py-2 text-right">Value</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {orders.map((o) => (
                  <tr key={o.po_id} className="border-b border-slate-800/50">
                    <td className="py-2 pr-4 font-mono text-xs">{o.po_number}</td>
                    <td className="py-2 pr-4"><Pill status={o.po_status} /></td>
                    <td className="py-2 pr-4">
                      <span className={o.triggered_by === 'AUTO'
                        ? 'text-emerald-400' : 'text-slate-500'}>
                        {o.triggered_by}
                      </span>
                    </td>
                    <td className="py-2 pr-4">{o.medicine_name}</td>
                    <td className="py-2 pr-4 text-slate-400">{o.warehouse_name}</td>
                    <td className="py-2 pr-4 text-slate-400">{o.supplier_name}</td>
                    <td className="py-2 pr-4 text-right">{num(o.qty_ordered)}</td>
                    <td className="py-2 text-right text-slate-400">{money(o.total_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>)
      )}

      {tab === 'policies' && (
        policies.length === 0
          ? <Empty message="Every warehouse is above its threshold" />
          : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-slate-500">
                <tr className="border-b border-slate-800">
                  <th className="py-2 pr-4">Warehouse</th>
                  <th className="py-2 pr-4">Medicine</th>
                  <th className="py-2 pr-4">Criticality</th>
                  <th className="py-2 pr-4 text-right">Available</th>
                  <th className="py-2 pr-4 text-right">Threshold</th>
                  <th className="py-2 pr-4 text-right">Target</th>
                  <th className="py-2 pr-4 text-right">On order</th>
                  <th className="py-2">Supplier</th>
                </tr>
              </thead>
              <tbody className="text-slate-300">
                {policies.map((p) => (
                  <tr key={p.policy_id} className="border-b border-slate-800/50">
                    <td className="py-2 pr-4 text-slate-400">{p.warehouse_name}</td>
                    <td className="py-2 pr-4">{p.medicine_name}</td>
                    <td className="py-2 pr-4 text-xs text-slate-500">{p.criticality}</td>
                    <td className="py-2 pr-4 text-right text-rose-400">
                      {num(p.available)}
                    </td>
                    <td className="py-2 pr-4 text-right">{num(p.min_threshold)}</td>
                    <td className="py-2 pr-4 text-right text-slate-400">
                      {num(p.target_level)}
                    </td>
                    <td className="py-2 pr-4 text-right text-sky-400">
                      {num(p.qty_on_order)}
                    </td>
                    <td className="py-2 text-slate-400">{p.preferred_supplier}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>)
      )}

      {tab === 'log' && (
        log.length === 0 ? <Empty message="No scans recorded" /> : (
        <Card>
          <div className="space-y-1.5 font-mono text-xs">
            {log.map((l) => (
              <div key={l.log_id} className="flex flex-wrap items-baseline gap-x-3
                border-b border-slate-800/40 py-1.5">
                <span className="text-slate-600">{clock(l.occurred_at)}</span>
                <span className={DECISION_STYLE[l.decision] || 'text-slate-400'}>
                  {l.decision}
                </span>
                <span className="text-slate-300">{l.medicine_name}</span>
                <span className="text-slate-500">{l.warehouse_name}</span>
                {l.qty_ordered && (
                  <span className="text-slate-400">qty {num(l.qty_ordered)}</span>
                )}
                <span className="text-slate-600">
                  avail {num(l.qty_available)} / min {num(l.min_threshold)}
                </span>
                {l.po_number && <span className="text-emerald-500">{l.po_number}</span>}
              </div>
            ))}
          </div>
        </Card>)
      )}

      {tab === 'notes' && (
        notes.length === 0 ? <Empty message="No notifications" /> : (
        <div className="space-y-2">
          {notes.map((n) => (
            <Card key={n.notification_id}>
              <div className="flex items-start justify-between gap-4">
                <div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold ${
                      n.severity === 'CRITICAL' ? 'text-rose-400'
                      : n.severity === 'WARNING' ? 'text-amber-400'
                      : 'text-sky-400'}`}>{n.severity}</span>
                    <span className="text-sm text-slate-200">{n.title}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-500">{n.body}</p>
                </div>
                <span className="shrink-0 text-xs text-slate-600">
                  {clock(n.created_at)}
                </span>
              </div>
            </Card>
          ))}
        </div>)
      )}
    </div>
  )
}
