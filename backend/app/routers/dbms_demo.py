from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.deps import require_roles
from app.db.postgres import get_db
from app.dbms import indexing, optimization

router = APIRouter(prefix="/dbms", tags=["DBMS Demonstrations"])

DEMO_ROLES = require_roles("ADMIN", "EMERGENCY_COORDINATOR")


def _guard():
    if not settings.enable_dbms_demos:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "DBMS demonstrations are disabled")


@router.get("/benchmarks", dependencies=[Depends(DEMO_ROLES)])
def list_benchmarks():
    _guard()
    return [{"key": k, "label": v["label"], "index": v["index"],
             "endpoint": v["endpoint"], "sql": v["sql"]}
            for k, v in indexing.BENCHMARKS.items()]


@router.get("/benchmarks/{key}", dependencies=[Depends(DEMO_ROLES)])
def run_benchmark(key: str, db: Session = Depends(get_db)):
    """Run one benchmark with and without index access. Live measurement."""
    _guard()
    try:
        return indexing.compare_with_without_index(db, key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))


@router.get("/indexes", dependencies=[Depends(DEMO_ROLES)])
def indexes(db: Session = Depends(get_db)):
    _guard()
    return indexing.list_indexes(db)


@router.get("/table-stats", dependencies=[Depends(DEMO_ROLES)])
def stats(db: Session = Depends(get_db)):
    _guard()
    return indexing.table_stats(db)


@router.get("/optimization", dependencies=[Depends(DEMO_ROLES)])
def list_optimization_demos():
    _guard()
    return optimization.list_demos()


@router.get("/optimization/{key}", dependencies=[Depends(DEMO_ROLES)])
def run_optimization_demo(key: str, db: Session = Depends(get_db)):
    _guard()
    try:
        return optimization.run_demo(db, key)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
