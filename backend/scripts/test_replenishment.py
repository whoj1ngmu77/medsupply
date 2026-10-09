"""Replenishment scan: correctness checks.

The meaningful invariant is NOT "a second scan creates zero orders" --
with more policies below threshold than the scan limit, a second scan
legitimately covers the next batch.

The invariant is: no (warehouse, medicine) ever has more than one OPEN
order line. That is requirement 6, and it is enforced by the partial
unique index uq_open_po_line, not by application logic.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.db.postgres import SessionLocal
from app.services import replenishment_service as rs

db = SessionLocal()
failures = []
try:
    # -----------------------------------------------------------------
    print("=" * 70)
    print("  1. DRY RUN changes nothing")
    print("=" * 70)
    before = db.execute(text("SELECT COUNT(*) FROM purchase_order_line")).scalar_one()
    d = rs.run_scan(db, dry_run=True, limit=5)
    after = db.execute(text("SELECT COUNT(*) FROM purchase_order_line")).scalar_one()
    print(f"  lines {before} -> {after}   {'PASS' if before == after else 'FAIL'}")
    if before != after:
        failures.append("dry run mutated state")

    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  2. SCAN EVERYTHING, then rescan")
    print("=" * 70)
    r1 = rs.run_scan(db, limit=1000, triggered_by="MANUAL")
    db.commit()
    print(f"  scan 1: due={r1['policies_due']:<4} created={r1['orders_created']}")

    r2 = rs.run_scan(db, limit=1000, triggered_by="MANUAL")
    db.commit()
    print(f"  scan 2: due={r2['policies_due']:<4} created={r2['orders_created']}")
    ok = r2["orders_created"] == 0
    print(f"  second scan created zero: {'PASS' if ok else 'FAIL'}")
    if not ok:
        failures.append(f"rescan created {r2['orders_created']} orders")

    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  3. NO DUPLICATE OPEN LINES  (the real invariant)")
    print("=" * 70)
    dupes = db.execute(text("""
        SELECT warehouse_id, medicine_id, COUNT(*) AS n
        FROM purchase_order_line
        WHERE line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')
        GROUP BY warehouse_id, medicine_id HAVING COUNT(*) > 1
    """)).all()
    total = db.execute(text(
        "SELECT COUNT(*) FROM purchase_order_line")).scalar_one()
    print(f"  {total} open lines, {len(dupes)} duplicated pairs "
          f"-> {'PASS' if not dupes else 'FAIL'}")
    if dupes:
        failures.append(f"{len(dupes)} duplicate pairs")

    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  4. THE DATABASE REFUSES A DUPLICATE")
    print("=" * 70)
    try:
        with db.begin_nested():
            db.execute(text("""
                INSERT INTO purchase_order_line
                    (po_id, warehouse_id, medicine_id, qty_ordered,
                     unit_price, line_status)
                -- a DIFFERENT po_id, so uq_po_line (po_id, medicine_id)
                -- cannot fire and only uq_open_po_line can reject this
                SELECT (SELECT MAX(po_id) FROM purchase_order),
                       l.warehouse_id, l.medicine_id, 999, 10.00, 'PENDING'
                FROM purchase_order_line l
                WHERE l.line_status = 'PENDING'
                  AND l.po_id <> (SELECT MAX(po_id) FROM purchase_order)
                ORDER BY l.po_line_id LIMIT 1
            """))
        print("  FAIL -- the duplicate was accepted")
        failures.append("index did not block a hand-written duplicate")
        db.rollback()
    except IntegrityError as exc:
        name = "uq_open_po_line" in str(exc.orig)
        print(f"  rejected by uq_open_po_line: {'PASS' if name else 'FAIL'}")
        print(f"  {str(exc.orig).splitlines()[0][:100]}")
        if not name:
            failures.append("wrong constraint fired")
        db.rollback()

    # -----------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  5. AUDIT LOG")
    print("=" * 70)
    for row in db.execute(text("""
        SELECT decision, COUNT(*) AS n FROM replenishment_log
        GROUP BY decision ORDER BY n DESC
    """)).mappings():
        print(f"   {row['decision']:<28} {row['n']}")

    print("\n" + "=" * 70)
    print(f"  RESULT: {'ALL PASS' if not failures else 'FAILURES: ' + '; '.join(failures)}")
    print("=" * 70)
finally:
    db.close()
