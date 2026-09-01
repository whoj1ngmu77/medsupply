import { useState } from 'react'
import { Card } from '../../components/ui'
import { Explain, RunButton } from '../../components/demo'

// ---- B+ tree implementation (educational, in-browser) ----

const makeLeaf = () => ({ leaf: true, keys: [], next: null })
const makeInternal = () => ({ leaf: false, keys: [], children: [] })

function insert(root, key, order) {
  const maxKeys = order - 1
  const result = insertInto(root, key, maxKeys)
  if (!result.split) return { root, log: result.log }

  const newRoot = makeInternal()
  newRoot.keys = [result.separator]
  newRoot.children = [root, result.right]
  return {
    root: newRoot,
    log: [...result.log,
          `Root split — tree height increased. New root key: ${result.separator}`],
  }
}

function insertInto(node, key, maxKeys) {
  const log = []

  if (node.leaf) {
    if (node.keys.includes(key)) return { split: false, log: [`${key} already present`] }
    node.keys.push(key)
    node.keys.sort((a, b) => a - b)
    log.push(`Inserted ${key} into leaf [${node.keys.join(', ')}]`)

    if (node.keys.length <= maxKeys) return { split: false, log }

    const mid = Math.ceil(node.keys.length / 2)
    const right = makeLeaf()
    right.keys = node.keys.slice(mid)
    node.keys = node.keys.slice(0, mid)
    right.next = node.next
    node.next = right

    log.push(`Leaf overflow (${maxKeys + 1} > ${maxKeys}) — split into ` +
             `[${node.keys.join(', ')}] and [${right.keys.join(', ')}]`)
    log.push(`Separator ${right.keys[0]} COPIED up (leaf split copies, ` +
             `internal split moves)`)
    return { split: true, separator: right.keys[0], right, log }
  }

  let i = 0
  while (i < node.keys.length && key >= node.keys[i]) i++
  const res = insertInto(node.children[i], key, maxKeys)
  log.push(...res.log)

  if (!res.split) return { split: false, log }

  node.keys.splice(i, 0, res.separator)
  node.children.splice(i + 1, 0, res.right)
  log.push(`Separator ${res.separator} inserted into parent ` +
           `[${node.keys.join(', ')}]`)

  if (node.keys.length <= maxKeys) return { split: false, log }

  const mid = Math.floor(node.keys.length / 2)
  const separator = node.keys[mid]
  const right = makeInternal()
  right.keys = node.keys.slice(mid + 1)
  right.children = node.children.slice(mid + 1)
  node.keys = node.keys.slice(0, mid)
  node.children = node.children.slice(0, mid + 1)

  log.push(`Internal overflow — split, ${separator} MOVED up (not copied)`)
  return { split: true, separator, right, log }
}

function search(root, key) {
  const path = []
  let node = root
  while (node && !node.leaf) {
    let i = 0
    while (i < node.keys.length && key >= node.keys[i]) i++
    path.push({ keys: [...node.keys], chose: i, leaf: false })
    node = node.children[i]
  }
  if (node) path.push({ keys: [...node.keys], leaf: true,
                        found: node.keys.includes(key) })
  return path
}

function levels(root) {
  const out = []
  let level = [root]
  while (level.length) {
    out.push(level)
    const next = []
    level.forEach((n) => { if (!n.leaf) next.push(...n.children) })
    level = next
  }
  return out
}

// ---- rendering ----

const Node = ({ node, highlight, chosen }) => (
  <div className={`flex rounded border ${
    highlight ? 'border-amber-500 bg-amber-500/10' :
    node.leaf ? 'border-emerald-700 bg-emerald-500/5'
              : 'border-sky-700 bg-sky-500/5'}`}>
    {node.keys.map((k, i) => (
      <div key={i}
        className={`border-r border-slate-700 px-2.5 py-1 font-mono text-xs last:border-r-0 ${
          chosen === k ? 'bg-amber-500/30 text-amber-200' : 'text-slate-300'}`}>
        {k}
      </div>
    ))}
  </div>
)

export default function BPlusTree() {
  const [order, setOrder] = useState(4)
  const [root, setRoot] = useState(makeLeaf())
  const [log, setLog] = useState([])
  const [input, setInput] = useState('')
  const [searchPath, setSearchPath] = useState(null)
  const [searchKey, setSearchKey] = useState('')

  const add = (value) => {
    const key = Number(value)
    if (!Number.isFinite(key)) return
    const cloned = structuredClone(root)
    const { root: newRoot, log: steps } = insert(cloned, key, order)
    setRoot(newRoot)
    setLog(steps)
    setSearchPath(null)
    setInput('')
  }

  const bulk = () => {
    let r = makeLeaf()
    const all = []
    ;[10, 20, 5, 30, 15, 25, 35, 40, 1, 45, 50, 12, 18, 22, 55].forEach((k) => {
      const res = insert(r, k, order)
      r = res.root
      all.push(...res.log)
    })
    setRoot(r)
    setLog(all.slice(-12))
    setSearchPath(null)
  }

  const doSearch = () => {
    const key = Number(searchKey)
    if (!Number.isFinite(key)) return
    setSearchPath({ key, path: search(root, key) })
  }

  const reset = () => {
    setRoot(makeLeaf())
    setLog([])
    setSearchPath(null)
  }

  const tree = levels(root)
  const leafCount = tree[tree.length - 1]?.length || 0
  const keyCount = tree.flat().filter((n) => n.leaf)
    .reduce((s, n) => s + n.keys.length, 0)

  return (
    <div className="space-y-5">
      <Explain title="Educational simulation — not PostgreSQL's internals">
        <p>
          This is a B+ tree implemented in the browser to make splits visible.
          PostgreSQL's actual B-tree is a highly optimised C implementation with
          page-level concurrency, WAL integration, and Lehman-Yao locking that
          cannot be observed from SQL.
        </p>
        <p className="text-slate-500">
          Two properties matter for indexing: <strong>all data lives in the
          leaves</strong> (internal nodes hold only separators), and{' '}
          <strong>leaves are linked</strong>, which is what makes range scans
          like <code className="text-slate-300">expiry_date BETWEEN … AND …</code> efficient.
        </p>
      </Explain>

      <Card>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
              Order (max children)
            </label>
            <select value={order}
              onChange={(e) => { setOrder(Number(e.target.value)); reset() }}
              className="rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100">
              {[3, 4, 5, 6].map((o) => (
                <option key={o} value={o}>{o} (max {o - 1} keys/node)</option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
              Insert key
            </label>
            <div className="flex gap-2">
              <input value={input} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && add(input)}
                type="number" placeholder="e.g. 42"
                className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100" />
              <RunButton onClick={() => add(input)}>Insert</RunButton>
            </div>
          </div>

          <div>
            <label className="mb-1 block text-xs uppercase tracking-wide text-slate-400">
              Search
            </label>
            <div className="flex gap-2">
              <input value={searchKey} onChange={(e) => setSearchKey(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && doSearch()}
                type="number" placeholder="key"
                className="w-28 rounded-lg border border-slate-700 bg-slate-950 px-3 py-1.5 text-sm text-slate-100" />
              <RunButton onClick={doSearch} variant="ghost">Find</RunButton>
            </div>
          </div>

          <RunButton onClick={bulk} variant="ghost">Load 15 keys</RunButton>
          <RunButton onClick={reset} variant="ghost">Reset</RunButton>
        </div>

        <div className="mt-4 flex gap-6 text-xs text-slate-500">
          <span>Height: <span className="text-slate-300">{tree.length}</span></span>
          <span>Leaves: <span className="text-slate-300">{leafCount}</span></span>
          <span>Keys: <span className="text-slate-300">{keyCount}</span></span>
          <span>Lookup cost: <span className="text-emerald-300">
            O(log n) — {tree.length} node visits
          </span></span>
        </div>
      </Card>

      <Card>
        <h3 className="mb-4 text-sm font-medium text-slate-300">Tree structure</h3>
        <div className="space-y-6 overflow-x-auto pb-2">
          {tree.map((level, li) => (
            <div key={li} className="flex items-center gap-4">
              <span className="w-16 shrink-0 text-[10px] uppercase text-slate-600">
                {li === 0 ? 'root' : li === tree.length - 1 ? 'leaves' : `level ${li}`}
              </span>
              <div className="flex flex-wrap gap-3">
                {level.map((n, ni) => {
                  const inPath = searchPath?.path[li]
                  const highlight = inPath &&
                    JSON.stringify(inPath.keys) === JSON.stringify(n.keys)
                  return (
                    <div key={ni} className="flex items-center gap-1">
                      <Node node={n} highlight={highlight}
                        chosen={highlight && n.leaf ? searchPath.key : null} />
                      {n.leaf && n.next && (
                        <span className="text-emerald-600">→</span>
                      )}
                    </div>
                  )
                })}
              </div>
            </div>
          ))}
        </div>
        <p className="mt-4 text-xs text-slate-500">
          <span className="text-sky-400">Blue</span> = internal (separators only) ·
          <span className="ml-2 text-emerald-400">Green</span> = leaf (actual keys) ·
          <span className="ml-2 text-emerald-600">→</span> = sibling pointer
        </p>
      </Card>

      {searchPath && (
        <Card>
          <h3 className="mb-3 text-sm font-medium text-slate-300">
            Search path for {searchPath.key}
          </h3>
          <div className="space-y-1.5">
            {searchPath.path.map((p, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg bg-slate-800/40 px-3 py-2 text-xs">
                <span className="w-20 text-slate-500">
                  {p.leaf ? 'leaf' : `level ${i}`}
                </span>
                <span className="font-mono text-slate-300">[{p.keys.join(', ')}]</span>
                {!p.leaf && (
                  <span className="text-slate-500">
                    → follow child {p.chose}
                  </span>
                )}
                {p.leaf && (
                  <span className={p.found ? 'text-emerald-300' : 'text-rose-300'}>
                    {p.found ? 'FOUND' : 'not present'}
                  </span>
                )}
              </div>
            ))}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            {searchPath.path.length} node visits for {keyCount} keys. A sequential
            scan would need {keyCount} comparisons — this is the O(log n) vs O(n)
            difference the indexing benchmarks measure.
          </p>
        </Card>
      )}

      {log.length > 0 && (
        <Card>
          <h3 className="mb-3 text-sm font-medium text-slate-300">
            Operation log
          </h3>
          <div className="space-y-1 font-mono text-[11px]">
            {log.map((l, i) => (
              <p key={i} className={
                l.includes('split') || l.includes('overflow')
                  ? 'text-amber-300' : 'text-slate-400'}>
                {l}
              </p>
            ))}
          </div>
        </Card>
      )}

      <Card>
        <h3 className="mb-3 text-sm font-medium text-slate-300">
          Why B+ tree, not B tree or hash
        </h3>
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg bg-slate-800/40 p-3">
            <p className="text-xs font-medium text-emerald-300">B+ tree</p>
            <p className="mt-1 text-xs text-slate-500">
              Data only in leaves, leaves linked. Range scans walk the leaf
              chain without revisiting internal nodes. PostgreSQL's default.
            </p>
          </div>
          <div className="rounded-lg bg-slate-800/40 p-3">
            <p className="text-xs font-medium text-sky-300">B tree</p>
            <p className="mt-1 text-xs text-slate-500">
              Data in every node. Slightly faster for a lucky point lookup,
              but range scans must traverse up and down repeatedly.
            </p>
          </div>
          <div className="rounded-lg bg-slate-800/40 p-3">
            <p className="text-xs font-medium text-violet-300">Hash</p>
            <p className="mt-1 text-xs text-slate-500">
              O(1) equality, but hashing destroys ordering — no ranges,
              no sorting, no prefix matching.
            </p>
          </div>
        </div>
      </Card>
    </div>
  )
}
