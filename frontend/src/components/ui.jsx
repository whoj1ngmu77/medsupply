export const Card = ({ children, className = '' }) => (
  <div className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 ${className}`}>
    {children}
  </div>
)

export const Spinner = ({ label = 'Loading' }) => (
  <div className="flex items-center gap-3 py-8 text-slate-400">
    <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-600 border-t-emerald-400" />
    <span className="text-sm">{label}…</span>
  </div>
)

export const ErrorBox = ({ message, onRetry }) => (
  <div className="rounded-lg border border-rose-900/60 bg-rose-950/30 p-4 text-sm text-rose-300">
    <p>{message}</p>
    {onRetry && (
      <button onClick={onRetry}
        className="mt-2 rounded border border-rose-800 px-3 py-1 text-xs hover:bg-rose-900/40">
        Retry
      </button>
    )}
  </div>
)

export const Empty = ({ message = 'No records found' }) => (
  <p className="py-8 text-center text-sm text-slate-500">{message}</p>
)

const BADGES = {
  CRITICAL: 'bg-rose-500/15 text-rose-300 border-rose-800',
  HIGH: 'bg-amber-500/15 text-amber-300 border-amber-800',
  MEDIUM: 'bg-sky-500/15 text-sky-300 border-sky-800',
  LOW: 'bg-slate-500/15 text-slate-300 border-slate-700',
  PENDING: 'bg-amber-500/15 text-amber-300 border-amber-800',
  PARTIAL: 'bg-orange-500/15 text-orange-300 border-orange-800',
  ALLOCATED: 'bg-sky-500/15 text-sky-300 border-sky-800',
  DISPATCHED: 'bg-violet-500/15 text-violet-300 border-violet-800',
  DELIVERED: 'bg-emerald-500/15 text-emerald-300 border-emerald-800',
  REJECTED: 'bg-rose-500/15 text-rose-300 border-rose-800',
  LIFE_SAVING: 'bg-rose-500/15 text-rose-300 border-rose-800',
  ESSENTIAL: 'bg-amber-500/15 text-amber-300 border-amber-800',
  ROUTINE: 'bg-slate-500/15 text-slate-300 border-slate-700',
  OUT_OF_STOCK: 'bg-rose-500/15 text-rose-300 border-rose-800',
  LOW_STOCK: 'bg-amber-500/15 text-amber-300 border-amber-800',
  HEALTHY: 'bg-emerald-500/15 text-emerald-300 border-emerald-800',
}

export const Badge = ({ value }) => (
  <span className={`inline-block rounded-full border px-2 py-0.5 text-xs ${
    BADGES[value] || 'bg-slate-500/15 text-slate-300 border-slate-700'}`}>
    {String(value).replace(/_/g, ' ')}
  </span>
)

export const Table = ({ columns, rows, empty }) => {
  if (!rows?.length) return <Empty message={empty} />
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-800 text-left text-xs uppercase tracking-wide text-slate-500">
            {columns.map((c) => (
              <th key={c.key} className="px-3 py-2 font-medium">{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-slate-800/60 hover:bg-slate-800/30">
              {columns.map((c) => (
                <td key={c.key} className="px-3 py-2 text-slate-300">
                  {c.render ? c.render(r) : r[c.key] ?? '—'}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export const Pagination = ({ total, limit, offset, onChange }) => {
  const page = Math.floor(offset / limit) + 1
  const pages = Math.ceil(total / limit)
  if (pages <= 1) return null
  return (
    <div className="mt-4 flex items-center justify-between text-sm text-slate-400">
      <span>{total.toLocaleString()} records · page {page} of {pages}</span>
      <div className="flex gap-2">
        <button disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          className="rounded border border-slate-700 px-3 py-1 disabled:opacity-30 hover:bg-slate-800">
          Previous
        </button>
        <button disabled={page >= pages}
          onClick={() => onChange(offset + limit)}
          className="rounded border border-slate-700 px-3 py-1 disabled:opacity-30 hover:bg-slate-800">
          Next
        </button>
      </div>
    </div>
  )
}
