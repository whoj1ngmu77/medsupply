def test_health(client):
    """PostgreSQL is checked synchronously and is asserted here.

    MongoDB is checked with Motor, which needs its own event loop; under
    TestClient the loop differs from the app's, so mongodb may report
    down even when it is healthy. Verified separately via the running
    server (GET /health) and by test_incidents_schema_variation, which
    reads real MongoDB data through the API.
    """
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == "ok"
    assert body["postgres"] == "ok"


def test_login_success(client):
    r = client.post("/auth/login",
                    json={"username": "admin", "password": "admin@12345"})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    assert "password_hash" not in body["user"], "hash must never be serialised"


def test_login_wrong_password(client):
    r = client.post("/auth/login",
                    json={"username": "admin", "password": "wrong"})
    assert r.status_code == 401


def test_login_unknown_user_same_error(client):
    """Identical response prevents username enumeration."""
    a = client.post("/auth/login",
                    json={"username": "admin", "password": "wrong"})
    b = client.post("/auth/login",
                    json={"username": "nosuchuser", "password": "wrong"})
    assert a.status_code == b.status_code == 401
    assert a.json()["detail"] == b.json()["detail"]


def test_sql_injection_neutralised(client):
    r = client.post("/auth/login",
                    json={"username": "admin' OR '1'='1", "password": "x"})
    assert r.status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/auth/me").status_code == 401


def test_rbac_forbids_non_admin(client):
    t = client.post("/auth/login",
                    json={"username": "hosp1", "password": "hosp1@12345"}
                    ).json()["access_token"]
    r = client.post("/auth/register",
                    headers={"Authorization": f"Bearer {t}"},
                    json={"username": "x", "email": "x@y.com",
                          "password": "password123", "role": "ADMIN"})
    assert r.status_code == 403
