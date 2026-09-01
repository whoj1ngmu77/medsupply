"""Transaction failure, rollback, savepoints and durability.

Demonstrates ATOMICITY (all or nothing) and DURABILITY (committed
work survives) using PostgreSQL's WAL.
"""
from sqlalchemy import text

from app.db.postgres import SessionLocal


def _snapshot(db, demo_id):
    r = db.execute(text("""
        SELECT qty_on_hand, qty_reserved FROM demo_inventory
        WHERE demo_id = :d
    """), {"d": demo_id}).mappings().one()
    return dict(r)


def rollback_demo() -> dict:
    """A multi-statement transaction fails partway. Nothing persists."""
    db = SessionLocal()
    steps = []
    try:
        db.execute(text(
            "UPDATE demo_inventory SET qty_on_hand = 100, qty_reserved = 0"))
        db.commit()

        demo_id = db.execute(text(
            "SELECT demo_id FROM demo_inventory ORDER BY demo_id LIMIT 1"
        )).scalar_one()

        before = _snapshot(db, demo_id)
        steps.append({"step": "BEGIN", "detail": "transaction started",
                      "state": before})

        db.execute(text("""
            UPDATE demo_inventory SET qty_reserved = qty_reserved + 40
            WHERE demo_id = :d
        """), {"d": demo_id})
        steps.append({"step": "UPDATE 1", "detail": "reserved += 40 (uncommitted)",
                      "state": _snapshot(db, demo_id)})

        db.execute(text("""
            UPDATE demo_inventory SET qty_reserved = qty_reserved + 30
            WHERE demo_id = :d
        """), {"d": demo_id})
        steps.append({"step": "UPDATE 2", "detail": "reserved += 30 (uncommitted)",
                      "state": _snapshot(db, demo_id)})

        # This violates chk_demo_reserved (qty_reserved <= qty_on_hand).
        failed = False
        try:
            db.execute(text("""
                UPDATE demo_inventory SET qty_reserved = qty_reserved + 50
                WHERE demo_id = :d
            """), {"d": demo_id})
            steps.append({"step": "UPDATE 3", "detail": "reserved += 50",
                          "state": _snapshot(db, demo_id)})
        except Exception as exc:
            failed = True
            steps.append({
                "step": "CONSTRAINT VIOLATION",
                "detail": ("reserved would reach 120 > on_hand 100; "
                           "CHECK constraint chk_demo_reserved rejected it"),
                "error": str(exc.orig)[:200] if hasattr(exc, "orig")
                         else str(exc)[:200],
            })

        db.rollback()
        after = _snapshot(db, demo_id)
        steps.append({"step": "ROLLBACK",
                      "detail": "entire transaction undone",
                      "state": after})

        return {
            "demo": "Transaction rollback (ATOMICITY)",
            "constraint_fired": failed,
            "steps": steps,
            "state_before": before,
            "state_after": after,
            "atomicity_held": after == before,
            "explanation": (
                "Updates 1 and 2 succeeded and were visible INSIDE the "
                "transaction. Update 3 violated a CHECK constraint. On "
                "ROLLBACK, all three were discarded — the two successful "
                "updates did not survive. Atomicity means all or nothing, "
                "not most."),
            "log_based_recovery": (
                "PostgreSQL writes every change to the Write-Ahead Log "
                "BEFORE modifying data pages (the WAL rule). On rollback "
                "or crash, uncommitted changes are undone from the log. "
                "This is IMMEDIATE UPDATE with UNDO: data pages may be "
                "written before commit, so undo information is required. "
                "DEFERRED UPDATE (no-undo) would buffer all writes until "
                "commit — simpler recovery, but unusable for long "
                "transactions."),
        }
    finally:
        db.close()


def savepoint_demo() -> dict:
    """Partial rollback: undo one step without losing the whole transaction."""
    db = SessionLocal()
    steps = []
    try:
        db.execute(text(
            "UPDATE demo_inventory SET qty_on_hand = 100, qty_reserved = 0"))
        db.commit()

        demo_id = db.execute(text(
            "SELECT demo_id FROM demo_inventory ORDER BY demo_id LIMIT 1"
        )).scalar_one()

        before = _snapshot(db, demo_id)
        steps.append({"step": "BEGIN", "state": before})

        db.execute(text("""
            UPDATE demo_inventory SET qty_reserved = qty_reserved + 30
            WHERE demo_id = :d
        """), {"d": demo_id})
        steps.append({"step": "UPDATE A", "detail": "reserved += 30",
                      "state": _snapshot(db, demo_id)})

        sp = db.begin_nested()
        steps.append({"step": "SAVEPOINT sp1", "detail": "marker set"})

        try:
            db.execute(text("""
                UPDATE demo_inventory SET qty_reserved = qty_reserved + 200
                WHERE demo_id = :d
            """), {"d": demo_id})
            steps.append({"step": "UPDATE B", "detail": "reserved += 200"})
        except Exception as exc:
            sp.rollback()
            steps.append({
                "step": "ROLLBACK TO sp1",
                "detail": ("Update B violated the CHECK constraint and was "
                           "undone; Update A survives"),
                "error": str(exc.orig)[:150] if hasattr(exc, "orig")
                         else str(exc)[:150],
                "state": _snapshot(db, demo_id),
            })

        db.execute(text("""
            UPDATE demo_inventory SET qty_reserved = qty_reserved + 20
            WHERE demo_id = :d
        """), {"d": demo_id})
        steps.append({"step": "UPDATE C", "detail": "reserved += 20",
                      "state": _snapshot(db, demo_id)})

        db.commit()
        final = _snapshot(db, demo_id)
        steps.append({"step": "COMMIT", "detail": "durable", "state": final})

        return {
            "demo": "Savepoints (partial rollback)",
            "steps": steps,
            "expected_reserved": 50,
            "actual_reserved": final["qty_reserved"],
            "correct": final["qty_reserved"] == 50,
            "explanation": (
                "A savepoint is a marker inside a transaction. ROLLBACK TO "
                "SAVEPOINT undoes work after the marker while keeping "
                "earlier work and the transaction itself alive. Final "
                "reserved = 30 (A) + 20 (C) = 50; B's 200 was discarded."),
            "why_it_matters": (
                "In the allocation engine, a savepoint would let one failing "
                "batch be skipped without abandoning the whole multi-batch "
                "allocation. MedSupply currently fails the entire allocation "
                "instead — a deliberate choice, since a partially-filled "
                "emergency order is worse than a clearly rejected one."),
        }
    finally:
        db.close()


def durability_demo() -> dict:
    """Committed data survives; uncommitted data does not."""
    db1 = SessionLocal()
    db2 = SessionLocal()
    try:
        db1.execute(text(
            "UPDATE demo_inventory SET qty_on_hand = 100, qty_reserved = 0"))
        db1.commit()

        demo_id = db1.execute(text(
            "SELECT demo_id FROM demo_inventory ORDER BY demo_id LIMIT 1"
        )).scalar_one()

        db1.execute(text("""
            UPDATE demo_inventory SET qty_reserved = 25 WHERE demo_id = :d
        """), {"d": demo_id})

        # Second connection cannot see uncommitted work (READ COMMITTED).
        other_sees = db2.execute(text(
            "SELECT qty_reserved FROM demo_inventory WHERE demo_id = :d"
        ), {"d": demo_id}).scalar_one()
        db2.commit()

        db1.commit()

        after_commit = db2.execute(text(
            "SELECT qty_reserved FROM demo_inventory WHERE demo_id = :d"
        ), {"d": demo_id}).scalar_one()

        wal = db1.execute(text("""
            SELECT pg_current_wal_lsn() AS lsn,
                   pg_walfile_name(pg_current_wal_lsn()) AS wal_file
        """)).mappings().one()

        settings = db1.execute(text("""
            SELECT name, setting FROM pg_settings
            WHERE name IN ('fsync', 'synchronous_commit', 'wal_level',
                           'full_page_writes')
            ORDER BY name
        """)).mappings().all()

        return {
            "demo": "Isolation & Durability",
            "uncommitted_visible_to_other_session": other_sees,
            "after_commit_visible": after_commit,
            "isolation_held": other_sees == 0 and after_commit == 25,
            "wal_position": dict(wal),
            "durability_settings": [dict(s) for s in settings],
            "explanation": (
                "Before COMMIT, session 2 read qty_reserved = 0 — "
                "uncommitted changes are invisible under READ COMMITTED "
                "(no dirty reads). After COMMIT it read 25."),
            "durability_explanation": (
                "With fsync=on and synchronous_commit=on, COMMIT does not "
                "return until the WAL record is flushed to durable storage. "
                "If the server crashed immediately after, replay would "
                "restore the committed change. The WAL LSN above is the "
                "exact log position."),
        }
    finally:
        db1.close()
        db2.close()


def transaction_log_view() -> dict:
    """Live view of the application-level audit log plus WAL state."""
    db = SessionLocal()
    try:
        events = db.execute(text("""
            SELECT event_id, request_id, batch_id, event_type,
                   old_value, new_value, txn_note, actor_type, occurred_at
            FROM allocation_event ORDER BY event_id DESC LIMIT 20
        """)).mappings().all()

        wal = db.execute(text("""
            SELECT pg_current_wal_lsn() AS current_lsn,
                   pg_walfile_name(pg_current_wal_lsn()) AS current_wal_file,
                   pg_size_pretty(
                       pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')
                   ) AS wal_generated
        """)).mappings().one()

        return {
            "application_audit_log": [dict(e) for e in events],
            "wal_state": dict(wal),
            "note": ("allocation_event is an APPLICATION-level log for "
                     "business auditing. PostgreSQL's WAL is the "
                     "SYSTEM-level log used for crash recovery. They serve "
                     "different purposes and should not be confused."),
        }
    finally:
        db.close()
