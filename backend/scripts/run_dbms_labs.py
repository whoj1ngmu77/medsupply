"""Run every Phase 9 lab and print readable output for the report."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.dbms import concurrency, deadlock, recovery

BAR = "=" * 72


def hdr(t):
    print(f"\n{BAR}\n  {t}\n{BAR}")


hdr("A. LOST UPDATE — no locking (UNSAFE)")
r = concurrency.run_concurrency_demo(use_lock=False)
for e in r["timeline"]:
    print(f"  [{e['t']:>9.2f}ms] {e['txn']}  {e['step']:<16} {e['detail']}")
print(f"\n  Stock: {r['stock']}   T1 wanted {r['requests']['T1']}, "
      f"T2 wanted {r['requests']['T2']}")
print(f"  Granted to: {r['granted_to']}  (total {r['total_granted']} units)")
print(f"  Final: {r['after']}")
print(f"  OVER-ALLOCATED: {r['over_allocated']}")
print(f"  {r['explanation']}")

hdr("B. SAME SCENARIO — SELECT ... FOR UPDATE (SAFE)")
r = concurrency.run_concurrency_demo(use_lock=True)
for e in r["timeline"]:
    print(f"  [{e['t']:>9.2f}ms] {e['txn']}  {e['step']:<16} {e['detail']}")
print(f"\n  Granted to: {r['granted_to']}  (total {r['total_granted']} units)")
print(f"  Final: {r['after']}")
print(f"  CORRECT: {r['correct']}")
print(f"  {r['explanation']}")

hdr("C. DEADLOCK")
d = deadlock.run_deadlock_demo()
print(f"  T1 lock order: {d['lock_order']['T1']}")
print(f"  T2 lock order: {d['lock_order']['T2']}\n")
for e in d["timeline"]:
    mark = " " if e["ok"] else "!"
    print(f" {mark}[{e['t']:>9.2f}ms] {e['txn']}  {e['step']:<18} {e['detail']}")
print(f"\n  Deadlock occurred: {d['deadlock_occurred']}")
print(f"  Victim: {d['victim']}")
print(f"  Wait-for cycle: {d['wait_for_graph']['cycle']}")
print("\n  Coffman conditions:")
for c in d["four_conditions"]:
    print(f"    - {c['condition']:<20} {c['present']}")
print(f"\n  Detection: {d['detection']}")
print(f"\n  Prevention: {d['prevention_in_production']}")

hdr("D. ROLLBACK (ATOMICITY)")
r = recovery.rollback_demo()
for s in r["steps"]:
    st = f"  state={s['state']}" if "state" in s else ""
    print(f"  {s['step']:<24} {s.get('detail','')}{st}")
print(f"\n  Atomicity held: {r['atomicity_held']}")
print(f"  {r['explanation']}")
print(f"\n  {r['log_based_recovery']}")

hdr("E. SAVEPOINTS (PARTIAL ROLLBACK)")
r = recovery.savepoint_demo()
for s in r["steps"]:
    st = f"  state={s['state']}" if "state" in s else ""
    print(f"  {s['step']:<24} {s.get('detail','')}{st}")
print(f"\n  Expected reserved=50, got {r['actual_reserved']}  "
      f"-> {'PASS' if r['correct'] else 'FAIL'}")
print(f"  {r['explanation']}")

hdr("F. ISOLATION & DURABILITY")
r = recovery.durability_demo()
print(f"  Other session saw (uncommitted): {r['uncommitted_visible_to_other_session']}")
print(f"  Other session saw (after commit): {r['after_commit_visible']}")
print(f"  Isolation held: {r['isolation_held']}")
print(f"  WAL position: {r['wal_position']['lsn']} "
      f"in {r['wal_position']['wal_file']}")
print("  Durability settings:")
for s in r["durability_settings"]:
    print(f"    {s['name']:<22} = {s['setting']}")
print(f"\n  {r['durability_explanation']}")

print(f"\n{BAR}\n  ALL LABS COMPLETE\n{BAR}")
