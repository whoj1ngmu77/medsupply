import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.postgres import SessionLocal, engine
from app.main import app

TEST_MEDICINE_ID = 997


@pytest.fixture(scope="session")
def client():
    return TestClient(app)


@pytest.fixture(scope="session")
def admin_token(client):
    r = client.post("/auth/login",
                    json={"username": "admin", "password": "admin@12345"})
    assert r.status_code == 200, "Run scripts/set_passwords.py first"
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def db():
    s = SessionLocal()
    yield s
    s.close()


@pytest.fixture
def scenario(db):
    """100 units, two requests for 70 and 50. Cleaned up after."""
    _cleanup(db)
    db.execute(text("""
        INSERT INTO medicine (medicine_id, name, category_id, manufacturer_id,
                              unit, criticality)
        VALUES (:m, 'PYTEST-MED', 1, 1, 'vial', 'LIFE_SAVING')
    """), {"m": TEST_MEDICINE_ID})
    batch = db.execute(text("""
        INSERT INTO inventory_batch (warehouse_id, medicine_id, batch_number,
                                     qty_on_hand, qty_reserved, expiry_date)
        VALUES (1, :m, 'PYTEST-B1', 100, 0, CURRENT_DATE + 365)
        RETURNING batch_id
    """), {"m": TEST_MEDICINE_ID}).scalar_one()
    a = db.execute(text("""
        INSERT INTO emergency_request (hospital_id, medicine_id, qty_requested,
                                       priority)
        VALUES (1, :m, 70, 'CRITICAL') RETURNING request_id
    """), {"m": TEST_MEDICINE_ID}).scalar_one()
    b = db.execute(text("""
        INSERT INTO emergency_request (hospital_id, medicine_id, qty_requested,
                                       priority)
        VALUES (2, :m, 50, 'CRITICAL') RETURNING request_id
    """), {"m": TEST_MEDICINE_ID}).scalar_one()
    db.commit()

    yield {"batch_id": batch, "req_a": a, "req_b": b}

    _cleanup(db)
    db.commit()


def _cleanup(db):
    m = TEST_MEDICINE_ID
    db.execute(text("DELETE FROM shipment WHERE allocation_id IN "
                    "(SELECT a.allocation_id FROM allocation a "
                    " JOIN emergency_request r ON r.request_id = a.request_id "
                    " WHERE r.medicine_id = :m)"), {"m": m})
    db.execute(text("DELETE FROM allocation_event WHERE batch_id IN "
                    "(SELECT batch_id FROM inventory_batch WHERE medicine_id = :m)"),
               {"m": m})
    db.execute(text("DELETE FROM allocation WHERE request_id IN "
                    "(SELECT request_id FROM emergency_request WHERE medicine_id = :m)"),
               {"m": m})
    db.execute(text("DELETE FROM emergency_request WHERE medicine_id = :m"), {"m": m})
    db.execute(text("DELETE FROM inventory_batch WHERE medicine_id = :m"), {"m": m})
    db.execute(text("DELETE FROM medicine WHERE medicine_id = :m"), {"m": m})
    db.commit()
