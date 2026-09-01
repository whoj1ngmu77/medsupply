import { useState } from 'react'
import { Card } from '../../components/ui'
import { Explain, Metric, RunButton } from '../../components/demo'

const BUCKET_CAPACITY = 3

// ---- static hashing ----
function staticInsert(buckets, key, n) {
  const idx = key % n
  const next = buckets.map((b) => ({ ...b, keys: [...b.keys],
                                     overflow: [...b.overflow] }))
  const b = next[idx]
  if (b.keys.includes(key) || b.overflow.includes(key)) {
    return { buckets: next, log: `${key} already present` }
  }
  if (b.keys.length < BUCKET_CAPACITY) {
    b.keys.push(key)
    return { buckets: next,
             log: `h(${key}) = ${key} mod ${n} = ${idx} → bucket ${idx}` }
  }
  b.overflow.push(key)
  return { buckets: next,
           log: `h(${key}) = ${idx}, bucket FULL → overflow chain ` +
                `(now ${b.overflow.length} deep — every probe costs an extra read)` }
}

// ---- extendible hashing ----
function binary(v, bits) {
  return v.toString(2).padStart(bits, '0').slice(-bits) || '0'
}

function extendibleInsert(state, key) {
  let { globalDepth, directory, buckets } = structuredClone(state)
  const log = []
  const hash = key
  const idx = parseInt(binary(hash, globalDepth), 2) || 0
  const bucketId = directory[idx]
  const bucket = buckets[bucketId]

  if (bucket.keys.includes(key)) return { ...state, log: [`${key} already present`] }

  log.push(`h(${key}) = ${binary(hash, globalDepth)}₂ → directory[${idx}] ` +
           `→ bucket ${bucketId}`)

  if (bucket.keys.length < BUCKET_CAPACITY) {
    bucket.keys.push(key)
    bucket.keys.sort((a, b) => a - b)
    return { globalDepth, directory, buckets, log }
  }

  log.push(`Bucket ${bucketId} full (local depth ${bucket.localDepth}, ` +
           `global depth ${globalDepth})`)

  if (bucket.localDepth === globalDepth) {
    globalDepth += 1
    directory = [...directory, ...directory]
    log.push(`Local = global → DIRECTORY DOUBLES to ${directory.length} entries ` +
             `(global depth now ${globalDepth})`)
  } else {
    log.push(`Local < global → split bucket only, directory unchanged`)
  }

  const newId = buckets.length
  bucket.localDepth += 1
  buckets.push({ localDepth: bucket.localDepth, keys: [] })

  const all = [...bucket.keys, key]
  bucket.keys = []
  all.forEach((k) => {
    const bit = binary(k, bucket.localDepth)[0]
    if (bit === '1') buckets[newId].keys.push(k)
    else bucket.keys.push(k)
  })
  bucket.keys.sort((a, b) => a - b)
  buckets[newId].keys.sort((a, b) => a - b)

  directory = directory.map((id, i) => {
    if (id !== bucketId) return id
    const prefix = binary(i, globalDepth)
    return prefix[globalDepth - bucket.localDepth] === '1' ? newId : bucketId
  })

  log.push(`Rehashed on bit ${bucket.localDepth}: ` +
           `bucket ${bucketId} = [${bucket.keys.join(', ')}], ` +
           `bucket ${newId} = [${buckets[newId].keys.join(', ')}]`)

  return { globalDepth, directory, buckets, log }
}

const initExtendible = () => ({
  globalDepth: 1,
  directory: [0, 1],
  buckets: [{ localDepth: 1, keys: [] }, { localDepth: 1, keys: [] }],
})

export default function Hashing() {
  const [mode, setMode] = useState('static')
  const [n, setN] = useState(4)
  const [buckets, setBuckets] = useState(
    Array.from({ length: 4 }, () => ({ keys: [], overflow: [] })))
  const [ext, setExt] = useState(initExtendible())
  const [input, setInput] = useState('')
  const [log, setLog] = useState([])

  const add = (v) => {
    const key = Number(v)
    if (!Number.isFinite(key) || key < 0) return
    if (mode === 'static') {
      const r = staticInsert(buckets, key, n)
      setBuckets(r.buckets)
      setLog([r.log])
    } else {
      const r = extendibleInsert(ext, key)
      setExt({ globalDepth: r.globalDepth, directory: r.directory,
               buckets: r.buckets })
      setLog(r.log)
    }
    setInput('')
  }

  const bulk = () => {
    const keys = [12, 4, 9, 20, 16, 7, 25, 8, 13, 1, 17, 33]
    if (mode === 'static') {
      let b = Array.from({ length: n }, () => ({ keys: [], overflow: [] }))
      const logs = []
      keys.forEach((k) => { const r = staticInsert(b, k, n); b = r.buckets; logs.push(r.log) })
      setBuckets(b)
      setLog(logs.slice(-6))
    } else {
      let s = initExtendible()
      const logs = []
      keys.forEach((k) => {
        const r = extendibleInsert(s, k)
        s = { globalDepth: r.globalDepth, directory: r.directory, buckets: r.buckets }
        logs.push(...r.log)
      })
      setExt(s)
      setLog(logs.slice(-8))
    }
  }

  const reset = () => {
    setBuckets(Array.from({ length: n }, () => ({ keys: [], overflow: [] })))
    setExt(initExtendible())
    setLog([])
  }

  const overflowCount = buckets.reduce((s, b) => s + b.overflow.length, 0)

  return (
    <div className="space-y-5">
      <Explain title="Educational simulation">
        <p>
          Hash indexes give O(1) average equality lookup but cannot serve
          ranges or ordering. MedSupply uses one hash index —{' '}
          <code className="text-slate-300">idx_hospital_reg_hash</code> on{' '}
          <code className="text-slate-300">reg_number</code> — because that
          column is only ever looked up by exact match.
        </p>
        <p className="text-slate-500">
          PostgreSQL's hash indexes were not crash-safe before version 10 and
          were effectively unusable. Since 10 they are WAL-logged.
        </p>
      </Explain>

      <Card>
        <div className="mb-4 flex gap-2">
          {[['static', 'Static hashing'], ['extendible', 'Extendible hashing']].map(
            ([k, label]) => (
            <button key={k} onClick={() => { setMode(k); setLog([]) }}
              className={`rounded-lg px-4 py-1.5 text-sm ${
                mode === k ? 'bg-emerald-500/10 text-emerald-300'
                           : 'text-slate-400 hover:bg-slate-800'}`}>
              {label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-end gap-3">
          {mode === 'static' && (
            <div>
              <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
                Buckets (n)
              </label>
              <select value={n}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  setN(v)
                  setBuckets(Array.from({ length: v }, () => ({ keys: [], overflow: [] })))
                  setLog([])
                }}
                className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100">
                {[4, 5, 8].map((v) => <option key={v} value={v}>{v}</option>)}
              </select>
            </div>
          )}

          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
              Insert key
            </label>
            <div className="flex gap-2">
              <input value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && add(input)}
                type="number" min="0" placeholder="e.g. 17"
                className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100" />
              <RunButton onClick={() => add(input)}>Insert</RunButton>
            </div>
          </div>

          <RunButton onClick={bulk} variant="ghost">Load 12 keys</RunButton>
          <RunButton onClick={reset} variant="ghost">Reset</RunButton>
        </div>
      </Card>

      {mode === 'static' ? (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">
              Static hashing · h(k) = k mod {n}
            </h3>
            <div className="flex gap-2">
              <Metric label="Buckets" value={n} />
              <Metric label="Overflow records" value={overflowCount}
                accent={overflowCount > 0 ? 'rose' : 'emerald'} />
            </div>
          </div>

          <div className="space-y-2">
            {buckets.map((b, i) => (
              <div key={i} className="flex items-center gap-3">
                <span className="w-20 shrink-0 font-mono text-xs text-slate-500">
                  bucket {i}
                </span>
                <div className="flex gap-1">
                  {Array.from({ length: BUCKET_CAPACITY }).map((_, s) => (
                    <div key={s}
                      className={`flex h-8 w-12 items-center justify-center rounded border font-mono text-xs ${
                        b.keys[s] != null
                          ? 'border-emerald-700 bg-emerald-500/10 text-emerald-300'
                          : 'border-slate-800 bg-slate-900 text-slate-700'}`}>
                      {b.keys[s] ?? '—'}
                    </div>
                  ))}
                </div>
                {b.overflow.length > 0 && (
                  <>
                    <span className="text-rose-500">→</span>
                    <div className="flex gap-1">
                      {b.overflow.map((k, oi) => (
                        <div key={oi}
                          className="flex h-8 w-12 items-center justify-center rounded border border-rose-700 bg-rose-500/10 font-mono text-xs text-rose-300">
                          {k}
                        </div>
                      ))}
                    </div>
                    <span className="text-[10px] text-rose-400">
                      overflow chain
                    </span>
                  </>
                )}
              </div>
            ))}
          </div>

          <p className="mt-4 text-xs text-slate-500">
            The bucket count is fixed. As data grows, overflow chains lengthen
            and lookups degrade from O(1) toward O(n) within a chain. Rebuilding
            with a larger n requires rehashing everything — the fundamental
            limitation of static hashing.
          </p>
        </Card>
      ) : (
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h3 className="text-sm font-medium text-slate-300">
              Extendible hashing
            </h3>
            <div className="flex gap-2">
              <Metric label="Global depth" value={ext.globalDepth} accent="sky" />
              <Metric label="Directory size" value={ext.directory.length} />
              <Metric label="Buckets" value={ext.buckets.length} accent="emerald" />
            </div>
          </div>

          <div className="flex gap-8">
            <div>
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                Directory ({ext.globalDepth} bits)
              </p>
              <div className="space-y-1">
                {ext.directory.map((bid, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="w-12 font-mono text-xs text-sky-300">
                      {binary(i, ext.globalDepth)}
                    </span>
                    <span className="text-slate-600">→</span>
                    <span className="w-16 rounded bg-slate-800 px-2 py-0.5 text-center font-mono text-xs text-slate-400">
                      B{bid}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            <div className="flex-1">
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                Buckets
              </p>
              <div className="space-y-2">
                {ext.buckets.map((b, i) => (
                  <div key={i} className="flex items-center gap-3">
                    <span className="w-24 shrink-0 font-mono text-xs text-slate-500">
                      B{i} <span className="text-slate-600">
                        (local {b.localDepth})
                      </span>
                    </span>
                    <div className="flex gap-1">
                      {Array.from({ length: BUCKET_CAPACITY }).map((_, s) => (
                        <div key={s}
                          className={`flex h-8 w-12 items-center justify-center rounded border font-mono text-xs ${
                            b.keys[s] != null
                              ? 'border-emerald-700 bg-emerald-500/10 text-emerald-300'
                              : 'border-slate-800 bg-slate-900 text-slate-700'}`}>
                          {b.keys[s] ?? '—'}
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p className="mt-4 text-xs text-slate-500">
            No overflow chains. When a bucket fills, it splits. If its local
            depth equals the global depth, the directory doubles; otherwise only
            the bucket splits and the directory is untouched. Lookup stays O(1)
            — one directory read, one bucket read.
          </p>
        </Card>
      )}

      {log.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-medium text-slate-300">Operation log</h3>
          <div className="space-y-1 font-mono text-[11px]">
            {log.map((l, i) => (
              <p key={i} className={
                l.includes('DOUBLES') || l.includes('FULL') || l.includes('overflow')
                  ? 'text-amber-300' : 'text-slate-400'}>
                {l}
              </p>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Static vs extendible vs B+ tree
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-slate-800 text-left text-slate-500">
                <th className="px-3 py-2">Property</th>
                <th className="px-3 py-2">Static hash</th>
                <th className="px-3 py-2">Extendible hash</th>
                <th className="px-3 py-2">B+ tree</th>
              </tr>
            </thead>
            <tbody className="text-slate-400">
              {[
                ['Equality lookup', 'O(1) + chain', 'O(1)', 'O(log n)'],
                ['Range query', 'Not supported', 'Not supported', 'Efficient'],
                ['ORDER BY', 'No', 'No', 'Yes'],
                ['Growth handling', 'Overflow chains', 'Directory doubling', 'Node splits'],
                ['Space overhead', 'Low', 'Directory', 'Internal nodes'],
                ['Used in MedSupply', 'No', 'No (concept only)',
                 'Yes — 10 of 11 indexes'],
              ].map((row) => (
                <tr key={row[0]} className="border-b border-slate-800/60">
                  {row.map((c, i) => (
                    <td key={i} className={`px-3 py-2 ${
                      i === 0 ? 'text-slate-300' : ''}`}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
