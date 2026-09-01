from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.config import settings
from app.core.deps import require_roles
from app.dbms import concurrency, deadlock, recovery

router = APIRouter(prefix="/dbms", tags=["DBMS Demonstrations"])
DEMO_ROLES = require_roles("ADMIN", "EMERGENCY_COORDINATOR")


def _guard():
    if not settings.enable_dbms_demos:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "DBMS demonstrations are disabled")


@router.post("/concurrency", dependencies=[Depends(DEMO_ROLES)])
def concurrency_demo(
    use_lock: bool = Query(default=True,
                           description="False reproduces the lost update"),
    stock: int = Query(default=100, ge=10, le=10000),
    qty_a: int = Query(default=70, ge=1),
    qty_b: int = Query(default=50, ge=1),
):
    """Two concurrent transactions reserving from the same row."""
    _guard()
    return concurrency.run_concurrency_demo(use_lock, qty_a, qty_b, stock)


@router.get("/concurrency/lock-matrix", dependencies=[Depends(DEMO_ROLES)])
def lock_matrix():
    _guard()
    return concurrency.LOCK_COMPATIBILITY


@router.get("/concurrency/locks", dependencies=[Depends(DEMO_ROLES)])
def current_locks():
    _guard()
    return concurrency.lock_monitor()


@router.post("/deadlock", dependencies=[Depends(DEMO_ROLES)])
def deadlock_demo():
    """Force a real deadlock. Runs only on demo tables."""
    _guard()
    return deadlock.run_deadlock_demo()


@router.get("/deadlock/stats", dependencies=[Depends(DEMO_ROLES)])
def deadlock_statistics():
    _guard()
    return deadlock.deadlock_stats()


@router.post("/recovery/rollback", dependencies=[Depends(DEMO_ROLES)])
def rollback():
    _guard()
    return recovery.rollback_demo()


@router.post("/recovery/savepoint", dependencies=[Depends(DEMO_ROLES)])
def savepoint():
    _guard()
    return recovery.savepoint_demo()


@router.post("/recovery/durability", dependencies=[Depends(DEMO_ROLES)])
def durability():
    _guard()
    return recovery.durability_demo()


@router.get("/recovery/log", dependencies=[Depends(DEMO_ROLES)])
def transaction_log():
    _guard()
    return recovery.transaction_log_view()
