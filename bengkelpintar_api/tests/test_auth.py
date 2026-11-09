import hashlib

import jwt
import pytest
from sqlalchemy import text

from app import config
from tests.conftest import (
    KUNCI_UJI,
    SECRET_UJI,
    buat_token_manual,
    header,
    masuk,
    token_bawaan,
)


def test_login_berhasil_bentuk_respons(klien):
    res = masuk(klien, "budi", "budi123")
    assert res.status_code == 200
    isi = res.json()
    assert set(isi) == {"access_token", "token_type", "user"}
    assert isi["token_type"] == "bearer"
    assert isi["user"] == {"id": 2, "nama": "Budi Santoso", "peran": "mekanik"}


def test_login_tanpa_api_key_diizinkan(klien):
    res = klien.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200


def test_login_password_salah(klien):
    res = masuk(klien, "budi", "salah")
    assert res.status_code == 401
    assert res.json()["detail"] == "Username atau password salah."


def test_login_username_tidak_ada_pesan_sama(klien):
    res = masuk(klien, "tidakada", "apa-saja")
    assert res.status_code == 401
    assert res.json()["detail"] == "Username atau password salah."


def test_login_pengguna_nonaktif_ditolak(klien):
    with klien.mesin.begin() as c:
        c.execute(text("UPDATE pengguna SET aktif = false WHERE username = 'rina'"))
    res = masuk(klien, "rina", "rina123")
    assert res.status_code == 401
    assert res.json()["detail"] == "Username atau password salah."


def test_login_password_terlalu_panjang_tidak_error(klien):
    assert masuk(klien, "admin", "a" * 100).status_code == 401
    assert masuk(klien, "admin", "é" * 60).status_code == 401


def test_me_dengan_token_dan_api_key(klien):
    res = klien.get("/auth/me", headers=header(token_bawaan(klien, "budi")))
    assert res.status_code == 200
    assert res.json() == {
        "id": 2,
        "nama": "Budi Santoso",
        "peran": "mekanik",
        "username": "budi",
        "aktif": True,
    }
    assert "password" not in str(res.json())


def test_me_tanpa_token_ditolak(klien):
    assert klien.get("/auth/me", headers=header(None)).status_code == 401


def test_me_tanpa_api_key_ditolak(klien):
    token = token_bawaan(klien)
    assert klien.get("/auth/me", headers=header(token, kunci=None)).status_code == 401


def test_me_api_key_salah_ditolak(klien):
    token = token_bawaan(klien)
    res = klien.get("/auth/me", headers=header(token, kunci="salah"))
    assert res.status_code == 401
    assert res.json()["detail"] == "API key tidak valid."


def test_api_key_kosong_di_server_tidak_membuka_akses(klien, monkeypatch):
    token = token_bawaan(klien)
    monkeypatch.setattr(config, "API_KEY", "")
    res = klien.get("/auth/me", headers={"Authorization": f"Bearer {token}", "X-API-Key": ""})
    assert res.status_code == 500


def test_token_kedaluwarsa_ditolak(klien):
    pv = hashlib.sha256(_hash(klien, 1).encode()).hexdigest()[:16]
    token = buat_token_manual(1, pv, exp_menit=-5)
    assert klien.get("/auth/me", headers=header(token)).status_code == 401


def test_token_secret_salah_ditolak(klien):
    pv = hashlib.sha256(_hash(klien, 1).encode()).hexdigest()[:16]
    token = buat_token_manual(1, pv, 60, secret="rahasia-lain-yang-juga-panjang-32-karakter")
    assert klien.get("/auth/me", headers=header(token)).status_code == 401


def test_token_alg_none_ditolak(klien):
    token = jwt.encode({"sub": "1", "exp": 9999999999, "iat": 1, "pv": "x"}, None, algorithm="none")
    assert klien.get("/auth/me", headers=header(token)).status_code == 401


def test_token_sampah_ditolak(klien):
    assert klien.get("/auth/me", headers=header("bukan.token.jwt")).status_code == 401


def test_token_pengguna_dinonaktifkan_ditolak(klien):
    token = token_bawaan(klien, "budi")
    with klien.mesin.begin() as c:
        c.execute(text("UPDATE pengguna SET aktif = false WHERE username = 'budi'"))
    assert klien.get("/auth/me", headers=header(token)).status_code == 401


def test_mekanik_tidak_boleh_reset_password(klien):
    token = token_bawaan(klien, "budi")
    res = klien.post("/pengguna/3/reset-password", json={"password_baru": "baru123"}, headers=header(token))
    assert res.status_code == 403
    assert masuk(klien, "rina", "rina123").status_code == 200


def test_admin_reset_password_pengguna_lain(klien):
    token = token_bawaan(klien, "admin")
    res = klien.post("/pengguna/3/reset-password", json={"password_baru": "baru123"}, headers=header(token))
    assert res.status_code == 200
    assert masuk(klien, "rina", "rina123").status_code == 401
    assert masuk(klien, "rina", "baru123").status_code == 200


def test_reset_password_pengguna_tidak_ada(klien):
    token = token_bawaan(klien, "admin")
    res = klien.post("/pengguna/999/reset-password", json={"password_baru": "baru123"}, headers=header(token))
    assert res.status_code == 404


def test_reset_password_terlalu_pendek(klien):
    token = token_bawaan(klien, "admin")
    res = klien.post("/pengguna/3/reset-password", json={"password_baru": "abc"}, headers=header(token))
    assert res.status_code == 422


def test_ganti_password_berhasil_dan_password_lama_ditolak(klien):
    token = token_bawaan(klien, "budi")
    res = klien.post(
        "/auth/ganti-password",
        json={"password_lama": "budi123", "password_baru": "sandibaru1"},
        headers=header(token),
    )
    assert res.status_code == 200
    assert masuk(klien, "budi", "budi123").status_code == 401
    assert masuk(klien, "budi", "sandibaru1").status_code == 200


def test_token_lama_tidak_berlaku_setelah_password_berubah(klien):
    token_lama = token_bawaan(klien, "budi")
    klien.post(
        "/auth/ganti-password",
        json={"password_lama": "budi123", "password_baru": "sandibaru1"},
        headers=header(token_lama),
    )
    assert klien.get("/auth/me", headers=header(token_lama)).status_code == 401
    token_baru = token_bawaan(klien, "budi", "sandibaru1")
    assert klien.get("/auth/me", headers=header(token_baru)).status_code == 200


def test_ganti_password_lama_salah(klien):
    token = token_bawaan(klien, "budi")
    res = klien.post(
        "/auth/ganti-password",
        json={"password_lama": "bukan-password-lama", "password_baru": "sandibaru1"},
        headers=header(token),
    )
    assert res.status_code == 400
    assert res.json()["detail"] == "Password lama salah."
    assert masuk(klien, "budi", "budi123").status_code == 200


def test_ganti_password_baru_pendek_atau_kepanjangan(klien):
    token = token_bawaan(klien, "budi")
    for baru in ("abc", "é" * 40):
        res = klien.post(
            "/auth/ganti-password",
            json={"password_lama": "budi123", "password_baru": baru},
            headers=header(token),
        )
        assert res.status_code == 422, baru


def test_password_tidak_disimpan_mentah_setelah_ganti(klien):
    token = token_bawaan(klien, "budi")
    klien.post(
        "/auth/ganti-password",
        json={"password_lama": "budi123", "password_baru": "sandibaru1"},
        headers=header(token),
    )
    with klien.mesin.connect() as c:
        h = c.execute(text("SELECT password_hash FROM pengguna WHERE username='budi'")).scalar()
    assert h.startswith("$2") and "sandibaru1" not in h


def test_jwt_secret_pendek_ditolak_saat_dipakai(klien, monkeypatch):
    monkeypatch.setattr(config, "JWT_SECRET", "pendek")
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        klien.post("/auth/login", json={"username": "admin", "password": "admin123"})


def _hash(klien, pengguna_id):
    with klien.mesin.connect() as c:
        return c.execute(text("SELECT password_hash FROM pengguna WHERE id=:i"), {"i": pengguna_id}).scalar()
