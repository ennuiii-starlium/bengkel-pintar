from fastapi.testclient import TestClient

from app import config
from app.main import buat_app

ASAL = "http://localhost:3000"
PREFLIGHT = {
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "authorization,x-api-key,content-type",
}


def test_tanpa_konfigurasi_tidak_ada_header_cors():
    c = TestClient(buat_app([]))
    res = c.get("/health", headers={"Origin": ASAL})
    assert res.status_code == 200
    assert "access-control-allow-origin" not in res.headers
    pre = c.options("/produk", headers={"Origin": ASAL, **PREFLIGHT})
    assert "access-control-allow-origin" not in pre.headers


def test_asal_yang_diizinkan_lolos_preflight():
    c = TestClient(buat_app([ASAL]))
    pre = c.options("/produk", headers={"Origin": ASAL, **PREFLIGHT})
    assert pre.status_code == 200
    assert pre.headers["access-control-allow-origin"] == ASAL
    izin_header = pre.headers["access-control-allow-headers"].lower()
    assert "authorization" in izin_header and "x-api-key" in izin_header
    assert "access-control-allow-credentials" not in pre.headers
    assert "DELETE" not in pre.headers["access-control-allow-methods"]


def test_asal_lain_ditolak():
    c = TestClient(buat_app([ASAL]))
    pre = c.options("/produk", headers={"Origin": "http://jahat.test", **PREFLIGHT})
    assert pre.status_code == 400
    assert "access-control-allow-origin" not in pre.headers
    res = c.get("/health", headers={"Origin": "http://jahat.test"})
    assert "access-control-allow-origin" not in res.headers


def test_permintaan_biasa_dari_asal_diizinkan_membawa_header():
    c = TestClient(buat_app([ASAL]))
    res = c.get("/health", headers={"Origin": ASAL})
    assert res.headers["access-control-allow-origin"] == ASAL


def test_metode_di_luar_daftar_ditolak_preflight():
    c = TestClient(buat_app([ASAL]))
    pre = c.options("/produk/1", headers={"Origin": ASAL, "Access-Control-Request-Method": "DELETE"})
    assert pre.status_code == 400


def test_pabrik_membaca_konfigurasi_env(monkeypatch):
    monkeypatch.setattr(config, "CORS_ORIGINS", [ASAL])
    res = TestClient(buat_app()).get("/health", headers={"Origin": ASAL})
    assert res.headers["access-control-allow-origin"] == ASAL
    monkeypatch.setattr(config, "CORS_ORIGINS", [])
    res = TestClient(buat_app()).get("/health", headers={"Origin": ASAL})
    assert "access-control-allow-origin" not in res.headers
