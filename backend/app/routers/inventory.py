from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.core import InventoryBatch
from app.repositories.common import paginate
from app.schemas.core import (InventoryBatchCreate, InventoryBatchOut,
                              InventoryBatchUpdate)

router = APIRouter(prefix="/inventory", tags=["Inventory"])

WH_STAFF = require_roles("ADMIN", "WAREHOUSE_STAFF")
ADMIN_ONLY = require_roles("ADMIN")


@router.get("", dependencies=[Depends(get_current_user)])
def list_batches(
    db: Session = Depends(get_db),
    warehouse_id: int | None = None,
    medicine_id: int | None = None,
    expiring_before: date | None = None,
    min_available: int | None = Query(default=None, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    """Filter combinations here are the Phase 8 index candidates:
    (warehouse_id, medicine_id), expiry_date, and the derived
    (qty_on_hand - qty_reserved) predicate.
    """
    stmt = select(InventoryBatch)
    if warehouse_id:
        stmt = stmt.where(InventoryBatch.warehouse_id == warehouse_id)
    if medicine_id:
        stmt = stmt.where(InventoryBatch.medicine_id == medicine_id)
    if expiring_before:
        stmt = stmt.where(InventoryBatch.expiry_date < expiring_before)
    if min_available is not None:
        stmt = stmt.where(
            InventoryBatch.qty_on_hand - InventoryBatch.qty_reserved
            >= min_available)
    stmt = stmt.order_by(InventoryBatch.batch_id)

    rows, total = paginate(db, stmt, limit, offset)
    return {
        "items": [InventoryBatchOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/available", dependencies=[Depends(get_current_user)])
def available(
    db: Session = Depends(get_db),
    medicine_id: int | None = None,
    warehouse_id: int | None = None,
    limit: int = Query(default=50, ge=1, le=200),
):
    """Reads v_available_inventory. FEFO order: soonest expiry first,
    which is the order the Phase 6 allocation engine consumes batches in.
    """
    sql = ("SELECT batch_id, warehouse_id, warehouse_name, medicine_id, "
           "medicine_name, criticality, batch_number, qty_on_hand, "
           "qty_reserved, qty_available, expiry_date "
           "FROM v_available_inventory WHERE qty_available > 0")
    params = {}
    if medicine_id:
        sql += " AND medicine_id = :mid"
        params["mid"] = medicine_id
    if warehouse_id:
        sql += " AND warehouse_id = :wid"
        params["wid"] = warehouse_id
    sql += " ORDER BY expiry_date ASC LIMIT :lim"
    params["lim"] = limit

    rows = db.execute(text(sql), params).mappings().all()
    return [dict(r) for r in rows]


@router.get("/expiring", dependencies=[Depends(get_current_user)])
def expiring(db: Session = Depends(get_db),
             limit: int = Query(default=50, ge=1, le=200)):
    rows = db.execute(text(
        "SELECT batch_id, batch_number, medicine_name, warehouse_name, "
        "qty_available, expiry_date, days_to_expiry FROM v_expiring_soon "
        "ORDER BY days_to_expiry ASC LIMIT :lim"
    ), {"lim": limit}).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{batch_id}", response_model=InventoryBatchOut,
            dependencies=[Depends(get_current_user)])
def get_batch(batch_id: int, db: Session = Depends(get_db)):
    row = db.get(InventoryBatch, batch_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return row


@router.post("", response_model=InventoryBatchOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(WH_STAFF)])
def create_batch(payload: InventoryBatchCreate, db: Session = Depends(get_db)):
    if payload.mfg_date and payload.expiry_date <= payload.mfg_date:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "expiry_date must be after mfg_date")
    row = InventoryBatch(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{batch_id}", response_model=InventoryBatchOut,
              dependencies=[Depends(WH_STAFF)])
def update_batch(batch_id: int, payload: InventoryBatchUpdate,
                 db: Session = Depends(get_db)):
    row = db.get(InventoryBatch, batch_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")

    data = payload.model_dump(exclude_unset=True)
    # Guard: never let qty_on_hand drop below what is already reserved.
    if "qty_on_hand" in data and data["qty_on_hand"] < row.qty_reserved:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"qty_on_hand cannot be below reserved quantity ({row.qty_reserved})")

    for k, v in data.items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{batch_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(ADMIN_ONLY)])
def delete_batch(batch_id: int, db: Session = Depends(get_db)):
    row = db.get(InventoryBatch, batch_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    if row.qty_reserved > 0:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "Cannot delete a batch with active reservations")
    db.delete(row)
    db.commit()
