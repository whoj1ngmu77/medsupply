import { useState } from 'react'
import { api } from '../../api/client'
import { Card, ErrorBox, Table } from '../../components/ui'
import { Explain, Metric, RunButton } from '../../components/demo'

const StepList = ({ steps }) => (
  <div className="space-y-1.5">
    {steps.map((s, i) => (
      <div key={i} className="flex items-start gap-3 rounded-lg bg-slate-800/40 px-3 py-2">
        <span className={`w-44 shrink-0 font-mono text-xs ${
          s.step.includes('ROLLBACK') || s.step.includes('VIOLATION')
            ? 'text-rose-300'
            : s.step === 'COMMIT' ? 'text-emerald-300' : 'text-sky-300'}`}>
          {s.step}
        </span>
        <div className="flex-1">
          <p className="text-xs text-slate-400">{s.detail}</p>
          {s.error && (
            <p className="mt-1 font-mono text-[10px] text-rose-400">{s.error}</p>
          )}
          {s.state && (
            <p className="mt-0.5 font-mono text-[11px] text-slate-500">
              on_hand={s.state.qty_on_hand} reserved={s.state.qty_reserved}
            </p>
          )}
        </div>
      </div>
    ))}
  </div>
)

export default function RecoveryLab() {
  const [results, setResults] = useState({})
  const [running, setRunning] = useState(null)
  const [error, setError] = useState(null)

  const run = async (key, path) => {
    setRunning(key)
    setError(null)
    try {
      const r = await api.post(path)
      setResults((s) => ({ ...s, [key]: r }))
    } catch (e) {
      setError(e.message)
    } finally {
      setRunning(null)
    }
  }

  const rollback = results.rollback
  const savepoint = results.savepoint
  const durability = results.durability

  return (
    <div className="space-y-5">
      <Explain title="Atomicity, savepoints and durability">
        <p>
          PostgreSQL writes every change to the Write-Ahead Log <em>before</em>
          modifying data pages. On rollback or crash, uncommitted changes are
          undone from the log — immediate update with UNDO.
        </p>
        <p className="text-slate-500">
          The <code className="text-slate-300">allocation_event</code> table is an
          application-level audit log for business history. The WAL is the
          system-level log used for crash recovery. They are not the same thing.
        </p>
      </Explain>

      {error && <ErrorBox message={error} />}

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-slate-300">
              Rollback — atomicity
            </h3>
            <p className="text-xs text-slate-500">
              Two successful updates, then a constraint violation. All three discarded.
            </p>
          </div>
          <RunButton onClick={() => run('rollback', '/dbms/recovery/rollback')}
            running={running === 'rollback'}>
            Run
          </RunButton>
        </div>

        {rollback && (
          <div className="mt-4 space-y-3">
            <StepList steps={rollback.steps} />
            <div className={`rounded-lg p-3 text-sm ${
              rollback.atomicity_held
                ? 'bg-emerald-500/10 text-emerald-300'
                : 'bg-rose-500/10 text-rose-300'}`}>
              <p className="font-medium">
                Atomicity held: {String(rollback.atomicity_held)}
              </p>
              <p className="mt-1 text-xs text-slate-400">{rollback.explanation}</p>
            </div>
            <div className="rounded-lg bg-slate-800/40 p-3">
              <p className="mb-1 text-xs uppercase tracking-wide text-slate-500">
                Log-based recovery
              </p>
              <p className="text-xs text-slate-400">{rollback.log_based_recovery}</p>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-slate-300">
              Savepoints — partial rollback
            </h3>
            <p className="text-xs text-slate-500">
              Undo one step without abandoning the transaction
            </p>
          </div>
          <RunButton onClick={() => run('savepoint', '/dbms/recovery/savepoint')}
            running={running === 'savepoint'}>
            Run
          </RunButton>
        </div>

        {savepoint && (
          <div className="mt-4 space-y-3">
            <StepList steps={savepoint.steps} />
            <div className="grid grid-cols-3 gap-2">
              <Metric label="Expected" value={savepoint.expected_reserved} />
              <Metric label="Actual" value={savepoint.actual_reserved}
                accent={savepoint.correct ? 'emerald' : 'rose'} />
              <Metric label="Result" value={savepoint.correct ? 'PASS' : 'FAIL'}
                accent={savepoint.correct ? 'emerald' : 'rose'} />
            </div>
            <div className="rounded-lg bg-slate-800/40 p-3">
              <p className="text-xs text-slate-400">{savepoint.explanation}</p>
              <p className="mt-2 text-xs text-emerald-400">
                {savepoint.why_it_matters}
              </p>
            </div>
          </div>
        )}
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-medium text-slate-300">
              Isolation and durability
            </h3>
            <p className="text-xs text-slate-500">
              Uncommitted changes are invisible to other sessions
            </p>
          </div>
          <RunButton onClick={() => run('durability', '/dbms/recovery/durability')}
            running={running === 'durability'}>
            Run
          </RunButton>
        </div>

        {durability && (
          <div className="mt-4 space-y-3">
            <div className="grid grid-cols-3 gap-2">
              <Metric label="Other session saw (uncommitted)"
                value={durability.uncommitted_visible_to_other_session} />
              <Metric label="After commit"
                value={durability.after_commit_visible} accent="emerald" />
              <Metric label="Isolation held"
                value={String(durability.isolation_held)}
                accent={durability.isolation_held ? 'emerald' : 'rose'} />
            </div>
            <p className="text-xs text-slate-400">{durability.explanation}</p>

            <div className="rounded-lg bg-slate-800/40 p-3">
              <p className="mb-2 text-xs uppercase tracking-wide text-slate-500">
                WAL position
              </p>
              <p className="font-mono text-xs text-slate-400">
                {durability.wal_position.lsn} in {durability.wal_position.wal_file}
              </p>
            </div>

            <Table rows={durability.durability_settings} empty=""
              columns={[
                { key: 'name', label: 'Setting' },
                { key: 'setting', label: 'Value',
                  render: (r) => (
                    <span className="font-mono text-emerald-300">{r.setting}</span>
                  ) },
              ]} />
            <p className="text-xs text-slate-400">
              {durability.durability_explanation}
            </p>
          </div>
        )}
      </Card>
    </div>
  )
}
