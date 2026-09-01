"""Concurrency control demonstrations on isolated demo tables.

Two real threads, two real database connections, two real transactions.
Nothing is simulated — the interleaving is enforced with barriers so
the race is reproducible rather than luck-dependent.
"""
import threading
import time
from datetime import datetime

from sqlalchemy import text

from app.db.postgres import SessionLocal


def _reset(use_lock: bool, qty: int = 100):
    """Safe mode uses demo_inventory (with CHECK constraint).
    Unsafe mode uses demo_inventory_unsafe (no constraint), so the
    lost update can actually manifest instead of being caught."""
    tbl = "demo_inventory" if use_lock else "demo_inventory_unsafe"
    db = SessionLocal()
    try:
        db.execute(text(f"UPDATE {tbl} SET qty_on_hand = :q, qty_reserved = 0"),
                   {"q": qty})
        db.commit()
        row = db.execute(text(
            f"SELECT demo_id FROM {tbl} ORDER BY demo_id LIMIT 1")).scalar_one()
        return row, tbl
    finally:
        db.close()


def _state(demo_id: int, tbl: str = "demo_inventory") -> dict:
    db = SessionLocal()
    try:
        r = db.execute(text(f"""
            SELECT qty_on_hand, qty_reserved,
                   qty_on_hand - qty_reserved AS available
            FROM {tbl} WHERE demo_id = :d
        """), {"d": demo_id}).mappings().one()
        return dict(r)
    finally:
        db.close()


def _worker(name, demo_id, want, use_lock, log, lock, barrier, read_delay,
            tbl="demo_inventory"):
    """One transaction attempting to reserve `want` units."""
    db = SessionLocal()

    def emit(step, detail):
        with lock:
            log.append({
                "t": round(time.perf_counter() * 1000, 2),
                "txn": name, "step": step, "detail": detail,
            })

    try:
        emit("BEGIN", f"transaction started, wants {want} units")

        clause = "FOR UPDATE" if use_lock else ""
        emit("READ", f"SELECT qty_available {clause or '(no lock)'}")

        # Both transactions read at the same moment. This is the barrier
        # that makes the race deterministic.
        barrier.wait(timeout=10)

        row = db.execute(text(f"""
            SELECT qty_on_hand, qty_reserved,
                   qty_on_hand - qty_reserved AS available
            FROM {tbl} WHERE demo_id = :d {clause}
        """), {"d": demo_id}).mappings().one()

        available = row["available"]
        emit("READ_RESULT",
             f"saw available={available} (on_hand={row['qty_on_hand']}, "
             f"reserved={row['qty_reserved']})")

        # Simulated think time. In the unsafe path this is the window
        # where the other transaction overwrites our read.
        time.sleep(read_delay)

        if available >= want:
            emit("DECIDE", f"{want} <= {available}, proceeding to reserve")
            # CRITICAL: write an ABSOLUTE value computed from the stale
            # read. "SET x = x + n" would be atomic in the database and
            # could never lose an update, which is why the naive version
            # of this demo silently fails to reproduce the bug.
            new_reserved = row["qty_reserved"] + want
            db.execute(text(f"""
                UPDATE {tbl} SET qty_reserved = :nr WHERE demo_id = :d
            """), {"nr": new_reserved, "d": demo_id})
            emit("UPDATE",
                 f"SET qty_reserved = {new_reserved} "
                 f"(computed from stale read {row['qty_reserved']} + {want})")
            db.commit()
            emit("COMMIT", "committed successfully")
            result = "GRANTED"
        else:
            emit("DECIDE", f"{want} > {available}, insufficient stock")
            db.rollback()
            emit("ROLLBACK", "rolled back, nothing reserved")
            result = "REJECTED"

        with lock:
            log.append({"txn": name, "step": "RESULT", "detail": result})

    except Exception as exc:
        db.rollback()
        emit("ERROR", f"{type(exc).__name__}: {str(exc)[:150]}")
    finally:
        db.close()


def run_concurrency_demo(use_lock: bool, qty_a: int = 70,
                         qty_b: int = 50, stock: int = 100) -> dict:
    """Two concurrent reservations against `stock` units.

    use_lock=False reproduces the lost update problem.
    use_lock=True  prevents it with SELECT ... FOR UPDATE.
    """
    demo_id, tbl = _reset(use_lock, qty=stock)
    before = _state(demo_id, tbl)

    log = []
    lock = threading.Lock()
    barrier = threading.Barrier(2)

    # Asymmetric delays so the interleaving is deterministic:
    # A reads, B reads, A writes, B writes.
    t_a = threading.Thread(target=_worker, args=(
        "T1", demo_id, qty_a, use_lock, log, lock, barrier, 0.30, tbl))
    t_b = threading.Thread(target=_worker, args=(
        "T2", demo_id, qty_b, use_lock, log, lock, barrier, 0.60, tbl))

    start = time.perf_counter()
    t_a.start()
    t_b.start()
    t_a.join(timeout=20)
    t_b.join(timeout=20)
    elapsed = round((time.perf_counter() - start) * 1000, 1)

    after = _state(demo_id, tbl)

    granted = [e["txn"] for e in log
               if e.get("step") == "RESULT" and e["detail"] == "GRANTED"]
    total_granted = sum(
        qty_a if t == "T1" else qty_b for t in granted)

    # The failure is that PROMISES exceed stock, not that the stored
    # column exceeds it — the lost update means the column under-reports
    # what was actually granted. Comparing the column would miss the bug.
    over_allocated = total_granted > stock
    units_lost = total_granted - after["qty_reserved"]

    return {
        "mode": "SAFE (SELECT ... FOR UPDATE)" if use_lock
                else "UNSAFE (no locking)",
        "isolation_level": "READ COMMITTED",
        "table": tbl,
        "stock": stock,
        "requests": {"T1": qty_a, "T2": qty_b},
        "before": before,
        "after": after,
        "elapsed_ms": elapsed,
        "granted_to": granted,
        "total_granted": total_granted,
        "over_allocated": over_allocated,
        "units_lost_by_overwrite": units_lost,
        "correct": total_granted <= stock,
        "timeline": sorted(
            [e for e in log if "t" in e], key=lambda e: e["t"]),
        "results": [e for e in log if e.get("step") == "RESULT"],
        "explanation": (
            "Both transactions read the same value before either wrote. "
            "Without a lock, T2's read is stale by the time it writes, so "
            f"{total_granted} units were promised against {stock} in stock — "
            "the LOST UPDATE problem."
            if not use_lock and total_granted > stock else
            "SELECT ... FOR UPDATE took an exclusive row lock at read time. "
            "The second transaction BLOCKED until the first committed, then "
            "re-read the committed value and decided correctly. This is "
            "two-phase locking: locks acquired in a growing phase, released "
            "only at COMMIT (the shrinking phase)."
            if use_lock else
            "No conflict arose on this run — retry, or check that both "
            "threads reached the barrier."),
    }


def lock_monitor() -> list[dict]:
    """Current locks held and waited on. Live pg_locks view."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT l.pid, l.locktype, l.mode, l.granted,
                   c.relname AS table_name,
                   LEFT(a.query, 80) AS query,
                   a.state, a.wait_event_type
            FROM pg_locks l
            LEFT JOIN pg_class c ON c.oid = l.relation
            LEFT JOIN pg_stat_activity a ON a.pid = l.pid
            WHERE l.pid <> pg_backend_pid()
              AND (c.relname IS NULL OR c.relname NOT LIKE 'pg_%')
            ORDER BY l.granted, l.pid
        """)).mappings().all()
        return [dict(r) for r in rows]
    finally:
        db.close()


LOCK_COMPATIBILITY = {
    "title": "Lock Compatibility Matrix (PostgreSQL row-level)",
    "modes": ["FOR KEY SHARE", "FOR SHARE", "FOR NO KEY UPDATE", "FOR UPDATE"],
    "matrix": [
        {"requested": "FOR KEY SHARE",
         "FOR KEY SHARE": True, "FOR SHARE": True,
         "FOR NO KEY UPDATE": True, "FOR UPDATE": False},
        {"requested": "FOR SHARE",
         "FOR KEY SHARE": True, "FOR SHARE": True,
         "FOR NO KEY UPDATE": False, "FOR UPDATE": False},
        {"requested": "FOR NO KEY UPDATE",
         "FOR KEY SHARE": True, "FOR SHARE": False,
         "FOR NO KEY UPDATE": False, "FOR UPDATE": False},
        {"requested": "FOR UPDATE",
         "FOR KEY SHARE": False, "FOR SHARE": False,
         "FOR NO KEY UPDATE": False, "FOR UPDATE": False},
    ],
    "note": ("MedSupply's allocation uses FOR UPDATE, which conflicts with "
             "every other mode. That is deliberate: reserving inventory must "
             "exclude all concurrent access to the row."),
}
