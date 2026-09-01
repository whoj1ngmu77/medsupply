from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.deps import get_current_user, require_roles
from app.db.postgres import get_db
from app.models.core import Manufacturer, Medicine, MedicineCategory
from app.repositories.common import paginate
from app.schemas.core import MedicineCreate, MedicineOut, MedicineUpdate

router = APIRouter(prefix="/medicines", tags=["Medicines"])

ADMIN_ONLY = require_roles("ADMIN")


@router.get("", dependencies=[Depends(get_current_user)])
def list_medicines(
    db: Session = Depends(get_db),
    category_id: int | None = None,
    criticality: str | None = None,
    q: str | None = Query(default=None, description="Name search"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Medicine)
    if category_id:
        stmt = stmt.where(Medicine.category_id == category_id)
    if criticality:
        stmt = stmt.where(Medicine.criticality == criticality)
    if q:
        stmt = stmt.where(Medicine.name.ilike(f"%{q}%"))
    stmt = stmt.order_by(Medicine.medicine_id)

    rows, total = paginate(db, stmt, limit, offset)
    return {
        "items": [MedicineOut.model_validate(r) for r in rows],
        "total": total, "limit": limit, "offset": offset,
    }


@router.get("/categories", dependencies=[Depends(get_current_user)])
def list_categories(db: Session = Depends(get_db)):
    rows = db.execute(select(MedicineCategory)
                      .order_by(MedicineCategory.category_id)).scalars().all()
    return [{"category_id": r.category_id, "name": r.name,
             "description": r.description} for r in rows]


@router.get("/manufacturers", dependencies=[Depends(get_current_user)])
def list_manufacturers(db: Session = Depends(get_db)):
    rows = db.execute(select(Manufacturer)
                      .order_by(Manufacturer.manufacturer_id)).scalars().all()
    return [{"manufacturer_id": r.manufacturer_id, "name": r.name,
             "country": r.country} for r in rows]


@router.get("/shortages", dependencies=[Depends(get_current_user)])
def critical_shortages(db: Session = Depends(get_db)):
    """Reads v_critical_shortage from Phase 3."""
    rows = db.execute(text(
        "SELECT medicine_id, medicine_name, criticality, total_available, "
        "open_requests FROM v_critical_shortage ORDER BY total_available"
    )).mappings().all()
    return [dict(r) for r in rows]


@router.get("/{medicine_id}", response_model=MedicineOut,
            dependencies=[Depends(get_current_user)])
def get_medicine(medicine_id: int, db: Session = Depends(get_db)):
    row = db.get(Medicine, medicine_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medicine not found")
    return row


@router.post("", response_model=MedicineOut,
             status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(ADMIN_ONLY)])
def create_medicine(payload: MedicineCreate, db: Session = Depends(get_db)):
    row = Medicine(**payload.model_dump())
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.patch("/{medicine_id}", response_model=MedicineOut,
              dependencies=[Depends(ADMIN_ONLY)])
def update_medicine(medicine_id: int, payload: MedicineUpdate,
                    db: Session = Depends(get_db)):
    row = db.get(Medicine, medicine_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medicine not found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{medicine_id}", status_code=status.HTTP_204_NO_CONTENT,
               dependencies=[Depends(ADMIN_ONLY)])
def delete_medicine(medicine_id: int, db: Session = Depends(get_db)):
    row = db.get(Medicine, medicine_id)
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Medicine not found")
    db.delete(row)
    db.commit()
