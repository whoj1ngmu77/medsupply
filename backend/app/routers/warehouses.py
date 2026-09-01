from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.core import Warehouse
from app.repositories.common import paginate
from app.schemas.core import WarehouseCreate, WarehouseOut, WarehouseUpdate

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])

ADMIN_ONLY = require_roles("ADMIN")
WH_STAFF = require_roles("ADMIN", "WAREHOUSE_STAFF")


@router.get("", dependencies=[Depends(get_current_user)])
def list_warehouses(
    db: Session = Depends(get_db),
    city: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Warehouse)
    if city:
        stmt = stmt.where(Warehouse.city == city)
    stmt = stmt.order_by(Warehouse.warehouse_id)

    rows, total = paginate(db, stmt, limit, offset)
    return {
        "items": [WarehouseOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/utilisation", dependencies=[Depends(get_current_user)])
def utilisation(db: Session = Depends(get_db)):
    """Reads the v_warehouse_utilisation view built in Phase 3."""
    rows = db.execute(text(
        "SELECT warehouse_id, warehouse_name, city, storage_capacity, "
        "units_stored, utilisation_pct, batch_count "
        "FROM v_warehouse_utilisation ORDER BY utilisation_pct DESC"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{warehouse_id}", response_model=WarehouseOut,
            dependencies=[Depends(get_current_user)])
def get_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    row = db.get(Warehouse, warehouse_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Warehouse not found")
    return row


@router.post("", response_model=WarehouseOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(ADMIN_ONLY)])
def create_warehouse(payload: WarehouseCreate, db: Session = Depends(get_db)):
    row = Warehouse(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{warehouse_id}", response_model=WarehouseOut,
              dependencies=[Depends(WH_STAFF)])
def update_warehouse(warehouse_id: int, payload: WarehouseUpdate,
                     db: Session = Depends(get_db)):
    row = db.get(Warehouse, warehouse_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Warehouse not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(ADMIN_ONLY)])
def delete_warehouse(warehouse_id: int, db: Session = Depends(get_db)):
    row = db.get(Warehouse, warehouse_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Warehouse not found")
    db.delete(row)
    db.commit()
