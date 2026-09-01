export const PlanBox = ({ plan, highlight = [] }) => {
  if (!plan) return null
  return (
    <pre className="max-h-72 overflow-auto rounded-lg bg-slate-950 p-3 font-mono text-[11px] leading-relaxed text-slate-400">
      {plan.split('\n').map((line, i) => {
        const hit = highlight.find((h) => line.includes(h))
        return (
          <div key={i} className={hit ? 'text-amber-300' : ''}>{line}</div>
        )
      })}
    </pre>
  )
}

export const Metric = ({ label, value, unit, accent = 'slate' }) => (
  <div className="rounded-lg bg-slate-800/40 px-3 py-2">
    <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
    <p className={`text-lg font-semibold text-${accent}-300`}>
      {value ?? '—'}
      {unit && <span className="ml-1 text-xs font-normal text-slate-500">{unit}</span>}
    </p>
  </div>
)

export const Timeline = ({ entries, keyFn }) => {
  if (!entries?.length) return null
  const t0 = entries[0].t
  const colors = { T1: 'text-emerald-300', T2: 'text-cyan-300' }
  return (
    <div className="space-y-0.5 rounded-lg bg-slate-950 p-3 font-mono text-[11px]">
      {entries.map((e, i) => (
        <div key={i} className={`flex gap-3 ${e.ok === false ? 'text-rose-300' : ''}`}>
          <span className="w-16 shrink-0 text-right text-slate-600">
            +{(e.t - t0).toFixed(0)}ms
          </span>
          <span className={`w-8 shrink-0 font-semibold ${colors[e.txn] || 'text-slate-400'}`}>
            {e.txn}
          </span>
          <span className="w-36 shrink-0 text-slate-500">{e.step}</span>
          <span className="text-slate-400">{e.detail}</span>
        </div>
      ))}
    </div>
  )
}

export const Explain = ({ title, children }) => (
  <div className="rounded-lg border border-slate-800 bg-slate-900/40 p-4">
    <h4 className="mb-2 text-xs uppercase tracking-wide text-emerald-400">{title}</h4>
    <div className="space-y-2 text-sm leading-relaxed text-slate-400">{children}</div>
  </div>
)

export const RunButton = ({ onClick, running, children, variant = 'primary' }) => {
  const styles = {
    primary: 'bg-gradient-to-r from-emerald-500 to-cyan-500 text-slate-950',
    danger: 'bg-gradient-to-r from-rose-500 to-orange-500 text-slate-950',
    ghost: 'border border-slate-700 text-slate-300 hover:bg-slate-800',
  }
  return (
    <button onClick={onClick} disabled={running}
      className={`rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-40 ${styles[variant]}`}>
      {running ? 'Running…' : children}
    </button>
  )
}
