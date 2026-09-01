from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.core import Supplier
from app.repositories.common import paginate
from app.schemas.core import SupplierCreate, SupplierOut, SupplierUpdate

router = APIRouter(prefix="/suppliers", tags=["Suppliers"])

ADMIN_ONLY = require_roles("ADMIN")


@router.get("", dependencies=[Depends(get_current_user)])
def list_suppliers(
    db: Session = Depends(get_db),
    min_rating: float | None = Query(default=None, ge=0, le=5),
    q: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Supplier)
    if min_rating is not None:
        stmt = stmt.where(Supplier.rating >= min_rating)
    if q:
        stmt = stmt.where(Supplier.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Supplier.supplier_id)

    rows, total = paginate(db, stmt, limit, offset)
    return {
        "items": [SupplierOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/{supplier_id}", response_model=SupplierOut,
            dependencies=[Depends(get_current_user)])
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    return row


@router.post("", response_model=SupplierOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(ADMIN_ONLY)])
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    row = Supplier(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{supplier_id}", response_model=SupplierOut,
              dependencies=[Depends(ADMIN_ONLY)])
def update_supplier(supplier_id: int, payload: SupplierUpdate,
                    db: Session = Depends(get_db)):
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{supplier_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(ADMIN_ONLY)])
def delete_supplier(supplier_id: int, db: Session = Depends(get_db)):
    row = db.get(Supplier, supplier_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Supplier not found")
    db.delete(row)
    db.commit()
