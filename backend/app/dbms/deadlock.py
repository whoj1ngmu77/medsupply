"""Deadlock demonstration on isolated demo tables.

A real deadlock: PostgreSQL's detector fires, chooses a victim, and
aborts it with SQLSTATE 40P01. Nothing is simulated.

SAFETY: only demo_inventory rows are involved. Production allocation
(Phase 6) locks batches in a deterministic order (expiry_date, batch_id)
and therefore CANNOT deadlock this way.
"""
import threading
import time

from sqlalchemy import text

from app.db.postgres import SessionLocal


def _reset():
    db = SessionLocal()
    try:
        db.execute(text(
            "UPDATE demo_inventory SET qty_on_hand = 100, qty_reserved = 0"))
        db.commit()
        rows = db.execute(text(
            "SELECT demo_id, label FROM demo_inventory ORDER BY demo_id"
        )).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


def _deadlock_worker(name, first_id, second_id, log, lock, barrier, delay):
    """Lock `first_id`, pause, then try `second_id`.

    Two workers with SWAPPED ids produce a cycle:
        T1 holds A, wants B
        T2 holds B, wants A
    """
    db = SessionLocal()

    def emit(step, detail, ok=True):
        with lock:
            log.append({
                "t": round(time.perf_counter() * 1000, 2),
                "txn": name, "step": step, "detail": detail, "ok": ok,
            })

    try:
        db.execute(text("SET LOCAL lock_timeout = '15000ms'"))
        db.execute(text("SET LOCAL deadlock_timeout = '1s'"))
        emit("BEGIN", "transaction started")

        db.execute(text(
            "SELECT * FROM demo_inventory WHERE demo_id = :d FOR UPDATE"
        ), {"d": first_id})
        emit("LOCK_1", f"acquired exclusive lock on row {first_id}")

        # Both hold their first lock before either requests its second.
        barrier.wait(timeout=10)
        time.sleep(delay)

        emit("LOCK_2_WAIT", f"requesting lock on row {second_id} "
                            f"(held by the other transaction)")

        db.execute(text(
            "SELECT * FROM demo_inventory WHERE demo_id = :d FOR UPDATE"
        ), {"d": second_id})

        emit("LOCK_2", f"acquired lock on row {second_id}")
        db.commit()
        emit("COMMIT", "committed — this transaction survived")

        with lock:
            log.append({"txn": name, "step": "OUTCOME", "detail": "SURVIVED"})

    except Exception as exc:
        db.rollback()
        msg = str(exc).lower()
        if "deadlock detected" in msg:
            emit("DEADLOCK_VICTIM",
                 "PostgreSQL detected a cycle and aborted this transaction "
                 "(SQLSTATE 40P01)", ok=False)
            outcome = "VICTIM"
        else:
            emit("ERROR", f"{type(exc).__name__}: {str(exc)[:200]}", ok=False)
            outcome = "ERROR"
        with lock:
            log.append({"txn": name, "step": "OUTCOME", "detail": outcome})
    finally:
        db.close()


def run_deadlock_demo() -> dict:
    rows = _reset()
    if len(rows) < 2:
        raise RuntimeError("demo_inventory needs at least 2 rows; "
                           "re-run backend/sql/02_demo_tables.sql")

    a, b = rows[0], rows[1]
    log = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    # SWAPPED lock order — this is the entire cause of the deadlock.
    t1 = threading.Thread(target=_deadlock_worker, args=(
        "T1", a["demo_id"], b["demo_id"], log, lock, barrier, 0.2))
    t2 = threading.Thread(target=_deadlock_worker, args=(
        "T2", b["demo_id"], a["demo_id"], log, lock, barrier, 0.2))

    start = time.perf_counter()
    t1.start()
    t2.start()
    t1.join(timeout=25)
    t2.join(timeout=25)
    elapsed = round((time.perf_counter() - start) * 1000, 1)

    outcomes = {e["txn"]: e["detail"]
                for e in log if e.get("step") == "OUTCOME"}
    victim = next((k for k, v in outcomes.items() if v == "VICTIM"), None)

    return {
        "resource_a": {"id": a["demo_id"], "label": a["label"]},
        "resource_b": {"id": b["demo_id"], "label": b["label"]},
        "lock_order": {
            "T1": f"{a['label']} then {b['label']}",
            "T2": f"{b['label']} then {a['label']}  <-- REVERSED",
        },
        "elapsed_ms": elapsed,
        "outcomes": outcomes,
        "victim": victim,
        "deadlock_occurred": victim is not None,
        "timeline": sorted([e for e in log if "t" in e], key=lambda e: e["t"]),
        "wait_for_graph": {
            "nodes": [
                {"id": "T1", "label": f"T1 (holds {a['label']})"},
                {"id": "T2", "label": f"T2 (holds {b['label']})"},
            ],
            "edges": [
                {"from": "T1", "to": "T2",
                 "label": f"waiting for {b['label']}"},
                {"from": "T2", "to": "T1",
                 "label": f"waiting for {a['label']}"},
            ],
            "cycle": "T1 -> T2 -> T1",
            "note": "A cycle in the wait-for graph IS the definition of "
                    "deadlock.",
        },
        "four_conditions": [
            {"condition": "Mutual exclusion",
             "present": "FOR UPDATE grants exclusive access to a row"},
            {"condition": "Hold and wait",
             "present": "Each transaction holds one lock while requesting "
                        "another"},
            {"condition": "No preemption",
             "present": "A lock cannot be forcibly taken from its holder"},
            {"condition": "Circular wait",
             "present": "T1 waits on T2, T2 waits on T1"},
        ],
        "detection": (
            "PostgreSQL runs a wait-for graph cycle check when a lock wait "
            "exceeds deadlock_timeout (set to 1s here). On finding a cycle "
            "it aborts one transaction with SQLSTATE 40P01. Detection is "
            "lazy, not continuous — checking on every lock request would "
            "cost more than the rare deadlock it prevents."),
        "prevention_in_production": (
            "MedSupply's allocation engine orders its FOR UPDATE by "
            "(expiry_date ASC, batch_id ASC). Every transaction acquires "
            "locks in the same sequence, so circular wait cannot arise. "
            "Breaking any one of the four conditions prevents deadlock; "
            "consistent lock ordering breaks circular wait, and it is the "
            "cheapest of the four to enforce."),
        "why_isolated": (
            "This demo runs only on demo_inventory. Deliberately deadlocking "
            "production inventory would be reckless — hence the separate "
            "tables created in Phase 3."),
    }


def deadlock_stats() -> dict:
    """Server-wide deadlock counter since the database was created."""
    db = SessionLocal()
    try:
        r = db.execute(text("""
            SELECT deadlocks, xact_commit, xact_rollback,
                   stats_reset
            FROM pg_stat_database WHERE datname = current_database()
        """)).mappings().one()
        return dict(r)
    finally:
        db.close()
