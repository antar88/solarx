"""End-to-end API tests via FastAPI TestClient against the test database."""

from tests.conftest import TEST_PASSWORD, seed_daily


def test_health_no_auth(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_protected_endpoint_requires_auth(client):
    r = client.get("/api/summary")
    assert r.status_code == 401


def test_login_success_sets_cookie_and_unlocks(client):
    r = client.post("/api/login", json={"username": "hantaro88", "password": TEST_PASSWORD})
    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # Cookie persisted by client -> protected route now works.
    r2 = client.get("/api/summary")
    assert r2.status_code == 200
    assert "today_kwh" in r2.json()


def test_login_wrong_password_rejected(client):
    r = client.post("/api/login", json={"username": "hantaro88", "password": "nope"})
    assert r.status_code == 401
    assert r.json()["detail"] == "Invalid credentials"


def test_login_wrong_username_rejected(client):
    r = client.post("/api/login", json={"username": "intruder", "password": TEST_PASSWORD})
    assert r.status_code == 401


def test_logout_clears_session(client):
    client.post("/api/login", json={"username": "hantaro88", "password": TEST_PASSWORD})
    assert client.get("/api/summary").status_code == 200
    client.post("/api/logout")
    assert client.get("/api/summary").status_code == 401


def test_rate_limit_after_repeated_failures(client):
    # 5 failures allowed, 6th attempt is blocked with 429.
    for _ in range(5):
        r = client.post("/api/login", json={"username": "hantaro88", "password": "bad"})
        assert r.status_code == 401
    r = client.post("/api/login", json={"username": "hantaro88", "password": "bad"})
    assert r.status_code == 429


def test_month_endpoint_returns_series(client, db_conn):
    seed_daily(db_conn, [("2026-06-01", 10.0), ("2025-06-01", 9.0)])
    client.post("/api/login", json={"username": "hantaro88", "password": TEST_PASSWORD})
    r = client.get("/api/month?year=2026&month=6")
    assert r.status_code == 200
    body = r.json()
    assert body["year"] == 2026 and body["month"] == 6
    assert len(body["days"]) == 30
    by_day = {d["day"]: d for d in body["days"]}
    assert by_day[1]["kwh_this"] == 10.0
    assert by_day[1]["kwh_last_year"] == 9.0


def test_month_endpoint_validates_params(client):
    client.post("/api/login", json={"username": "hantaro88", "password": TEST_PASSWORD})
    assert client.get("/api/month?year=2026&month=13").status_code == 422
    assert client.get("/api/month?year=1500&month=6").status_code == 422
