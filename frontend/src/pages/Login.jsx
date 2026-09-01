import { useState } from 'react'
import { useAuth } from '../context/AuthContext'

const DEMO = [
  ['admin', 'admin@12345', 'Admin'],
  ['coordinator', 'coord@12345', 'Coordinator'],
  ['hosp1', 'hosp1@12345', 'Hospital staff'],
  ['wh1', 'wh1@12345', 'Warehouse staff'],
]

export default function Login() {
  const { login, loading, error } = useAuth()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    await login(username, password)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-950 p-6">
      <div className="w-full max-w-md">
        <h1 className="bg-gradient-to-r from-emerald-400 to-cyan-400 bg-clip-text text-4xl font-bold text-transparent">
          MedSupply
        </h1>
        <p className="mt-1 text-sm text-slate-400">
          Emergency Medical Supply Management · BCSE302L
        </p>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/60 p-6">
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
                Username
              </label>
              <input value={username} onChange={(e) => setUsername(e.target.value)}
                autoComplete="username" required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-emerald-600" />
            </div>
            <div>
              <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
                Password
              </label>
              <input type="password" value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password" required
                className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-slate-100 outline-none focus:border-emerald-600" />
            </div>

            {error && (
              <p className="rounded border border-rose-900/60 bg-rose-950/30 px-3 py-2 text-sm text-rose-300">
                {error}
              </p>
            )}

            <button type="submit" disabled={loading}
              className="w-full rounded-lg bg-gradient-to-r from-emerald-500 to-cyan-500 px-4 py-2 font-medium text-slate-950 disabled:opacity-50">
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>

          <div className="mt-6 border-t border-slate-800 pt-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
              Demo accounts
            </p>
            <div className="grid grid-cols-2 gap-2">
              {DEMO.map(([u, p, label]) => (
                <button key={u} onClick={() => { setUsername(u); setPassword(p) }}
                  className="rounded border border-slate-800 px-2 py-1.5 text-left text-xs text-slate-400 hover:border-emerald-800 hover:text-emerald-300">
                  <span className="block font-medium text-slate-300">{label}</span>
                  {u}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
