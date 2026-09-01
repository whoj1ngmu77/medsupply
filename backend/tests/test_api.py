def test_kpis(client, auth):
    r = client.get("/analytics/kpis", headers=auth)
    assert r.status_code == 200
    assert r.json()["total_hospitals"] > 0


def test_pagination(client, auth):
    r = client.get("/hospitals?limit=5&offset=0", headers=auth)
    body = r.json()
    assert len(body["items"]) == 5
    assert body["total"] > 5


def test_filter_works(client, auth):
    r = client.get("/medicines?criticality=LIFE_SAVING", headers=auth)
    assert all(m["criticality"] == "LIFE_SAVING" for m in r.json()["items"])


def test_validation_rejects_bad_enum(client, auth):
    r = client.post("/hospitals", headers=auth,
                    json={"name": "T", "reg_number": "TN-X-1", "city": "C",
                          "bed_capacity": 10, "emergency_level": "NUCLEAR"})
    assert r.status_code == 422


def test_duplicate_key_returns_409_not_500(client, auth):
    r = client.post("/hospitals", headers=auth,
                    json={"name": "Dup", "reg_number": "TN-HOSP-00001",
                          "city": "Chennai", "bed_capacity": 100})
    assert r.status_code == 409
    assert "constraint" in r.json()["detail"].lower()


def test_error_does_not_leak_internals(client, auth):
    r = client.post("/hospitals", headers=auth,
                    json={"name": "Dup2", "reg_number": "TN-HOSP-00001",
                          "city": "Chennai", "bed_capacity": 100})
    detail = r.json()["detail"]
    assert "hospital" not in detail.lower() or "reg_number" not in detail.lower()


def test_incidents_schema_variation(client, auth):
    r = client.get("/incidents/schema-variation", headers=auth)
    samples = r.json()["samples"]
    assert len(samples) >= 3
    fieldsets = [set(s["detail_fields"]) for s in samples.values()]
    for i in range(len(fieldsets)):
        for j in range(i + 1, len(fieldsets)):
            assert fieldsets[i] != fieldsets[j], "types must differ in shape"
