from sqlalchemy import func, select
from sqlalchemy.orm import Session


def paginate(db: Session, stmt, limit: int, offset: int):
    """Return (rows, total). Runs a COUNT over the same filters.

    The COUNT is a second query by design: window-function counts
    (COUNT(*) OVER ()) force the planner to materialise every matching
    row even when only 50 are returned.
    """
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()
    rows = db.execute(stmt.limit(limit).offset(offset)).scalars().all()
    return rows, total
