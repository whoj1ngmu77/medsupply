import { useState } from 'react'
import { api } from '../../api/client'
import { useFetch } from '../../hooks/useFetch'
import { Card, ErrorBox, Spinner, Table } from '../../components/ui'
import { Explain, Metric, PlanBox, RunButton } from '../../components/demo'

export default function IndexingLab() {
  const benchmarks = useFetch('/dbms/benchmarks')
  const indexes = useFetch('/dbms/indexes')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(null)
  const [error, setError] = useState(null)

  const run = async (key) => {
    setRunning(key)
    setError(null)
    setResult(null)
    try {
      setResult(await api.get(`/dbms/benchmarks/${key}`))
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-5">
      <Explain title="What this measures">
        <p>
          Each benchmark runs the same query twice: once with index access
          disabled via <code className="text-slate-300">SET LOCAL enable_indexscan = off</code>,
          then once with it enabled. Median of three runs.
        </p>
        <p>
          Index access is disabled with a planner flag rather than by dropping
          the index — dropping and recreating on a 60,000-row table would take
          seconds and make the demo unusable.
        </p>
        <p className="text-slate-500">
          Watch <span className="text-amber-300">Rows Removed by Filter</span> rather
          than milliseconds. The dataset fits in cache, so timings understate the
          difference; discarded rows do not.
        </p>
      </Explain>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">Benchmarks</h3>
        {benchmarks.loading ? <Spinner /> : (
          <div className="grid gap-2 md:grid-cols-2">
            {benchmarks.data.map((b) => (
              <div key={b.key}
                className="flex items-start justify-between rounded-lg bg-slate-800/40 p-3">
                <div className="pr-3">
                  <p className="text-sm text-slate-200">{b.label}</p>
                  <p className="mt-0.5 font-mono text-[11px] text-slate-500">
                    {b.index}
                  </p>
                  <p className="mt-1 text-[11px] text-slate-600">{b.endpoint}</p>
                </div>
                <RunButton onClick={() => run(b.key)} running={running === b.key}>
                  Run
                </RunButton>
              </div>
            ))}
          </div>
        )}
      </Card>

      {error && <ErrorBox message={error} />}

      {result && (
        <Card>
          <h3 className="mb-1 text-sm font-medium text-slate-300">{result.label}</h3>
          <p className="mb-4 font-mono text-xs text-slate-500">{result.index_name}</p>

          <div className="grid gap-4 lg:grid-cols-2">
            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-rose-400">
                Without index
              </p>
              <div className="mb-3 grid grid-cols-3 gap-2">
                <Metric label="Scan" value={result.without_index.scan_type}
                  accent="rose" />
                <Metric label="Time" value={result.without_index.execution_ms?.toFixed(2)}
                  unit="ms" accent="rose" />
                <Metric label="Rows discarded"
                  value={result.without_index.rows_removed_by_filter?.toLocaleString()}
                  accent="rose" />
              </div>
              <PlanBox plan={result.without_index.plan}
                highlight={['Seq Scan', 'Rows Removed']} />
            </div>

            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-emerald-400">
                With index
              </p>
              <div className="mb-3 grid grid-cols-3 gap-2">
                <Metric label="Scan" value={result.with_index.scan_type}
                  accent="emerald" />
                <Metric label="Time" value={result.with_index.execution_ms?.toFixed(2)}
                  unit="ms" accent="emerald" />
                <Metric label="Rows discarded"
                  value={result.with_index.rows_removed_by_filter?.toLocaleString()}
                  accent="emerald" />
              </div>
              <PlanBox plan={result.with_index.plan}
                highlight={['Index Scan', 'Index Only Scan', 'Bitmap Index Scan']} />
            </div>
          </div>

          <div className="mt-4 rounded-lg bg-slate-800/40 p-3">
            <p className="text-sm text-slate-300">
              Speedup: <span className="text-lg font-semibold text-emerald-300">
                {result.speedup_factor}×
              </span>
              <span className="ml-3 text-xs text-slate-500">
                rows discarded {result.without_index.rows_removed_by_filter?.toLocaleString()}
                {' → '}{result.with_index.rows_removed_by_filter?.toLocaleString()}
              </span>
            </p>
            <p className="mt-1 text-[11px] text-slate-500">{result.note}</p>
          </div>
        </Card>
      )}

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Indexes in this database
          <span className="ml-2 text-xs font-normal text-slate-500">
            live from pg_stat_user_indexes
          </span>
        </h3>
        {indexes.loading ? <Spinner /> : (
          <Table rows={indexes.data} empty="No indexes"
            columns={[
              { key: 'index_name', label: 'Index' },
              { key: 'table_name', label: 'Table' },
              { key: 'index_type', label: 'Type',
                render: (r) => (
                  <span className={`rounded px-2 py-0.5 text-xs ${
                    r.index_type === 'hash'
                      ? 'bg-violet-500/15 text-violet-300'
                      : 'bg-sky-500/15 text-sky-300'}`}>
                    {r.index_type}
                  </span>
                ) },
              { key: 'size', label: 'Size' },
              { key: 'times_used', label: 'Scans',
                render: (r) => Number(r.times_used).toLocaleString() },
            ]} />
        )}
      </Card>
    </div>
  )
}
