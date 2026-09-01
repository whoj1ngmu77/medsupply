import { useState } from 'react'
import { api } from '../../api/client'
import { useFetch } from '../../hooks/useFetch'
import { Card, ErrorBox, Spinner } from '../../components/ui'
import { Explain, Metric, PlanBox, RunButton } from '../../components/demo'

export default function OptimizationLab() {
  const demos = useFetch('/dbms/optimization')
  const [result, setResult] = useState(null)
  const [running, setRunning] = useState(null)
  const [error, setError] = useState(null)

  const run = async (key) => {
    setRunning(key)
    setError(null)
    setResult(null)
    try {
      setResult(await api.get(`/dbms/optimization/${key}`))
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(null)
    }
  }

  return (
    <div className="space-y-5">
      <Explain title="Query rewriting vs index selection">
        <p>
          Each demo runs two forms of the same logical query and compares the
          plans. Some pairs produce identical plans — that is the finding, not
          a failure: PostgreSQL's optimizer normalises them during rewriting.
        </p>
        <p className="text-slate-500">
          The most important result in this project came from a rewrite, not an
          index: <code className="text-slate-300">v_critical_shortage</code> fell
          from 10,967 ms to 11.5 ms by aggregating each child table before
          joining, eliminating a 127-million-row fan-out.
        </p>
      </Explain>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">Demonstrations</h3>
        {demos.loading ? <Spinner /> : (
          <div className="space-y-2">
            {demos.data.map((d) => (
              <div key={d.key}
                className="flex items-start justify-between rounded-lg bg-slate-800/40 p-3">
                <div className="pr-4">
                  <p className="text-sm text-slate-200">{d.title}</p>
                  <p className="mt-0.5 text-xs text-slate-500">{d.concept}</p>
                </div>
                <RunButton onClick={() => run(d.key)} running={running === d.key}>
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
          <h3 className="text-sm font-medium text-slate-300">{result.title}</h3>
          <p className="mt-1 text-xs text-slate-500">{result.concept}</p>

          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            {['variant_a', 'variant_b'].map((v, i) => {
              const r = result.results[v]
              return (
                <div key={v}>
                  <p className={`mb-2 text-xs uppercase tracking-wide ${
                    i === 0 ? 'text-sky-400' : 'text-violet-400'}`}>
                    {r.label}
                  </p>
                  <div className="mb-2 grid grid-cols-2 gap-2">
                    <Metric label="Scan type" value={r.scan_type} />
                    <Metric label="Time" value={r.execution_ms?.toFixed(2)} unit="ms" />
                  </div>
                  <pre className="mb-2 overflow-x-auto rounded bg-slate-950 p-2 font-mono text-[10px] text-slate-500">
                    {r.sql}
                  </pre>
                  <PlanBox plan={r.plan}
                    highlight={['Seq Scan', 'Index Scan', 'Hash Join',
                                'Nested Loop', 'Merge Join', 'Sort']} />
                </div>
              )
            })}
          </div>

          <div className={`mt-4 rounded-lg p-3 text-sm ${
            result.plans_use_same_scan_type
              ? 'bg-amber-500/10 text-amber-300'
              : 'bg-emerald-500/10 text-emerald-300'}`}>
            <p className="font-medium">{result.observation}</p>
            <p className="mt-1 text-xs text-slate-400">{result.expected}</p>
          </div>
        </Card>
      )}
    </div>
  )
}
