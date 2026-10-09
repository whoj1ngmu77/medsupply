import { useEffect, useState } from 'react'
import { Card } from '../components/ui'

const CSS = `
@keyframes ms-flow { to { stroke-dashoffset: -200; } }
@keyframes ms-pulse { 0%,100% { opacity:.25 } 50% { opacity:1 } }
@keyframes ms-rise { from { opacity:0; transform: translateY(8px) } to { opacity:1; transform:none } }
.ms-flow { stroke-dasharray: 6 10; animation: ms-flow 3s linear infinite; }
.ms-pulse { animation: ms-pulse 2.4s ease-in-out infinite; }
.ms-rise { animation: ms-rise .5s ease-out both; }
`

const Section = ({ eyebrow, title, children }) => (
  <section className="space-y-4">
    <div>
      {eyebrow && (
        <div className="text-[11px] font-medium uppercase tracking-[0.2em] text-emerald-400/70">
          {eyebrow}
        </div>
      )}
      <h2 className="mt-1 text-xl font-semibold text-slate-100">{title}</h2>
    </div>
    {children}
  </section>
)

/* ---------------------------------------------------------------- */
/* 1. The two loops — supply in, demand out                          */
/* ---------------------------------------------------------------- */
function PipelineDiagram() {
  const box = (x, y, w, h, fill, stroke) => (
    <rect x={x} y={y} width={w} height={h} rx="10"
          fill={fill} stroke={stroke} strokeWidth="1.5" />
  )
  return (
    <svg viewBox="0 0 860 300" className="w-full">
      <defs>
        <marker id="ms-arrow" markerWidth="9" markerHeight="9"
                refX="8" refY="4.5" orient="auto">
          <path d="M0,0 L9,4.5 L0,9 Z" fill="#64748b" />
        </marker>
      </defs>

      {box(40, 110, 150, 80, 'rgba(139,92,246,.10)', 'rgba(139,92,246,.45)')}
      <text x="115" y="143" textAnchor="middle" fill="#c4b5fd"
            fontSize="14" fontWeight="600">Suppliers</text>
      <text x="115" y="163" textAnchor="middle" fill="#64748b" fontSize="11">
        60 registered
      </text>

      {box(355, 110, 150, 80, 'rgba(16,185,129,.10)', 'rgba(16,185,129,.45)')}
      <text x="430" y="143" textAnchor="middle" fill="#6ee7b7"
            fontSize="14" fontWeight="600">Warehouses</text>
      <text x="430" y="163" textAnchor="middle" fill="#64748b" fontSize="11">
        40 · 60,000 batches
      </text>

      {box(670, 110, 150, 80, 'rgba(56,189,248,.10)', 'rgba(56,189,248,.45)')}
      <text x="745" y="143" textAnchor="middle" fill="#7dd3fc"
            fontSize="14" fontWeight="600">Hospitals</text>
      <text x="745" y="163" textAnchor="middle" fill="#64748b" fontSize="11">
        200 connected
      </text>

      <path d="M190 150 L350 150" stroke="#8b5cf6" strokeWidth="2"
            fill="none" markerEnd="url(#ms-arrow)" className="ms-flow" />
      <text x="270" y="138" textAnchor="middle" fill="#a78bfa" fontSize="11">
        purchase orders
      </text>

      <path d="M505 150 L665 150" stroke="#38bdf8" strokeWidth="2"
            fill="none" markerEnd="url(#ms-arrow)" className="ms-flow" />
      <text x="585" y="138" textAnchor="middle" fill="#7dd3fc" fontSize="11">
        allocations
      </text>

      <path d="M430 110 Q430 40 270 40 Q115 40 115 108"
            stroke="#f59e0b" strokeWidth="1.8" fill="none"
            strokeDasharray="4 6" markerEnd="url(#ms-arrow)" />
      <text x="272" y="30" textAnchor="middle" fill="#fbbf24" fontSize="11">
        stock below threshold → auto stock-up
      </text>

      <path d="M745 190 Q745 258 585 258 Q430 258 430 192"
            stroke="#f43f5e" strokeWidth="1.8" fill="none"
            strokeDasharray="4 6" markerEnd="url(#ms-arrow)" />
      <text x="588" y="275" textAnchor="middle" fill="#fb7185" fontSize="11">
        emergency request
      </text>
    </svg>
  )
}

/* ---------------------------------------------------------------- */
/* 2. The race condition, stepped                                     */
/* ---------------------------------------------------------------- */
const UNSAFE = [
  ['T1', 'reads stock', 'sees 100', 100, 0],
  ['T2', 'reads stock', 'sees 100', 100, 0],
  ['T1', 'reserves 70', '100 − 70 = 30', 100, 70],
  ['T2', 'reserves 50', 'from its stale 100', 100, 120],
  ['!!', 'over-allocated', '120 promised, 100 exist', 100, 120],
]
const SAFE = [
  ['T1', 'SELECT … FOR UPDATE', 'row locked, sees 100', 100, 0],
  ['T2', 'SELECT … FOR UPDATE', 'BLOCKED, waiting', 100, 0],
  ['T1', 'reserves 70, COMMIT', 'lock released', 100, 70],
  ['T2', 'unblocks, re-reads', 'sees 30 available', 100, 70],
  ['T2', 'reserves 30', 'partial, not 50', 100, 100],
]

function RaceSim() {
  const [step, setStep] = useState(0)
  const [playing, setPlaying] = useState(true)

  useEffect(() => {
    if (!playing) return
    const id = setInterval(() => setStep((s) => (s + 1) % 6), 1600)
    return () => clearInterval(id)
  }, [playing])

  const Panel = ({ rows, title, good }) => {
    const shown = rows.slice(0, step)
    const last = shown[shown.length - 1]
    const reserved = last ? last[4] : 0
    const over = reserved > 100
    return (
      <Card>
        <div className="mb-3 flex items-center justify-between">
          <h3 className={`text-sm font-semibold ${good ? 'text-emerald-300' : 'text-rose-300'}`}>
            {title}
          </h3>
          <span className={`rounded px-2 py-0.5 text-[10px] font-medium ${
            over ? 'bg-rose-500/15 text-rose-300'
                 : 'bg-emerald-500/15 text-emerald-300'}`}>
            {reserved} / 100 reserved
          </span>
        </div>

        <div className="mb-3 h-2.5 overflow-hidden rounded-full bg-slate-800">
          <div className={`h-full transition-all duration-500 ${
            over ? 'bg-rose-500' : 'bg-emerald-500'}`}
            style={{ width: `${Math.min(reserved, 100)}%` }} />
        </div>

        <div className="space-y-1.5 font-mono text-xs">
          {shown.map(([who, what, note], i) => (
            <div key={i} className="ms-rise flex gap-2">
              <span className={`w-7 shrink-0 ${
                who === 'T1' ? 'text-sky-400'
                : who === 'T2' ? 'text-violet-400' : 'text-rose-400'}`}>
                {who}
              </span>
              <span className="text-slate-300">{what}</span>
              <span className="text-slate-600">— {note}</span>
            </div>
          ))}
          {shown.length === 0 && (
            <div className="text-slate-600">waiting…</div>
          )}
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs text-slate-400">
        <button onClick={() => setPlaying((p) => !p)}
          className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5
            text-slate-300 transition hover:border-slate-600">
          {playing ? 'Pause' : 'Play'}
        </button>
        <button onClick={() => setStep(0)}
          className="rounded-lg border border-slate-700 bg-slate-800/60 px-3 py-1.5
            text-slate-300 transition hover:border-slate-600">
          Restart
        </button>
        <span>
          One batch of 100 units. Hospital A wants 70, Hospital B wants 50.
        </span>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel rows={UNSAFE} title="Without row locking" good={false} />
        <Panel rows={SAFE} title="With SELECT … FOR UPDATE" good />
      </div>
    </div>
  )
}

/* ---------------------------------------------------------------- */
/* 3. Auto stock-up cycle                                             */
/* ---------------------------------------------------------------- */
const CYCLE = [
  ['Scan', 'scheduler checks every policy', '#38bdf8'],
  ['Below threshold', 'available + on-order ≤ min', '#f59e0b'],
  ['Pick supplier', 'from the catalogue, best rated', '#a78bfa'],
  ['Raise PO', 'qty = target − available − on-order', '#34d399'],
  ['Lifecycle', 'SENT → CONFIRMED → SHIPPED', '#60a5fa'],
  ['Delivered', 'new batch lands in inventory', '#6ee7b7'],
]

function CycleSim() {
  const [i, setI] = useState(0)
  useEffect(() => {
    const id = setInterval(() => setI((v) => (v + 1) % CYCLE.length), 1800)
    return () => clearInterval(id)
  }, [])

  return (
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      {CYCLE.map(([label, note, color], idx) => {
        const active = idx === i
        return (
          <div key={label}
            className={`rounded-xl border p-4 transition-all duration-500 ${
              active ? 'scale-[1.02] border-slate-600 bg-slate-800/70'
                     : 'border-slate-800 bg-slate-900/40'}`}>
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full transition-all"
                style={{ background: color, opacity: active ? 1 : 0.3,
                         boxShadow: active ? `0 0 12px ${color}` : 'none' }} />
              <span className="text-xs font-semibold"
                style={{ color: active ? color : '#64748b' }}>
                {idx + 1}. {label}
              </span>
            </div>
            <p className={`mt-1.5 text-xs transition-colors ${
              active ? 'text-slate-300' : 'text-slate-600'}`}>{note}</p>
          </div>
        )
      })}
    </div>
  )
}

/* ---------------------------------------------------------------- */

const CONCEPTS = [
  ['ER / EER modelling', '17 relations, weak entities, associative entities'],
  ['Normalization', 'UNF → 1NF → 2NF → 3NF → BCNF, with a documented BCNF violation'],
  ['Indexing', '11 indexes: composite, partial, hash, range — measured with EXPLAIN ANALYZE'],
  ['Query optimization', 'fan-out join rewrite: 10,967 ms → 11.5 ms'],
  ['ACID transactions', 'allocation never over-promises; CHECK constraint as backstop'],
  ['Concurrency control', 'lost update reproduced, then prevented with two-phase locking'],
  ['Deadlock', 'induced, detected by PostgreSQL (40P01), prevented by lock ordering'],
  ['Recovery', 'rollback, savepoints, WAL, durability settings'],
  ['NoSQL + CAP', 'MongoDB for 6 incident shapes sharing no common fields'],
]

const STACK = [
  ['Frontend', 'React · Vite · Tailwind · Recharts'],
  ['Backend', 'FastAPI · SQLAlchemy 2.0 · Pydantic v2'],
  ['Relational', 'PostgreSQL 16'],
  ['Document', 'MongoDB 7'],
]

const TEAM = ['Mukesh', 'Deepakshi', 'Shaheed', 'Gayathri Menon', 'Sahana']

export default function Overview() {
  return (
    <div className="space-y-10 pb-12">
      <style>{CSS}</style>

      <header>
        <div className="text-[11px] font-medium uppercase tracking-[0.2em] text-emerald-400/70">
          BCSE302L · Database Systems
        </div>
        <h1 className="mt-2 bg-gradient-to-r from-emerald-300 via-sky-300 to-violet-300
          bg-clip-text text-4xl font-semibold text-transparent">
          MedSupply
        </h1>
        <p className="mt-3 max-w-3xl text-slate-400">
          Emergency medical supply management. Scarce medicine is allocated to
          hospitals without ever being promised twice, and warehouse stock
          replenishes itself before it runs out. The interesting problems here
          are database problems: concurrency, consistency and query cost.
        </p>
      </header>

      <Section eyebrow="How it fits together" title="Two loops, opposite directions">
        <Card><PipelineDiagram /></Card>
        <p className="text-sm text-slate-400">
          Demand pulls stock out of warehouses toward hospitals. Supply pushes
          it back in from suppliers. Both touch the same inventory rows, which
          is exactly why the locking has to be right.
        </p>
      </Section>

      <Section eyebrow="The core problem"
               title="Two hospitals, one batch, 100 units">
        <RaceSim />
        <p className="text-sm text-slate-400">
          Both transactions read before either writes. Without a lock the second
          read is stale by the time it writes, so 120 units get promised against
          100 in stock — the lost update problem. Taking the row lock at
          <em> read</em> time forces the second transaction to wait and re-read.
          A <code className="rounded bg-slate-800 px-1 text-xs">CHECK
          (qty_reserved &lt;= qty_on_hand)</code> sits underneath as a database
          backstop.
        </p>
      </Section>

      <Section eyebrow="Supply side" title="Auto Stock-Up, step by step">
        <CycleSim />
        <p className="text-sm text-slate-400">
          Runs on a background scheduler, not a button. Duplicate orders are
          prevented by a partial unique index permitting at most one open order
          line per (warehouse, medicine) — an application-level check alone
          would be a time-of-check/time-of-use race. All orders are simulated;
          no supplier is contacted.
        </p>
      </Section>

      <Section eyebrow="Syllabus" title="Concepts demonstrated">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {CONCEPTS.map(([t, d]) => (
            <div key={t}
              className="rounded-xl border border-slate-800 bg-slate-900/40 p-4
                transition hover:border-slate-700">
              <div className="text-sm font-medium text-slate-200">{t}</div>
              <p className="mt-1 text-xs text-slate-500">{d}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section eyebrow="Built with" title="Stack">
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {STACK.map(([k, v]) => (
            <Card key={k}>
              <div className="text-[11px] uppercase tracking-widest text-slate-500">{k}</div>
              <div className="mt-1.5 text-sm text-slate-300">{v}</div>
            </Card>
          ))}
        </div>
      </Section>

      <Section eyebrow="Group" title="Team">
        <div className="flex flex-wrap gap-2">
          {TEAM.map((n) => (
            <span key={n}
              className="rounded-full border border-slate-700 bg-slate-800/50 px-4
                py-1.5 text-sm text-slate-300">{n}</span>
          ))}
        </div>
      </Section>
    </div>
  )
}
