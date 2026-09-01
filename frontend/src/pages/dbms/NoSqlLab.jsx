import { useFetch } from '../../hooks/useFetch'
import { Card, Spinner, Table } from '../../components/ui'
import { Explain } from '../../components/demo'

export default function NoSqlLab() {
  const cap = useFetch('/dbms/nosql/cap')
  const chars = useFetch('/dbms/nosql/characteristics')
  const comparison = useFetch('/dbms/nosql/comparison')
  const indexes = useFetch('/dbms/nosql/indexes')

  if (cap.loading) return <Spinner />

  const c = cap.data

  return (
    <div className="space-y-5">
      <Explain title="CAP theorem">
        <p>{c.theorem}</p>
        <div className="mt-3 grid gap-2 md:grid-cols-3">
          {c.properties.map((p) => (
            <div key={p.letter} className="rounded-lg bg-slate-800/40 p-3">
              <p className="text-lg font-semibold text-emerald-300">
                {p.letter} — {p.name}
              </p>
              <p className="mt-1 text-xs text-slate-500">{p.meaning}</p>
            </div>
          ))}
        </div>
      </Explain>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <h3 className="text-sm font-medium text-sky-300">PostgreSQL</h3>
          <p className="mt-1 text-xs text-slate-500">{c.postgresql.classification}</p>
          <p className="mt-3 text-sm text-slate-400">{c.postgresql.why}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {c.postgresql.used_for.map((u) => (
              <span key={u} className="rounded bg-sky-500/15 px-2 py-0.5 text-xs text-sky-300">
                {u}
              </span>
            ))}
          </div>
          <p className="mt-3 rounded-lg bg-slate-800/40 p-3 text-xs text-slate-400">
            {c.postgresql.justification}
          </p>
        </Card>

        <Card>
          <h3 className="text-sm font-medium text-emerald-300">MongoDB</h3>
          <p className="mt-1 text-xs text-slate-500">{c.mongodb.classification}</p>
          <p className="mt-3 text-sm text-slate-400">{c.mongodb.why}</p>
          <div className="mt-3 flex flex-wrap gap-1.5">
            {c.mongodb.used_for.map((u) => (
              <span key={u} className="rounded bg-emerald-500/15 px-2 py-0.5 text-xs text-emerald-300">
                {u}
              </span>
            ))}
          </div>
          <p className="mt-3 rounded-lg bg-slate-800/40 p-3 text-xs text-slate-400">
            {c.mongodb.justification}
          </p>
        </Card>
      </div>

      <Card>
        <p className="text-sm text-emerald-300">{c.the_split}</p>
        <p className="mt-3 rounded-lg bg-rose-500/10 p-3 text-xs text-rose-300">
          <span className="font-medium">The cost, stated honestly: </span>
          {c.cost_acknowledged}
        </p>
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          PostgreSQL vs MongoDB
        </h3>
        {comparison.loading ? <Spinner /> : (
          <Table rows={comparison.data} empty=""
            columns={[
              { key: 'aspect', label: 'Aspect' },
              { key: 'postgresql', label: 'PostgreSQL' },
              { key: 'mongodb', label: 'MongoDB' },
            ]} />
        )}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Document database characteristics
        </h3>
        {chars.loading ? <Spinner /> : (
          <div className="grid gap-2 md:grid-cols-2">
            {Object.entries(chars.data).map(([k, v]) => (
              <div key={k} className="rounded-lg bg-slate-800/40 p-3">
                <p className="text-xs font-medium text-emerald-300">
                  {k.replace(/_/g, ' ')}
                </p>
                <p className="mt-1 text-xs text-slate-500">{v}</p>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          MongoDB indexes
        </h3>
        {indexes.loading ? <Spinner /> : (
          <>
            <pre className="overflow-x-auto rounded-lg bg-slate-950 p-3 font-mono text-[11px] text-slate-400">
              {JSON.stringify(indexes.data.incidents, null, 2)}
            </pre>
            <p className="mt-2 text-xs text-slate-500">{indexes.data.note}</p>
          </>
        )}
      </Card>
    </div>
  )
}
