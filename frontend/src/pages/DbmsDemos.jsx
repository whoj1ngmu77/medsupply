import { useState } from 'react'
import { PageHeader } from '../components/form'
import IndexingLab from './dbms/IndexingLab'
import OptimizationLab from './dbms/OptimizationLab'
import ConcurrencyLab from './dbms/ConcurrencyLab'
import DeadlockLab from './dbms/DeadlockLab'
import RecoveryLab from './dbms/RecoveryLab'
import NoSqlLab from './dbms/NoSqlLab'
import BPlusTree from './dbms/BPlusTree'
import Hashing from './dbms/Hashing'

const TABS = [
  ['indexing', 'Indexing', IndexingLab],
  ['optimization', 'Query optimization', OptimizationLab],
  ['concurrency', 'Concurrency & 2PL', ConcurrencyLab],
  ['deadlock', 'Deadlock', DeadlockLab],
  ['recovery', 'Recovery', RecoveryLab],
  ['nosql', 'NoSQL & CAP', NoSqlLab],
  ['bplustree', 'B+ Tree', BPlusTree],
  ['hashing', 'Hashing', Hashing],
]

export default function DbmsDemos() {
  const [tab, setTab] = useState('indexing')
  const Active = TABS.find(([k]) => k === tab)[2]

  return (
    <div>
      <PageHeader title="DBMS Demonstrations"
        subtitle="Every result below is measured live against this database — nothing is pre-recorded" />

      <div className="mb-6 flex flex-wrap gap-2 border-b border-slate-800 pb-3">
        {TABS.map(([k, label]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`rounded-lg px-4 py-1.5 text-sm transition ${
              tab === k
                ? 'bg-emerald-500/10 text-emerald-300'
                : 'text-slate-400 hover:bg-slate-800'}`}>
            {label}
          </button>
        ))}
      </div>

      <Active />
    </div>
  )
}
