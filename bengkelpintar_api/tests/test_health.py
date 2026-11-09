from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_tanpa_login():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "versi": "1.0"}


def test_docs_terbuka():
    assert client.get("/docs").status_code == 200
