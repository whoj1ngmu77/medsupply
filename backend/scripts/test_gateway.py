"""Walk simulated orders through their lifecycle and verify stock lands."""
import time, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import SessionLocal
from app.services import supplier_gateway as gw

db = SessionLocal()
try:
    def snap():
        return dict(db.execute(text("""
            SELECT (SELECT COUNT(*) FROM purchase_order WHERE po_status='PENDING')   AS pending,
                   (SELECT COUNT(*) FROM purchase_order WHERE po_status='SENT')      AS sent,
                   (SELECT COUNT(*) FROM purchase_order WHERE po_status='CONFIRMED') AS confirmed,
                   (SELECT COUNT(*) FROM purchase_order WHERE po_status='SHIPPED')   AS shipped,
                   (SELECT COUNT(*) FROM purchase_order WHERE po_status='DELIVERED') AS delivered,
                   (SELECT COUNT(*) FROM inventory_batch WHERE source_po_line_id IS NOT NULL) AS po_batches
        """)).mappings().first())

    print("start:", snap())
    for i in range(12):
        time.sleep(6)
        r = gw.advance_due_orders(db, limit=200)
        db.commit()
        print(f"tick {i+1}: advanced={r['advanced']:<4} delivered={r['delivered']:<4} {snap()}")

    print("\nStock created by delivered orders:")
    for row in db.execute(text("""
        SELECT b.batch_number, w.name AS warehouse, m.name AS medicine,
               b.qty_on_hand, b.expiry_date
        FROM inventory_batch b
        JOIN warehouse w ON w.warehouse_id=b.warehouse_id
        JOIN medicine  m ON m.medicine_id =b.medicine_id
        WHERE b.source_po_line_id IS NOT NULL
        ORDER BY b.batch_id DESC LIMIT 5
    """)).mappings():
        print(f"  {row['batch_number']:<26} {row['warehouse'][:26]:<28} "
              f"{row['medicine']:<14} {row['qty_on_hand']:>8}")
finally:
    db.close()
