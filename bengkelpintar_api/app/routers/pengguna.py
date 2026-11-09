from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import Pengguna
from app.schemas import (
    PenggunaBuat,
    PenggunaDetail,
    PenggunaUbah,
    PesanResponse,
    ResetPasswordRequest,
)
from app.util import IdPath, ambil_atau_404, pola_cari, simpan

router = APIRouter(tags=["Pengguna"])
USERNAME_DUPLIKAT = "Username sudah dipakai."


def _username_dipakai(db: Session, username: str, kecuali_id: int | None = None) -> bool:
    kueri = select(Pengguna.id).where(func.lower(Pengguna.username) == username)
    if kecuali_id is not None:
        kueri = kueri.where(Pengguna.id != kecuali_id)
    return db.scalar(kueri.limit(1)) is not None


@router.get("/pengguna", response_model=list[PenggunaDetail])
def daftar_pengguna(
    q: str | None = None,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    kueri = select(Pengguna).order_by(Pengguna.id)
    if q:
        pola = pola_cari(q)
        kueri = kueri.where(
            Pengguna.nama.ilike(pola, escape="\\") | Pengguna.username.ilike(pola, escape="\\")
        )
    return db.scalars(kueri).all()


@router.post("/pengguna", response_model=PenggunaDetail, status_code=201)
def tambah_pengguna(
    data: PenggunaBuat,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if _username_dipakai(db, data.username):
        raise HTTPException(status_code=409, detail=USERNAME_DUPLIKAT)
    pengguna = Pengguna(
        nama=data.nama,
        username=data.username,
        peran=data.peran,
        aktif=data.aktif,
        password_hash=auth.hash_password(data.password),
    )
    db.add(pengguna)
    simpan(db, USERNAME_DUPLIKAT)
    return pengguna


@router.put("/pengguna/{pengguna_id}", response_model=PenggunaDetail)
def ubah_pengguna(
    pengguna_id: IdPath,
    data: PenggunaUbah,
    admin: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    pengguna = ambil_atau_404(db, Pengguna, pengguna_id, "Pengguna tidak ditemukan.")
    if pengguna.id == admin.id and (not data.aktif or data.peran != "admin"):
        raise HTTPException(
            status_code=400,
            detail="Admin tidak dapat menonaktifkan atau menurunkan peran dirinya sendiri.",
        )
    if _username_dipakai(db, data.username, kecuali_id=pengguna.id):
        raise HTTPException(status_code=409, detail=USERNAME_DUPLIKAT)
    pengguna.nama = data.nama
    pengguna.username = data.username
    pengguna.peran = data.peran
    pengguna.aktif = data.aktif
    simpan(db, USERNAME_DUPLIKAT)
    return pengguna


@router.post("/pengguna/{pengguna_id}/reset-password", response_model=PesanResponse)
def reset_password(
    pengguna_id: IdPath,
    data: ResetPasswordRequest,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    sasaran = ambil_atau_404(db, Pengguna, pengguna_id, "Pengguna tidak ditemukan.")
    sasaran.password_hash = auth.hash_password(data.password_baru)
    db.commit()
    return PesanResponse(pesan="Password berhasil diatur ulang.")
