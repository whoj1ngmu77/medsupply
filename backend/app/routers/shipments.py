from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.shipment import Shipment, SupplyConsignment
from app.models.user import UserAccount
from app.repositories.common import paginate
from app.schemas.shipment import (ConsignmentCreate, ConsignmentOut,
                                  ShipmentCreate, ShipmentOut, ShipmentUpdate)
from app.services.shipment_service import (ShipmentError, create_shipment,
                                           deliver_shipment,
                                           dispatch_shipment,
                                           receive_consignment)

router = APIRouter(tags=["Shipments & Supply"])

WH_STAFF = require_roles("ADMIN", "WAREHOUSE_STAFF", "EMERGENCY_COORDINATOR")
SUPPLY_STAFF = require_roles("ADMIN", "WAREHOUSE_STAFF", "SUPPLIER")


def _handle(exc: Exception, db: Session):
    db.rollback()
    if isinstance(exc, ShipmentError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, OperationalError):
        msg = str(exc.orig).lower() if exc.orig else ""
        if "lock timeout" in msg or "canceling statement" in msg:
            raise HTTPException(status.HTTP_423_LOCKED,
                                "Resource locked by another transaction")
    raise exc


# ---------- Shipments ----------

@router.get("/shipments", dependencies=[Depends(get_current_user)])
def list_shipments(
    db: Session = Depends(get_db),
    delivery_status: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Shipment)
    if delivery_status:
        stmt = stmt.where(Shipment.delivery_status == delivery_status)
    stmt = stmt.order_by(Shipment.shipment_id.desc())

    rows, total = paginate(db, stmt, limit, offset)
    return {"items": [ShipmentOut.model_validate(r) for r in rows],
            "total": total, "limit": limit, "offset": offset}


@router.get("/shipments/tracking", dependencies=[Depends(get_current_user)])
def tracking(db: Session = Depends(get_db),
             limit: int = Query(default=50, ge=1, le=200)):
    rows = db.execute(text("""
        SELECT s.shipment_id, s.delivery_status, s.vehicle_number,
               s.dispatched_at, s.expected_at, s.delivered_at,
               a.qty_allocated, b.batch_number, m.name AS medicine_name,
               w.name AS warehouse_name, h.name AS hospital_name,
               r.priority
        FROM shipment s
        JOIN allocation a        ON a.allocation_id = s.allocation_id
        JOIN inventory_batch b   ON b.batch_id = a.batch_id
        JOIN medicine m          ON m.medicine_id = b.medicine_id
        JOIN warehouse w         ON w.warehouse_id = b.warehouse_id
        JOIN emergency_request r ON r.request_id = a.request_id
        JOIN hospital h          ON h.hospital_id = r.hospital_id
        ORDER BY s.shipment_id DESC
        LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/shipments/{shipment_id}", response_model=ShipmentOut,
            dependencies=[Depends(get_current_user)])
def get_shipment(shipment_id: int, db: Session = Depends(get_db)):
    row = db.get(Shipment, shipment_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    return row


@router.post("/shipments", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(WH_STAFF)])
def create(payload: ShipmentCreate, db: Session = Depends(get_db),
           user: UserAccount = Depends(get_current_user)):
    try:
        result = create_shipment(
            db, payload.allocation_id, payload.vehicle_number,
            payload.driver_name, payload.expected_at, user.user_id)
        db.commit()
        return result
    except Exception as exc:
        _handle(exc, db)


@router.post("/shipments/{shipment_id}/dispatch",
             dependencies=[Depends(WH_STAFF)])
def dispatch(shipment_id: int, db: Session = Depends(get_db),
             user: UserAccount = Depends(get_current_user)):
    try:
        result = dispatch_shipment(db, shipment_id, user.user_id)
        db.commit()
        return result
    except Exception as exc:
        _handle(exc, db)


@router.post("/shipments/{shipment_id}/deliver",
             dependencies=[Depends(WH_STAFF)])
def deliver(shipment_id: int, db: Session = Depends(get_db),
            user: UserAccount = Depends(get_current_user)):
    """Confirm delivery. Decrements qty_on_hand and qty_reserved atomically."""
    try:
        result = deliver_shipment(db, shipment_id, user.user_id)
        db.commit()
        return result
    except Exception as exc:
        _handle(exc, db)


@router.patch("/shipments/{shipment_id}", response_model=ShipmentOut,
              dependencies=[Depends(WH_STAFF)])
def update_shipment(shipment_id: int, payload: ShipmentUpdate,
                    db: Session = Depends(get_db)):
    row = db.get(Shipment, shipment_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Shipment not found")
    if row.delivery_status == "DELIVERED":
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Cannot modify a delivered shipment")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


# ---------- Consignments ----------

@router.get("/consignments", dependencies=[Depends(get_current_user)])
def list_consignments(
    db: Session = Depends(get_db),
    supplier_id: int | None = None,
    warehouse_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(SupplyConsignment)
    if supplier_id:
        stmt = stmt.where(SupplyConsignment.supplier_id == supplier_id)
    if warehouse_id:
        stmt = stmt.where(SupplyConsignment.warehouse_id == warehouse_id)
    stmt = stmt.order_by(SupplyConsignment.consignment_id.desc())

    rows, total = paginate(db, stmt, limit, offset)
    return {"items": [ConsignmentOut.model_validate(r) for r in rows],
            "total": total, "limit": limit, "offset": offset}


@router.get("/consignments/history", dependencies=[Depends(get_current_user)])
def supply_history(db: Session = Depends(get_db),
                   limit: int = Query(default=50, ge=1, le=200)):
    """Supplier performance. Demonstrates aggregation over a join."""
    rows = db.execute(text("""
        SELECT s.supplier_id, s.name AS supplier_name, s.rating,
               COUNT(c.consignment_id) AS consignments,
               COALESCE(SUM(c.qty_supplied), 0) AS total_units,
               COALESCE(AVG(c.unit_price), 0)::numeric(10,2) AS avg_price,
               MAX(c.supplied_on) AS last_supply
        FROM supplier s
        LEFT JOIN supply_consignment c ON c.supplier_id = s.supplier_id
        GROUP BY s.supplier_id, s.name, s.rating
        ORDER BY total_units DESC
        LIMIT :lim
    """), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.post("/consignments", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(SUPPLY_STAFF)])
def receive(payload: ConsignmentCreate, db: Session = Depends(get_db),
            user: UserAccount = Depends(get_current_user)):
    """Receive stock: creates an inventory batch and its provenance record."""
    if payload.mfg_date and payload.expiry_date <= payload.mfg_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "expiry_date must be after mfg_date")
    if user.role == "SUPPLIER" and user.supplier_id != payload.supplier_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "You may only record consignments for your own "
                            "supplier account")
    try:
        result = receive_consignment(db, payload.model_dump(), user.user_id)
        db.commit()
        return result
    except Exception as exc:
        _handle(exc, db)
