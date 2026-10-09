"""Simulated supplier gateway.

NOTHING HERE CONTACTS A REAL SUPPLIER. No email is sent, no API is
called. Every order carries is_simulated=TRUE and the UI labels it.
This module models what a real integration would do so the workflow is
demonstrable end to end.

A real implementation would replace _transmit() with an SMTP send or an
EDI/REST call to the supplier, and would advance statuses from supplier
callbacks rather than from elapsed time.

LIFECYCLE                     advances after (simulated)
    PENDING   -> SENT              5 s
    SENT      -> CONFIRMED        10 s
    CONFIRMED -> SHIPPED          15 s
    SHIPPED   -> DELIVERED        20 s

DELIVERY IS THE TRANSACTIONAL PART. Receiving goods must do three things
atomically or none of them:
    1. create the inventory_batch row,
    2. set qty_received on the line,
    3. move the line and order to DELIVERED.
A crash between 1 and 3 would otherwise create stock that no order
accounts for, or an order marked delivered with no stock behind it.
"""
import logging
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("medsupply.gateway")

# from_status -> (to_status, dwell_seconds, entered_col, stamp_col)
#   entered_col: when the order ENTERED its current status. Dwell is
#                measured from this. Using the next status's column
#                instead reads NULL and makes every stage look overdue.
#   stamp_col:   the column written when the new status is reached.
TRANSITIONS = {
    "PENDING":   ("SENT",      5,  "created_at",   "sent_at"),
    "SENT":      ("CONFIRMED", 10, "sent_at",      "confirmed_at"),
    "CONFIRMED": ("SHIPPED",   15, "confirmed_at", "shipped_at"),
    "SHIPPED":   ("DELIVERED", 20, "shipped_at",   "delivered_at"),
}


def _transmit(po_number: str, supplier_name: str) -> dict:
    """Stand-in for a real send. Returns a simulated acknowledgement."""
    logger.info("SIMULATED transmit %s -> %s", po_number, supplier_name)
    return {"channel": "SIMULATED", "accepted": True,
            "note": f"Simulated transmission of {po_number} to {supplier_name}. "
                    f"No real supplier was contacted."}


def advance_due_orders(db: Session, limit: int = 50) -> dict:
    """Advance every order whose dwell time in its current status has
    elapsed. Caller commits."""
    moved, delivered = [], []

    for from_status, (to_status, dwell, entered, stamp) in TRANSITIONS.items():
        rows = db.execute(text(f"""
            SELECT o.po_id, o.po_number, o.supplier_id, o.warehouse_id,
                   s.name AS supplier_name
            FROM purchase_order o
            JOIN supplier s ON s.supplier_id = o.supplier_id
            WHERE o.po_status = :from_status
              AND COALESCE(o.{entered}, o.created_at)
                  < NOW() - make_interval(secs => :dwell)
            ORDER BY o.po_id
            LIMIT :lim
            FOR UPDATE OF o SKIP LOCKED
        """), {"from_status": from_status, "dwell": dwell,
               "lim": limit}).mappings().all()

        for r in rows:
            try:
                with db.begin_nested():
                    if to_status == "DELIVERED":
                        received = _receive_order(db, r["po_id"],
                                                  r["warehouse_id"])
                        delivered.append({"po_number": r["po_number"],
                                          "units_received": received})
                    else:
                        if to_status == "SENT":
                            _transmit(r["po_number"], r["supplier_name"])

                        db.execute(text(f"""
                            UPDATE purchase_order
                            SET po_status = :st, {stamp} = NOW()
                            WHERE po_id = :po
                        """), {"st": to_status, "po": r["po_id"]})
                        db.execute(text("""
                            UPDATE purchase_order_line SET line_status = :st
                            WHERE po_id = :po
                        """), {"st": to_status, "po": r["po_id"]})

                    moved.append({"po_number": r["po_number"],
                                  "from": from_status, "to": to_status})
            except Exception:                              # noqa: BLE001
                logger.exception("could not advance %s", r["po_number"])

    return {"advanced": len(moved), "delivered": len(delivered),
            "transitions": moved, "deliveries": delivered,
            "simulated": True}


def _receive_order(db: Session, po_id: int, warehouse_id: int) -> int:
    """Receive goods: create stock, close the line, close the order.

    All inside the caller's SAVEPOINT -- atomic by construction.
    """
    lines = db.execute(text("""
        SELECT l.po_line_id, l.medicine_id, l.qty_ordered, l.qty_received
        FROM purchase_order_line l
        WHERE l.po_id = :po AND l.line_status = 'SHIPPED'
        FOR UPDATE
    """), {"po": po_id}).mappings().all()

    total = 0
    for ln in lines:
        qty = ln["qty_ordered"] - ln["qty_received"]
        if qty <= 0:
            continue

        batch_number = db.execute(text("""
            SELECT 'PO' || :po || '-' || :line || '-' ||
                   TO_CHAR(NOW(), 'YYYYMMDD')
        """), {"po": po_id, "line": ln["po_line_id"]}).scalar_one()

        db.execute(text("""
            INSERT INTO inventory_batch
                (warehouse_id, medicine_id, batch_number, qty_on_hand,
                 qty_reserved, expiry_date, source_po_line_id)
            VALUES (:w, :m, :bn, :q, 0, :exp, :line)
        """), {"w": warehouse_id, "m": ln["medicine_id"], "bn": batch_number,
               "q": qty, "exp": date.today() + timedelta(days=540),
               "line": ln["po_line_id"]})

        db.execute(text("""
            UPDATE purchase_order_line
            SET qty_received = qty_ordered, line_status = 'DELIVERED'
            WHERE po_line_id = :line
        """), {"line": ln["po_line_id"]})

        total += qty

    db.execute(text("""
        UPDATE purchase_order SET po_status = 'DELIVERED', delivered_at = NOW()
        WHERE po_id = :po
    """), {"po": po_id})

    db.execute(text("""
        INSERT INTO notification
            (recipient_role, category, severity, title, body, po_id)
        SELECT 'ADMIN', 'REPLENISHMENT', 'INFO',
               'Delivered: ' || o.po_number,
               'Received ' || :total || ' units into ' || w.name ||
               '. Simulated delivery.', o.po_id
        FROM purchase_order o
        JOIN warehouse w ON w.warehouse_id = o.warehouse_id
        WHERE o.po_id = :po
    """), {"po": po_id, "total": total})

    return total
