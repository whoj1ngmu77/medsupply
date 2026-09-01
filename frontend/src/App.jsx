import { useEffect, useState } from 'react'

export default function App() {
  const [health, setHealth] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    fetch('/api/health')
      .then((r) => r.json())
      .then(setHealth)
      .catch((e) => setError(e.message))
  }, [])

  const Pill = ({ label, state }) => (
    <div className="flex items-center justify-between rounded-lg bg-slate-800/60 px-4 py-3">
      <span className="text-slate-300">{label}</span>
      <span
        className={
          state === 'ok'
            ? 'rounded-full bg-emerald-500/15 px-3 py-1 text-sm text-emerald-400'
            : 'rounded-full bg-rose-500/15 px-3 py-1 text-sm text-rose-400'
        }
      >
        {state ?? '-'}
      </span>
    </div>
  )

  return (
    <div className="min-h-screen bg-slate-950 p-8 text-slate-100">
      <div className="mx-auto max-w-xl">
        <h1 className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-3xl font-bold text-transparent">
          MedSupply
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Emergency Medical Supply Management - BCSE302L
        </p>

        <div className="mt-8 space-y-3">
          <Pill label="API" state={health?.api} />
          <Pill label="PostgreSQL" state={health?.postgres} />
          <Pill label="MongoDB" state={health?.mongodb} />
        </div>

        {error && (
          <p className="mt-4 text-sm text-rose-400">
            Cannot reach backend: {error}
          </p>
        )}
      </div>
    </div>
  )
}
