"""Automatic inventory replenishment (Auto Stock-Up) endpoints.

The scan also runs on a background schedule (see app/services/scheduler.py).
These endpoints exist for inspection, demonstration and testing; the
feature does not depend on anyone pressing a button.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.user import UserAccount
from app.services import replenishment_service as rs
from app.services import supplier_gateway as gw

router = APIRouter(prefix="/replenishment", tags=["Auto Replenishment"])

MANAGER = require_roles("ADMIN", "EMERGENCY_COORDINATOR", "WAREHOUSE_STAFF")


@router.get("/policies", dependencies=[Depends(get_current_user)])
def list_policies(db: Session = Depends(get_db),
                  warehouse_id: int | None = None,
                  below_threshold_only: bool = False,
                  limit: int = Query(default=50, ge=1, le=200),
                  offset: int = Query(default=0, ge=0)):
    where = ["p.auto_order_enabled"]
    params = {"lim": limit, "off": offset}
    if warehouse_id:
        where.append("p.warehouse_id = :wid")
        params["wid"] = warehouse_id
    if below_threshold_only:
        where.append("COALESCE(h.available,0) <= p.min_threshold")
    clause = " AND ".join(where)

    rows = db.execute(text(f"""
        WITH holding AS (
            SELECT warehouse_id, medicine_id,
                   SUM(qty_on_hand - qty_reserved) AS available
            FROM inventory_batch WHERE expiry_date > CURRENT_DATE
            GROUP BY warehouse_id, medicine_id
        ),
        on_order AS (
            SELECT warehouse_id, medicine_id,
                   SUM(qty_ordered - qty_received) AS qty_on_order
            FROM purchase_order_line
            WHERE line_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')
            GROUP BY warehouse_id, medicine_id
        )
        SELECT p.policy_id, p.warehouse_id, w.name AS warehouse_name,
               p.medicine_id, m.name AS medicine_name, m.criticality,
               p.min_threshold, p.target_level,
               COALESCE(h.available,0)    AS available,
               COALESCE(o.qty_on_order,0) AS qty_on_order,
               s.name AS preferred_supplier,
               (COALESCE(h.available,0) <= p.min_threshold) AS below_threshold
        FROM stock_policy p
        JOIN warehouse w ON w.warehouse_id = p.warehouse_id
        JOIN medicine  m ON m.medicine_id  = p.medicine_id
        LEFT JOIN supplier s ON s.supplier_id = p.preferred_supplier_id
        LEFT JOIN holding  h ON h.warehouse_id=p.warehouse_id AND h.medicine_id=p.medicine_id
        LEFT JOIN on_order o ON o.warehouse_id=p.warehouse_id AND o.medicine_id=p.medicine_id
        WHERE {clause}
        ORDER BY (p.min_threshold - COALESCE(h.available,0)) DESC
        LIMIT :lim OFFSET :off
    """), params).mappings().all()
    return {"items": [dict(r) for r in rows], "limit": limit, "offset": offset}


@router.get("/preview", dependencies=[Depends(MANAGER)])
def preview(db: Session = Depends(get_db),
            limit: int = Query(default=25, ge=1, le=200)):
    """What the next scan would order. Read-only."""
    return rs.run_scan(db, dry_run=True, limit=limit)


@router.post("/scan", dependencies=[Depends(MANAGER)])
def scan(db: Session = Depends(get_db),
         user: UserAccount = Depends(get_current_user),
         limit: int = Query(default=50, ge=1, le=500)):
    """Force a scan now. The scheduler does this automatically too."""
    try:
        result = rs.run_scan(db, actor_user_id=user.user_id, limit=limit,
                             triggered_by="MANUAL")
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get("/orders", dependencies=[Depends(get_current_user)])
def list_orders(db: Session = Depends(get_db),
                po_status: str | None = None,
                limit: int = Query(default=50, ge=1, le=200),
                offset: int = Query(default=0, ge=0)):
    where, params = ["TRUE"], {"lim": limit, "off": offset}
    if po_status:
        where.append("o.po_status = :st")
        params["st"] = po_status.upper()
    clause = " AND ".join(where)

    total = db.execute(text(
        f"SELECT COUNT(*) FROM purchase_order o WHERE {clause}"),
        params).scalar_one()
    rows = db.execute(text(f"""
        SELECT o.po_id, o.po_number, o.po_status, o.total_value,
               o.is_simulated, o.dispatch_channel, o.triggered_by,
               o.created_at, o.sent_at, o.confirmed_at, o.shipped_at,
               o.delivered_at, o.expected_by,
               s.name AS supplier_name, w.name AS warehouse_name,
               m.name AS medicine_name, l.qty_ordered, l.qty_received
        FROM purchase_order o
        JOIN supplier  s ON s.supplier_id  = o.supplier_id
        JOIN warehouse w ON w.warehouse_id = o.warehouse_id
        LEFT JOIN purchase_order_line l ON l.po_id = o.po_id
        LEFT JOIN medicine m ON m.medicine_id = l.medicine_id
        WHERE {clause}
        ORDER BY o.po_id DESC
        LIMIT :lim OFFSET :off
    """), params).mappings().all()
    return {"items": [dict(r) for r in rows], "total": total,
            "limit": limit, "offset": offset}


@router.get("/orders/{po_id}", dependencies=[Depends(get_current_user)])
def get_order(po_id: int, db: Session = Depends(get_db)):
    po = db.execute(text("""
        SELECT o.*, s.name AS supplier_name, s.contact_email,
               w.name AS warehouse_name
        FROM purchase_order o
        JOIN supplier  s ON s.supplier_id  = o.supplier_id
        JOIN warehouse w ON w.warehouse_id = o.warehouse_id
        WHERE o.po_id = :po
    """), {"po": po_id}).mappings().first()
    if not po:
        raise HTTPException(status_code=404, detail=f"Order {po_id} not found")

    lines = db.execute(text("""
        SELECT l.*, m.name AS medicine_name, m.criticality
        FROM purchase_order_line l
        JOIN medicine m ON m.medicine_id = l.medicine_id
        WHERE l.po_id = :po
    """), {"po": po_id}).mappings().all()

    return {**dict(po), "lines": [dict(r) for r in lines]}


@router.post("/advance", dependencies=[Depends(MANAGER)])
def advance(db: Session = Depends(get_db),
            limit: int = Query(default=50, ge=1, le=200)):
    """Advance simulated orders whose dwell time has elapsed."""
    try:
        result = gw.advance_due_orders(db, limit=limit)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


@router.get("/log", dependencies=[Depends(get_current_user)])
def scan_log(db: Session = Depends(get_db),
             limit: int = Query(default=50, ge=1, le=200)):
    rows = db.execute(text("""
        SELECT l.log_id, l.scan_id, l.decision, l.qty_available,
               l.qty_on_order, l.min_threshold, l.target_level,
               l.qty_ordered, l.note, l.occurred_at,
               w.name AS warehouse_name, m.name AS medicine_name,
               o.po_number
        FROM replenishment_log l
        LEFT JOIN warehouse w ON w.warehouse_id = l.warehouse_id
        LEFT JOIN medicine  m ON m.medicine_id  = l.medicine_id
        LEFT JOIN purchase_order o ON o.po_id = l.po_id
        ORDER BY l.log_id DESC LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/notifications", dependencies=[Depends(get_current_user)])
def notifications(db: Session = Depends(get_db),
                  unread_only: bool = False,
                  limit: int = Query(default=30, ge=1, le=100)):
    clause = "WHERE NOT is_read" if unread_only else ""
    rows = db.execute(text(f"""
        SELECT notification_id, severity, title, body, po_id, is_read, created_at
        FROM notification {clause}
        ORDER BY notification_id DESC LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return {"items": [dict(r) for r in rows]}


@router.get("/stats", dependencies=[Depends(get_current_user)])
def stats(db: Session = Depends(get_db)):
    kpi = db.execute(text("""
        SELECT
          (SELECT COUNT(*) FROM stock_policy WHERE auto_order_enabled) AS active_policies,
          (SELECT COUNT(*) FROM purchase_order)                        AS total_orders,
          (SELECT COUNT(*) FROM purchase_order
             WHERE po_status IN ('PENDING','SENT','CONFIRMED','SHIPPED')) AS open_orders,
          (SELECT COUNT(*) FROM purchase_order WHERE po_status='DELIVERED') AS delivered_orders,
          (SELECT COALESCE(SUM(total_value),0) FROM purchase_order)    AS total_value,
          (SELECT COUNT(*) FROM purchase_order WHERE triggered_by='AUTO') AS auto_orders,
          (SELECT COUNT(*) FROM notification WHERE NOT is_read)        AS unread_notifications,
          (SELECT COALESCE(SUM(qty_on_hand),0) FROM inventory_batch
             WHERE source_po_line_id IS NOT NULL)                      AS units_replenished
    """)).mappings().first()

    by_status = db.execute(text("""
        SELECT po_status, COUNT(*) AS n, COALESCE(SUM(total_value),0) AS value
        FROM purchase_order GROUP BY po_status ORDER BY n DESC
    """)).mappings().all()

    decisions = db.execute(text("""
        SELECT decision, COUNT(*) AS n FROM replenishment_log
        GROUP BY decision ORDER BY n DESC
    """)).mappings().all()

    return {"kpis": dict(kpi),
            "by_status": [dict(r) for r in by_status],
            "scan_decisions": [dict(r) for r in decisions],
            "all_orders_simulated": True}
