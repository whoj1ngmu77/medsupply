"""Automatic inventory replenishment (Auto Stock-Up).

Supply side of the pipeline: warehouse stock falls below its policy
threshold -> a purchase order is raised against a supplier.

This is the INVERSE of allocation_service, which moves stock from a
warehouse out to a hospital. The two never touch the same rows in the
same transaction and allocation is not modified by this module.

CONCURRENCY
    Each policy is evaluated inside its own SAVEPOINT, holding
    SELECT ... FOR UPDATE on the stock_policy row. Two concurrent scans
    therefore serialize per policy.

    The database is the real backstop: uq_open_po_line is a partial
    unique index permitting at most one open order line per
    (warehouse, medicine). If two scans somehow both reach INSERT, the
    second raises IntegrityError and is recorded as SKIPPED_ORDER_OPEN.
    An application-level "is there an open order?" check alone would be
    a time-of-check/time-of-use race.

SIMULATION
    No real supplier is ever contacted. Every order carries
    is_simulated=TRUE and dispatch_channel='SIMULATED'.
"""
import logging
import math
import uuid
from datetime import date, timedelta

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

logger = logging.getLogger("medsupply.replenishment")

OPEN_STATUSES = ("PENDING", "SENT", "CONFIRMED", "SHIPPED")


# ---------------------------------------------------------------------
# Reading the current position
# ---------------------------------------------------------------------

DUE_SQL = """
WITH holding AS (
    SELECT warehouse_id, medicine_id,
           SUM(qty_on_hand - qty_reserved) AS available
    FROM inventory_batch
    WHERE expiry_date > CURRENT_DATE
    GROUP BY warehouse_id, medicine_id
),
on_order AS (
    SELECT l.warehouse_id, l.medicine_id,
           SUM(l.qty_ordered - l.qty_received) AS qty_on_order
    FROM purchase_order_line l
    WHERE l.line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')
    GROUP BY l.warehouse_id, l.medicine_id
)
SELECT p.policy_id, p.warehouse_id, w.name AS warehouse_name,
       p.medicine_id, m.name AS medicine_name, m.criticality,
       p.min_threshold, p.target_level, p.preferred_supplier_id,
       p.auto_order_enabled, w.auto_replenish_enabled,
       COALESCE(h.available, 0)     AS available,
       COALESCE(o.qty_on_order, 0)  AS qty_on_order
FROM stock_policy p
JOIN warehouse w ON w.warehouse_id = p.warehouse_id
JOIN medicine  m ON m.medicine_id  = p.medicine_id
LEFT JOIN holding  h ON h.warehouse_id = p.warehouse_id
                    AND h.medicine_id  = p.medicine_id
LEFT JOIN on_order o ON o.warehouse_id = p.warehouse_id
                    AND o.medicine_id  = p.medicine_id
WHERE COALESCE(h.available, 0) + COALESCE(o.qty_on_order, 0) <= p.min_threshold
ORDER BY
    CASE m.criticality WHEN 'LIFE_SAVING' THEN 1
                       WHEN 'ESSENTIAL'   THEN 2 ELSE 3 END,
    (p.min_threshold - COALESCE(h.available, 0)) DESC
LIMIT :lim
"""


def due_policies(db: Session, limit: int = 100) -> list[dict]:
    """Policies whose stock PLUS stock already on order is at or below
    the threshold.

    Including qty_on_order is what makes repeated scans idempotent: once
    an order exists, it counts toward coverage, so the policy stops
    being due until that order is delivered or cancelled.
    """
    return [dict(r) for r in
            db.execute(text(DUE_SQL), {"lim": limit}).mappings().all()]


def compute_order_qty(target_level: int, available: int, on_order: int,
                      min_order_qty: int, pack_size: int) -> int:
    """Restock to the target, honouring supplier pack size and MOQ.

    Requirement 4: quantity derives from current stock, the threshold
    and the desired restocking level -- not a fixed reorder amount.
    """
    shortfall = target_level - available - on_order
    if shortfall <= 0:
        return 0
    qty = max(shortfall, min_order_qty)
    return int(math.ceil(qty / pack_size) * pack_size)


def _pick_supplier(db: Session, medicine_id: int,
                   preferred_id: int | None) -> dict | None:
    """Preferred supplier if it still stocks the medicine, else the
    best-rated active alternative. Requirement 3."""
    if preferred_id:
        row = db.execute(text("""
            SELECT sm.supplier_id, s.name AS supplier_name, sm.unit_price,
                   sm.lead_time_days, sm.min_order_qty, sm.pack_size
            FROM supplier_medicine sm
            JOIN supplier s ON s.supplier_id = sm.supplier_id
            WHERE sm.medicine_id = :m AND sm.supplier_id = :s AND sm.is_active
        """), {"m": medicine_id, "s": preferred_id}).mappings().first()
        if row:
            return dict(row)

    row = db.execute(text("""
        SELECT sm.supplier_id, s.name AS supplier_name, sm.unit_price,
               sm.lead_time_days, sm.min_order_qty, sm.pack_size
        FROM supplier_medicine sm
        JOIN supplier s ON s.supplier_id = sm.supplier_id
        WHERE sm.medicine_id = :m AND sm.is_active
        ORDER BY s.rating DESC NULLS LAST, sm.unit_price ASC
        LIMIT 1
    """), {"m": medicine_id}).mappings().first()
    return dict(row) if row else None


def _log(db: Session, scan_id: str, p: dict, decision: str,
         qty: int | None = None, po_id: int | None = None,
         note: str | None = None) -> None:
    db.execute(text("""
        INSERT INTO replenishment_log
            (scan_id, policy_id, warehouse_id, medicine_id, decision,
             qty_available, qty_on_order, min_threshold, target_level,
             qty_ordered, po_id, note)
        VALUES (:sid, :pid, :w, :m, :d, :av, :oo, :mt, :tl, :q, :po, :n)
    """), {"sid": scan_id, "pid": p.get("policy_id"),
           "w": p.get("warehouse_id"), "m": p.get("medicine_id"),
           "d": decision, "av": p.get("available"),
           "oo": p.get("qty_on_order"), "mt": p.get("min_threshold"),
           "tl": p.get("target_level"), "q": qty, "po": po_id, "n": note})


def _notify(db: Session, po_id: int, p: dict, qty: int,
            supplier_name: str) -> None:
    """Requirement 7 -- notify the inventory manager."""
    severity = "CRITICAL" if p["criticality"] == "LIFE_SAVING" else "WARNING"
    db.execute(text("""
        INSERT INTO notification
            (recipient_role, category, severity, title, body, po_id)
        VALUES ('ADMIN', 'REPLENISHMENT', :sev, :title, :body, :po)
    """), {"sev": severity,
           "title": f"Auto stock-up: {p['medicine_name']} at {p['warehouse_name']}",
           "body": (f"Stock {p['available']} fell to or below threshold "
                    f"{p['min_threshold']}. Ordered {qty} units from "
                    f"{supplier_name} to reach target {p['target_level']}. "
                    f"Simulated order — no supplier was contacted."),
           "po": po_id})


# ---------------------------------------------------------------------
# The scan
# ---------------------------------------------------------------------

def run_scan(db: Session, actor_user_id: int | None = None,
             limit: int = 100, dry_run: bool = False,
             triggered_by: str = "AUTO") -> dict:
    """Evaluate every due policy and raise orders. Caller commits."""
    scan_id = str(uuid.uuid4())
    candidates = due_policies(db, limit)

    if dry_run:
        preview = []
        for p in candidates:
            sup = _pick_supplier(db, p["medicine_id"], p["preferred_supplier_id"])
            qty = compute_order_qty(p["target_level"], p["available"],
                                    p["qty_on_order"],
                                    sup["min_order_qty"] if sup else 100,
                                    sup["pack_size"] if sup else 50) if sup else 0
            preview.append({
                "warehouse": p["warehouse_name"], "medicine": p["medicine_name"],
                "criticality": p["criticality"], "available": p["available"],
                "min_threshold": p["min_threshold"],
                "target_level": p["target_level"],
                "would_order": qty,
                "supplier": sup["supplier_name"] if sup else None,
                "blocked": None if sup else "no active supplier",
            })
        return {"scan_id": scan_id, "dry_run": True,
                "policies_due": len(candidates), "would_create": preview,
                "message": f"{len(candidates)} policy/policies below threshold"}

    created, skipped, failed = [], [], []

    for p in candidates:
        try:
            with db.begin_nested():          # SAVEPOINT per policy
                # Serialize concurrent scans on this policy.
                locked = db.execute(text("""
                    SELECT policy_id, min_threshold, target_level,
                           preferred_supplier_id, auto_order_enabled
                    FROM stock_policy
                    WHERE policy_id = :pid
                    FOR UPDATE
                """), {"pid": p["policy_id"]}).mappings().first()

                if not locked or not locked["auto_order_enabled"]:
                    _log(db, scan_id, p, "SKIPPED_DISABLED")
                    skipped.append({**p, "reason": "policy disabled"})
                    continue

                if not p["auto_replenish_enabled"]:
                    _log(db, scan_id, p, "SKIPPED_DISABLED",
                         note="warehouse auto-replenish off")
                    skipped.append({**p, "reason": "warehouse disabled"})
                    continue

                # Re-read inside the lock; the picture may have moved.
                fresh = db.execute(text("""
                    WITH holding AS (
                        SELECT COALESCE(SUM(qty_on_hand - qty_reserved), 0) AS available
                        FROM inventory_batch
                        WHERE warehouse_id = :w AND medicine_id = :m
                          AND expiry_date > CURRENT_DATE
                    ),
                    oo AS (
                        SELECT COALESCE(SUM(qty_ordered - qty_received), 0) AS on_order
                        FROM purchase_order_line
                        WHERE warehouse_id = :w AND medicine_id = :m
                          AND line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')
                    )
                    SELECT holding.available, oo.on_order FROM holding, oo
                """), {"w": p["warehouse_id"], "m": p["medicine_id"]}).mappings().first()

                p = {**p, "available": fresh["available"],
                     "qty_on_order": fresh["on_order"]}

                if fresh["available"] + fresh["on_order"] > locked["min_threshold"]:
                    _log(db, scan_id, p, "SKIPPED_ABOVE_THRESHOLD",
                         note="recovered before the lock was taken")
                    skipped.append({**p, "reason": "above threshold on re-read"})
                    continue

                sup = _pick_supplier(db, p["medicine_id"],
                                     locked["preferred_supplier_id"])
                if not sup:
                    _log(db, scan_id, p, "SKIPPED_NO_SUPPLIER")
                    skipped.append({**p, "reason": "no active supplier"})
                    continue

                qty = compute_order_qty(locked["target_level"],
                                        fresh["available"], fresh["on_order"],
                                        sup["min_order_qty"], sup["pack_size"])
                if qty <= 0:
                    _log(db, scan_id, p, "SKIPPED_ABOVE_THRESHOLD",
                         note="computed quantity was zero")
                    skipped.append({**p, "reason": "nothing to order"})
                    continue

                po_id, po_number = _create_order(
                    db, p, sup, qty, actor_user_id, triggered_by)

                _log(db, scan_id, p, "ORDERED", qty=qty, po_id=po_id,
                     note=f"{po_number} -> {sup['supplier_name']}")
                _notify(db, po_id, p, qty, sup["supplier_name"])

                created.append({
                    "po_id": po_id, "po_number": po_number,
                    "warehouse": p["warehouse_name"],
                    "medicine": p["medicine_name"],
                    "criticality": p["criticality"],
                    "available": fresh["available"],
                    "min_threshold": locked["min_threshold"],
                    "target_level": locked["target_level"],
                    "qty_ordered": qty,
                    "supplier": sup["supplier_name"],
                    "unit_price": float(sup["unit_price"]),
                    "is_simulated": True,
                })

        except IntegrityError as exc:
            # The partial unique index fired: another transaction opened
            # an order for this (warehouse, medicine) first. This is the
            # duplicate-prevention guarantee working, not a bug.
            #
            # No db.rollback() here. The begin_nested() context manager
            # has already rolled back to the SAVEPOINT. Calling
            # db.rollback() would abort the WHOLE session transaction and
            # discard every order raised earlier in this scan.
            if "uq_open_po_line" in str(exc.orig):
                _log(db, scan_id, p, "SKIPPED_ORDER_OPEN",
                     note="blocked by uq_open_po_line (concurrent scan)")
                skipped.append({**p, "reason": "open order exists"})
            else:
                _log(db, scan_id, p, "FAILED", note=str(exc.orig)[:300])
                failed.append({**p, "error": str(exc.orig)[:200]})
        except Exception as exc:                       # noqa: BLE001
            # Savepoint already rolled back; the rest of the scan stands.
            logger.exception("replenishment failed for policy %s",
                             p.get("policy_id"))
            _log(db, scan_id, p, "FAILED", note=str(exc)[:300])
            failed.append({**p, "error": str(exc)[:200]})

    logger.info("scan %s: %d ordered, %d skipped, %d failed",
                scan_id, len(created), len(skipped), len(failed))

    return {
        "scan_id": scan_id,
        "dry_run": False,
        "triggered_by": triggered_by,
        "policies_due": len(candidates),
        "orders_created": len(created),
        "skipped": len(skipped),
        "failed": len(failed),
        "created": created,
        "skipped_detail": [
            {"warehouse": s["warehouse_name"], "medicine": s["medicine_name"],
             "reason": s["reason"]} for s in skipped],
        "message": (f"Raised {len(created)} simulated purchase order(s) "
                    f"from {len(candidates)} policy/policies below threshold"),
    }


def _create_order(db: Session, p: dict, sup: dict, qty: int,
                  actor_user_id: int | None, triggered_by: str):
    """One PO with one line. Returns (po_id, po_number)."""
    po_number = db.execute(text("""
        SELECT 'PO-' || TO_CHAR(NOW(), 'YYYYMMDD') || '-' ||
               LPAD(NEXTVAL('po_number_seq')::text, 6, '0')
    """)).scalar_one()

    expected = date.today() + timedelta(days=int(sup["lead_time_days"]))
    total = round(float(sup["unit_price"]) * qty, 2)

    po_id = db.execute(text("""
        INSERT INTO purchase_order
            (po_number, supplier_id, warehouse_id, po_status, total_value,
             is_simulated, dispatch_channel, triggered_by, raised_by, expected_by)
        VALUES (:num, :s, :w, 'PENDING', :tv, TRUE, 'SIMULATED', :tb, :u, :exp)
        RETURNING po_id
    """), {"num": po_number, "s": sup["supplier_id"], "w": p["warehouse_id"],
           "tv": total, "tb": triggered_by, "u": actor_user_id,
           "exp": expected}).scalar_one()

    # This INSERT is the one guarded by uq_open_po_line.
    db.execute(text("""
        INSERT INTO purchase_order_line
            (po_id, warehouse_id, medicine_id, qty_ordered, unit_price,
             line_status)
        VALUES (:po, :w, :m, :q, :p, 'PENDING')
    """), {"po": po_id, "w": p["warehouse_id"], "m": p["medicine_id"],
           "q": qty, "p": sup["unit_price"]})

    return po_id, po_number
