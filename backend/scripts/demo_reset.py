"""Put the system into a state where Auto Stock-Up visibly runs.

Knocks selected warehouse stock below threshold so the next scheduled
scan raises orders the audience can watch move through the pipeline.
Clears nothing historical -- it only reduces stock.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import SessionLocal

db = SessionLocal()
try:
    n = db.execute(text("""
        -- Never cut below qty_reserved: CHECK (qty_reserved <= qty_on_hand)
        -- rejects it, and rightly so -- that stock is already promised.
        UPDATE inventory_batch
        SET qty_on_hand = GREATEST(qty_on_hand / 5, qty_reserved)
        WHERE batch_id IN (
            SELECT batch_id FROM inventory_batch
            WHERE warehouse_id BETWEEN :lo AND :hi
            ORDER BY batch_id LIMIT 4000)
    """), {"lo": 6, "hi": 14}).rowcount
    db.commit()

    due = db.execute(text("""
        WITH holding AS (
            SELECT warehouse_id, medicine_id,
                   SUM(qty_on_hand - qty_reserved) AS available
            FROM inventory_batch WHERE expiry_date > CURRENT_DATE
            GROUP BY warehouse_id, medicine_id
        ),
        oo AS (
            SELECT warehouse_id, medicine_id,
                   SUM(qty_ordered - qty_received) AS on_order
            FROM purchase_order_line
            WHERE line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')
            GROUP BY warehouse_id, medicine_id
        )
        SELECT COUNT(*) FROM stock_policy p
        LEFT JOIN holding h ON h.warehouse_id=p.warehouse_id AND h.medicine_id=p.medicine_id
        LEFT JOIN oo o      ON o.warehouse_id=p.warehouse_id AND o.medicine_id=p.medicine_id
        WHERE COALESCE(h.available,0) + COALESCE(o.on_order,0) <= p.min_threshold
    """)).scalar_one()

    print(f"Reduced {n} batches. {due} policies now below threshold.")
    print("The next scheduled scan will raise orders for them.")
finally:
    db.close()
