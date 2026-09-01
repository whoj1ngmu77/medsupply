"""Reproduce the brief's scenario: 100 units, requests for 70 and 50."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.services.allocation_service import AllocationError, allocate_request

MED = 999


def setup(db):
    db.execute(text("DELETE FROM allocation_event WHERE request_id IN "
                    "(SELECT request_id FROM emergency_request "
                    " WHERE medicine_id = :m)"), {"m": MED})
    db.execute(text("DELETE FROM allocation WHERE request_id IN "
                    "(SELECT request_id FROM emergency_request "
                    " WHERE medicine_id = :m)"), {"m": MED})
    db.execute(text("DELETE FROM emergency_request WHERE medicine_id = :m"),
               {"m": MED})
    db.execute(text("DELETE FROM inventory_batch WHERE medicine_id = :m"),
               {"m": MED})
    db.execute(text("DELETE FROM medicine WHERE medicine_id = :m"), {"m": MED})

    db.execute(text("""
        INSERT INTO medicine (medicine_id, name, category_id,
                              manufacturer_id, unit, criticality)
        VALUES (:m, 'TEST-SCENARIO-MED', 1, 1, 'vial', 'LIFE_SAVING')
    """), {"m": MED})
    db.execute(text("""
        INSERT INTO inventory_batch (warehouse_id, medicine_id, batch_number,
                                     qty_on_hand, qty_reserved, expiry_date)
        VALUES (1, :m, 'TEST-BATCH-100', 100, 0, CURRENT_DATE + 365)
    """), {"m": MED})
    a = db.execute(text("""
        INSERT INTO emergency_request (hospital_id, medicine_id,
                                       qty_requested, priority)
        VALUES (1, :m, 70, 'CRITICAL') RETURNING request_id
    """), {"m": MED}).scalar_one()
    b = db.execute(text("""
        INSERT INTO emergency_request (hospital_id, medicine_id,
                                       qty_requested, priority)
        VALUES (2, :m, 50, 'CRITICAL') RETURNING request_id
    """), {"m": MED}).scalar_one()
    db.commit()
    return a, b


def state(db):
    r = db.execute(text(
        "SELECT qty_on_hand, qty_reserved, qty_on_hand - qty_reserved AS avail "
        "FROM inventory_batch WHERE medicine_id = :m"), {"m": MED}).mappings().one()
    return dict(r)


db = SessionLocal()
req_a, req_b = setup(db)
print(f"Setup: batch has 100 units. Request A={req_a} wants 70, "
      f"Request B={req_b} wants 50.\n")

print("--- Allocating A (70) ---")
try:
    res = allocate_request(db, req_a, actor_user_id=1)
    db.commit()
    print(f"  {res['message']}")
except AllocationError as e:
    db.rollback()
    print(f"  REJECTED: {e}")
print(f"  Inventory: {state(db)}\n")

print("--- Allocating B (50) ---")
try:
    res = allocate_request(db, req_b, actor_user_id=1)
    db.commit()
    print(f"  {res['message']}")
except AllocationError as e:
    db.rollback()
    print(f"  REJECTED: {e}")
print(f"  Inventory: {state(db)}\n")

s = state(db)
total = db.execute(text("""
    SELECT COALESCE(SUM(qty_allocated), 0) FROM allocation a
    JOIN emergency_request r ON r.request_id = a.request_id
    WHERE r.medicine_id = :m AND a.allocation_status = 'RESERVED'
"""), {"m": MED}).scalar_one()

print("=" * 55)
print(f"Total allocated across both requests: {total}")
print(f"Physical stock:                       {s['qty_on_hand']}")
print(f"Reserved:                             {s['qty_reserved']}")
print(f"CORRECTNESS: {'PASS' if total <= s['qty_on_hand'] else 'FAIL — OVER-ALLOCATED'}")
print("=" * 55)
db.close()
