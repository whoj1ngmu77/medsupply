import { useState } from 'react'
import { api } from '../../api/client'
import { useFetch } from '../../hooks/useFetch'
import { Card, ErrorBox, Spinner } from '../../components/ui'
import { Explain, Metric, RunButton, Timeline } from '../../components/demo'

export default function ConcurrencyLab() {
  const matrix = useFetch('/dbms/concurrency/lock-matrix')
  const [unsafe, setUnsafe] = useState(null)
  const [safe, setSafe] = useState(null)
  const [running, setRunning] = useState(null)
  const [error, setError] = useState(null)

  const run = async (useLock) => {
    setRunning(useLock ? 'safe' : 'unsafe')
    setError(null)
    try {
      const r = await api.post(
        `/dbms/concurrency?use_lock=${useLock}&stock=100&qty_a=70&qty_b=50`)
      useLock ? setSafe(r) : setUnsafe(r)
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(null)
    }
  }

  const Result = ({ data, tone }) => data && (
    <div className="mt-4 space-y-3">
      <div className="grid grid-cols-4 gap-2">
        <Metric label="Granted to" value={data.granted_to.join(', ') || 'none'} />
        <Metric label="Total granted" value={data.total_granted}
          accent={data.correct ? 'emerald' : 'rose'} />
        <Metric label="Physical stock" value={data.stock} />
        <Metric label="Final reserved" value={data.after.qty_reserved} />
      </div>

      <div className={`rounded-lg p-3 text-sm ${
        data.over_allocated
          ? 'bg-rose-500/10 text-rose-300'
          : 'bg-emerald-500/10 text-emerald-300'}`}>
        <p className="font-medium">
          {data.over_allocated
            ? `OVER-ALLOCATED: ${data.total_granted} units promised against ${data.stock} in stock`
            : `Correct: ${data.total_granted} units allocated from ${data.stock}`}
        </p>
        {data.units_lost_by_overwrite > 0 && (
          <p className="mt-1 text-xs">
            {data.units_lost_by_overwrite} units silently lost — the second
            write overwrote the first
          </p>
        )}
        <p className="mt-2 text-xs text-slate-400">{data.explanation}</p>
      </div>

      <Timeline entries={data.timeline} />
    </div>
  )

  return (
    <div className="space-y-5">
      <Explain title="The lost update problem">
        <p>
          Two transactions, two real database connections, 100 units of stock.
          T1 wants 70, T2 wants 50. A barrier forces both to read before either
          writes, so the race is reproducible rather than luck-dependent.
        </p>
        <p className="text-slate-500">
          The unsafe run writes an <em>absolute</em> value computed from its
          stale read. Writing <code className="text-slate-300">SET x = x + n</code> instead
          would be atomic in the database and could never lose an update — which
          is itself the answer to "how do you prevent this without locking?"
        </p>
      </Explain>

      {error && <ErrorBox message={error} />}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-rose-300">
                Without locking
              </h3>
              <p className="text-xs text-slate-500">
                plain SELECT, READ COMMITTED
              </p>
            </div>
            <RunButton onClick={() => run(false)} running={running === 'unsafe'}
              variant="danger">
              Run unsafe
            </RunButton>
          </div>
          <Result data={unsafe} />
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-medium text-emerald-300">
                With SELECT … FOR UPDATE
              </h3>
              <p className="text-xs text-slate-500">
                exclusive row lock at read time
              </p>
            </div>
            <RunButton onClick={() => run(true)} running={running === 'safe'}>
              Run safe
            </RunButton>
          </div>
          <Result data={safe} />
        </Card>
      </div>

      <Card>
        <h3 className="mb-1 text-sm font-medium text-slate-300">
          Two-phase locking
        </h3>
        <p className="mb-4 text-xs text-slate-500">
          Growing phase: locks acquired during the transaction. Shrinking phase:
          all released at COMMIT. PostgreSQL uses <em>strict</em> 2PL — no lock
          is released early, which also prevents cascading aborts.
        </p>

        {matrix.loading ? <Spinner /> : (
          <>
            <h4 className="mb-2 text-xs uppercase tracking-wide text-slate-500">
              {matrix.data.title}
            </h4>
            <div className="overflow-x-auto">
              <table className="text-xs">
                <thead>
                  <tr className="text-slate-500">
                    <th className="px-3 py-1.5 text-left">Requested ↓ / Held →</th>
                    {matrix.data.modes.map((m) => (
                      <th key={m} className="px-3 py-1.5 font-mono">{m}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {matrix.data.matrix.map((row) => (
                    <tr key={row.requested} className="border-t border-slate-800">
                      <td className="px-3 py-1.5 font-mono text-slate-400">
                        {row.requested}
                      </td>
                      {matrix.data.modes.map((m) => (
                        <td key={m} className="px-3 py-1.5 text-center">
                          <span className={row[m]
                            ? 'text-emerald-400' : 'text-rose-400'}>
                            {row[m] ? '✓' : '✕'}
                          </span>
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-3 text-xs text-slate-500">{matrix.data.note}</p>
          </>
        )}
      </Card>
    </div>
  )
}
