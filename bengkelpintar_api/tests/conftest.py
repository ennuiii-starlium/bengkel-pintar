from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import seed
from app import config
from app.database import get_db
from app.main import app
from app.models_db import Base

KUNCI_UJI = "kunci-api-untuk-uji"
SECRET_UJI = "rahasia-jwt-untuk-uji-minimal-32-karakter"


def punya_database_uji():
    return bool(config.TEST_DATABASE_URL) and config.TEST_DATABASE_URL != config.DATABASE_URL


@pytest.fixture
def klien(monkeypatch):
    if not punya_database_uji():
        pytest.skip("TEST_DATABASE_URL harus diisi dan berbeda dari DATABASE_URL")
    monkeypatch.setattr(config, "API_KEY", KUNCI_UJI)
    monkeypatch.setattr(config, "JWT_SECRET", SECRET_UJI)

    asli = bcrypt.gensalt
    monkeypatch.setattr(bcrypt, "gensalt", lambda rounds=4, prefix=b"2b": asli(rounds, prefix))

    mesin = create_engine(config.TEST_DATABASE_URL)
    Base.metadata.drop_all(mesin)
    seed.jalankan(mesin)

    def ganti_db():
        with Session(mesin) as sesi:
            yield sesi

    app.dependency_overrides[get_db] = ganti_db
    c = TestClient(app)
    c.mesin = mesin
    yield c
    app.dependency_overrides.clear()
    mesin.dispose()


def masuk(klien, username, password):
    return klien.post("/auth/login", json={"username": username, "password": password})


def header(token, kunci=KUNCI_UJI):
    h = {}
    if token:
        h["Authorization"] = f"Bearer {token}"
    if kunci:
        h["X-API-Key"] = kunci
    return h


def token_bawaan(klien, username="admin", password=None):
    sandi = password or {"admin": "admin123", "budi": "budi123", "rina": "rina123"}[username]
    return masuk(klien, username, sandi).json()["access_token"]


def buat_token_manual(sub, pv, exp_menit, secret=SECRET_UJI, algoritma="HS256"):
    sekarang = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(sub), "iat": sekarang, "exp": sekarang + timedelta(minutes=exp_menit), "pv": pv},
        secret,
        algorithm=algoritma,
    )
