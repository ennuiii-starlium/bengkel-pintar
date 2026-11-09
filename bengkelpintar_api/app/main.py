from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth, config
from app.config import APP_VERSION
from app.database import get_db
from app.errors import pasang_penanganan_error
from app.models_db import Pengguna
from app.routers import (
    diagnosis,
    gejala,
    jasa,
    kategori,
    kerusakan,
    laporan,
    pengaturan,
    pengguna,
    produk,
    transaksi,
)
from app.schemas import (
    GantiPasswordRequest,
    HealthResponse,
    LoginRequest,
    LoginResponse,
    PenggunaDetail,
    PesanResponse,
)

dasar = APIRouter()


@dasar.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok", versi=APP_VERSION)


@dasar.post("/auth/login", response_model=LoginResponse)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    pengguna_db = db.scalar(
        select(Pengguna).where(Pengguna.username == data.username.strip().lower())
    )
    hash_pembanding = pengguna_db.password_hash if pengguna_db else auth.hash_tiruan()
    sandi_cocok = auth.verify_password(data.password, hash_pembanding)
    if pengguna_db is None or not pengguna_db.aktif or not sandi_cocok:
        raise HTTPException(status_code=401, detail="Username atau password salah.")
    return LoginResponse(access_token=auth.buat_token(pengguna_db), user=pengguna_db)


@dasar.get("/auth/me", response_model=PenggunaDetail)
def auth_me(pengguna_aktif: Pengguna = Depends(auth.pengguna_saat_ini)):
    return pengguna_aktif


@dasar.post("/auth/ganti-password", response_model=PesanResponse)
def ganti_password(
    data: GantiPasswordRequest,
    pengguna_aktif: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    if not auth.verify_password(data.password_lama, pengguna_aktif.password_hash):
        raise HTTPException(status_code=400, detail="Password lama salah.")
    pengguna_aktif.password_hash = auth.hash_password(data.password_baru)
    db.commit()
    return PesanResponse(pesan="Password berhasil diganti.")


def buat_app(asal_cors: list[str] | None = None) -> FastAPI:
    aplikasi = FastAPI(title="BengkelPintar API", version=APP_VERSION)
    pasang_penanganan_error(aplikasi)
    asal = config.CORS_ORIGINS if asal_cors is None else asal_cors
    if asal:
        aplikasi.add_middleware(
            CORSMiddleware,
            allow_origins=asal,
            allow_methods=["GET", "POST", "PUT"],
            allow_headers=["Authorization", "X-API-Key", "Content-Type"],
            allow_credentials=False,
            max_age=600,
        )
    aplikasi.include_router(dasar)
    for modul in (
        kategori, produk, jasa, gejala, kerusakan, pengguna, pengaturan, transaksi, laporan, diagnosis
    ):
        aplikasi.include_router(modul.router)
    return aplikasi


app = buat_app()
