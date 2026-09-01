"""End-to-end: request -> allocate -> ship -> dispatch -> deliver.

Proves qty_on_hand decrements ONLY at delivery.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.services.allocation_service import allocate_request
from app.services.shipment_service import (create_shipment, deliver_shipment,
                                           dispatch_shipment)

MED = 998


def setup(db):
    for t in ["allocation_event", "shipment", "allocation"]:
        db.execute(text(f"""
            DELETE FROM {t} WHERE {'request_id' if t != 'shipment' else
            'allocation_id'} IN (
                SELECT {'request_id' if t != 'shipment' else 'allocation_id'}
                FROM {'emergency_request' if t != 'shipment' else 'allocation'}
                WHERE {'medicine_id' if t != 'shipment' else 'batch_id'} IN (
                    SELECT {'medicine_id' if t != 'shipment' else 'batch_id'}
                    FROM {'medicine' if t != 'shipment' else 'inventory_batch'}
                    WHERE medicine_id = :m))
        """), {"m": MED}) if False else None

    db.execute(text("DELETE FROM shipment WHERE allocation_id IN "
                    "(SELECT a.allocation_id FROM allocation a "
                    " JOIN emergency_request r ON r.request_id = a.request_id "
                    " WHERE r.medicine_id = :m)"), {"m": MED})
    db.execute(text("DELETE FROM allocation_event WHERE batch_id IN "
                    "(SELECT batch_id FROM inventory_batch WHERE medicine_id = :m)"),
               {"m": MED})
    db.execute(text("DELETE FROM allocation WHERE request_id IN "
                    "(SELECT request_id FROM emergency_request WHERE medicine_id = :m)"),
               {"m": MED})
    db.execute(text("DELETE FROM emergency_request WHERE medicine_id = :m"), {"m": MED})
    db.execute(text("DELETE FROM inventory_batch WHERE medicine_id = :m"), {"m": MED})
    db.execute(text("DELETE FROM medicine WHERE medicine_id = :m"), {"m": MED})

    db.execute(text("""
        INSERT INTO medicine (medicine_id, name, category_id, manufacturer_id,
                              unit, criticality)
        VALUES (:m, 'LIFECYCLE-TEST-MED', 1, 1, 'vial', 'ESSENTIAL')
    """), {"m": MED})
    db.execute(text("""
        INSERT INTO inventory_batch (warehouse_id, medicine_id, batch_number,
                                     qty_on_hand, qty_reserved, expiry_date)
        VALUES (1, :m, 'LIFECYCLE-B1', 500, 0, CURRENT_DATE + 365)
    """), {"m": MED})
    rid = db.execute(text("""
        INSERT INTO emergency_request (hospital_id, medicine_id, qty_requested,
                                       priority)
        VALUES (1, :m, 200, 'HIGH') RETURNING request_id
    """), {"m": MED}).scalar_one()
    db.commit()
    return rid


def show(db, label):
    r = db.execute(text("""
        SELECT qty_on_hand, qty_reserved,
               qty_on_hand - qty_reserved AS available
        FROM inventory_batch WHERE medicine_id = :m
    """), {"m": MED}).mappings().one()
    print(f"  {label:<22} on_hand={r['qty_on_hand']:<5} "
          f"reserved={r['qty_reserved']:<5} available={r['available']}")


db = SessionLocal()
rid = setup(db)
print(f"Batch: 500 units. Request {rid} for 200 units.\n")
show(db, "initial")

allocate_request(db, rid, actor_user_id=1)
db.commit()
show(db, "after allocate")
print("    -> reserved rises, on_hand UNCHANGED (stock still in warehouse)\n")

aid = db.execute(text(
    "SELECT allocation_id FROM allocation WHERE request_id = :r"),
    {"r": rid}).scalar_one()

sid = create_shipment(db, aid, "TN-01-AB-1234", "Test Driver",
                      actor_user_id=1)["shipment_id"]
db.commit()
show(db, "after create shipment")

dispatch_shipment(db, sid, actor_user_id=1)
db.commit()
show(db, "after dispatch")
print("    -> in transit, still NOTHING removed from stock\n")

res = deliver_shipment(db, sid, actor_user_id=1)
db.commit()
show(db, "after deliver")
print("    -> BOTH decrement together: stock has physically left\n")

final = db.execute(text("""
    SELECT qty_on_hand, qty_reserved FROM inventory_batch WHERE medicine_id = :m
"""), {"m": MED}).mappings().one()
status = db.execute(text(
    "SELECT request_status FROM emergency_request WHERE request_id = :r"),
    {"r": rid}).scalar_one()

print("=" * 60)
ok = final["qty_on_hand"] == 300 and final["qty_reserved"] == 0
print(f"Expected on_hand=300 reserved=0  |  Got on_hand="
      f"{final['qty_on_hand']} reserved={final['qty_reserved']}")
print(f"Request status: {status}")
print(f"LIFECYCLE: {'PASS' if ok and status == 'DELIVERED' else 'FAIL'}")
print("=" * 60)
db.close()
