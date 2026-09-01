#!/usr/bin/env bash
# One-command setup for a fresh clone.
set -e

PGURL="postgresql://medsupply:medsupply_dev_pw@localhost:5432/medsupply"

echo "==> Starting databases"
docker compose up -d
echo "    waiting for health checks…"
until docker compose ps postgres | grep -q healthy; do sleep 2; done
until docker compose ps mongo | grep -q healthy; do sleep 2; done

echo "==> Applying schema"
cd backend
for f in sql/01_schema.sql sql/02_demo_tables.sql sql/03_views.sql \
         sql/05_indexes.sql sql/07_analytics_views.sql; do
    echo "    $f"
    psql "$PGURL" -q -f "$f"
done

echo "==> Seeding PostgreSQL (this takes 1-3 minutes)"
python scripts/seed_data.py --mode bulk

echo "==> Setting dev passwords"
python scripts/set_passwords.py

echo "==> Seeding MongoDB"
python scripts/seed_incidents.py

echo "==> Verifying"
psql "$PGURL" -q -c "SELECT 'batches: ' || COUNT(*) FROM inventory_batch;"
psql "$PGURL" -q -c "SELECT 'requests: ' || COUNT(*) FROM emergency_request;"

cd ..
echo ""
echo "Setup complete."
echo "  Backend:  cd backend && python -m uvicorn app.main:app --reload --port 8000"
echo "  Frontend: cd frontend && npm install && npm run dev"
echo "  Login:    admin / admin@12345"
