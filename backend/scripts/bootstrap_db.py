"""Build the full schema on a fresh database, in dependency order.

Deployment use: point DATABASE_URL at the managed database and run once.
Safe to re-run -- every file uses IF NOT EXISTS or DROP/CREATE.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text
from app.db.postgres import engine

SQL_DIR = Path(__file__).resolve().parents[1] / "sql"
ORDER = [
    "01_schema.sql", "02_demo_tables.sql", "03_views.sql",
    "05_indexes.sql", "07_analytics_views.sql", "10_replenishment.sql",
]

for name in ORDER:
    path = SQL_DIR / name
    if not path.exists():
        print(f"  skip {name} (not found)")
        continue
    print(f"  running {name} ...", end=" ", flush=True)
    try:
        with engine.begin() as conn:
            conn.execute(text(path.read_text()))
        print("ok")
    except Exception as exc:
        print(f"FAILED\n    {str(exc)[:300]}")

with engine.connect() as conn:
    n = conn.execute(text("""
        SELECT COUNT(*) FROM information_schema.tables
        WHERE table_schema='public'
    """)).scalar_one()
print(f"\n{n} tables present")
