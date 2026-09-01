import { useState } from 'react'
import { api } from '../../api/client'
import { Card, ErrorBox } from '../../components/ui'
import { Explain, Metric, RunButton, Timeline } from '../../components/demo'

const WaitForGraph = ({ graph, victim }) => (
  <svg viewBox="0 0 420 160" className="w-full max-w-md">
    <defs>
      <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
        orient="auto">
        <path d="M0,0 L0,6 L7,3 z" fill="#f43f5e" />
      </marker>
    </defs>

    <circle cx="90" cy="80" r="42"
      fill={victim === 'T1' ? '#4c0519' : '#064e3b'}
      stroke={victim === 'T1' ? '#f43f5e' : '#10b981'} strokeWidth="2" />
    <text x="90" y="76" textAnchor="middle" fill="#e2e8f0"
      fontSize="16" fontWeight="600">T1</text>
    <text x="90" y="94" textAnchor="middle" fill="#94a3b8" fontSize="9">
      {victim === 'T1' ? 'VICTIM' : 'survived'}
    </text>

    <circle cx="330" cy="80" r="42"
      fill={victim === 'T2' ? '#4c0519' : '#064e3b'}
      stroke={victim === 'T2' ? '#f43f5e' : '#10b981'} strokeWidth="2" />
    <text x="330" y="76" textAnchor="middle" fill="#e2e8f0"
      fontSize="16" fontWeight="600">T2</text>
    <text x="330" y="94" textAnchor="middle" fill="#94a3b8" fontSize="9">
      {victim === 'T2' ? 'VICTIM' : 'survived'}
    </text>

    <path d="M 132 62 Q 210 25 288 62" fill="none" stroke="#f43f5e"
      strokeWidth="2" markerEnd="url(#arrow)" />
    <text x="210" y="22" textAnchor="middle" fill="#fda4af" fontSize="9">
      waits for
    </text>

    <path d="M 288 98 Q 210 135 132 98" fill="none" stroke="#f43f5e"
      strokeWidth="2" markerEnd="url(#arrow)" />
    <text x="210" y="152" textAnchor="middle" fill="#fda4af" fontSize="9">
      waits for
    </text>
  </svg>
)

export default function DeadlockLab() {
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  const run = async () => {
    setRunning(true)
    setError(null)
    setResult(null)
    try {
      setResult(await api.post('/dbms/deadlock'))
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(false)
    }
  }

  return (
    <div className="space-y-5">
      <Explain title="Forcing a real deadlock">
        <p>
          Two transactions lock two rows in <strong>opposite order</strong>.
          T1 takes row A then wants B; T2 takes B then wants A. Neither can
          proceed. PostgreSQL's detector finds the cycle and aborts one with
          SQLSTATE 40P01.
        </p>
        <p className="text-slate-500">
          This runs only on <code className="text-slate-300">demo_inventory</code>.
          Production allocation orders its locks by (expiry_date, batch_id), so
          every transaction acquires locks in the same sequence and circular
          wait cannot form.
        </p>
      </Explain>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-slate-300">Deadlock demonstration</h3>
            <p className="text-xs text-slate-500">
              Takes ~1 second — deadlock_timeout is set to 1s
            </p>
          </div>
          <RunButton onClick={run} running={running} variant="danger">
            Force deadlock
          </RunButton>
        </div>

        {error && <div className="mt-4"><ErrorBox message={error} /></div>}

        {result && (
          <div className="mt-5 space-y-5">
            <div className="grid gap-4 lg:grid-cols-2">
              <div>
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                  Lock order
                </p>
                <div className="space-y-2">
                  <div className="rounded-lg bg-slate-800/40 p-3">
                    <p className="text-xs text-emerald-300">T1</p>
                    <p className="font-mono text-xs text-slate-400">
                      {result.lock_order.T1}
                    </p>
                  </div>
                  <div className="rounded-lg bg-slate-800/40 p-3">
                    <p className="text-xs text-cyan-300">T2</p>
                    <p className="font-mono text-xs text-amber-300">
                      {result.lock_order.T2}
                    </p>
                  </div>
                </div>
                <div className="mt-3 grid grid-cols-2 gap-2">
                  <Metric label="Deadlock occurred"
                    value={result.deadlock_occurred ? 'Yes' : 'No'}
                    accent={result.deadlock_occurred ? 'rose' : 'slate'} />
                  <Metric label="Victim" value={result.victim} accent="rose" />
                </div>
              </div>

              <div>
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                  Wait-for graph · cycle {result.wait_for_graph.cycle}
                </p>
                <WaitForGraph graph={result.wait_for_graph} victim={result.victim} />
                <p className="mt-1 text-[11px] text-slate-500">
                  {result.wait_for_graph.note}
                </p>
              </div>
            </div>

            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                Execution timeline
              </p>
              <Timeline entries={result.timeline} />
            </div>

            <div className="grid gap-3 lg:grid-cols-2">
              <div className="rounded-lg bg-slate-800/40 p-3">
                <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                  Coffman conditions — all four present
                </p>
                <ul className="space-y-1.5">
                  {result.four_conditions.map((c) => (
                    <li key={c.condition} className="text-xs">
                      <span className="text-emerald-300">{c.condition}</span>
                      <span className="text-slate-500"> — {c.present}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="space-y-2">
                <div className="rounded-lg bg-slate-800/40 p-3">
                  <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">
                    Detection
                  </p>
                  <p className="text-xs text-slate-400">{result.detection}</p>
                </div>
                <div className="rounded-lg bg-emerald-500/10 p-3">
                  <p className="mb-1 text-xs uppercase tracking-wide text-emerald-400">
                    Prevention in production
                  </p>
                  <p className="text-xs text-slate-400">
                    {result.prevention_in_production}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}
      </Card>
    </div>
  )
}
