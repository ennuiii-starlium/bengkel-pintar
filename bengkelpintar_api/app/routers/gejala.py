from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import Gejala, Pengguna
from app.schemas import GejalaBuat, GejalaOut, GejalaUbah
from app.util import IdPath, ambil_atau_404, pola_cari, simpan

router = APIRouter(tags=["Gejala"])
KODE_DUPLIKAT = "Kode gejala sudah dipakai."


@router.get("/gejala", response_model=list[GejalaOut])
def daftar_gejala(
    q: str | None = None,
    _: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = select(Gejala).order_by(Gejala.id)
    if q:
        pola = pola_cari(q)
        kueri = kueri.where(
            Gejala.kode.ilike(pola, escape="\\") | Gejala.nama.ilike(pola, escape="\\")
        )
    return db.scalars(kueri).all()


@router.post("/gejala", response_model=GejalaOut, status_code=201)
def tambah_gejala(
    data: GejalaBuat,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Gejala.id).where(Gejala.kode == data.kode)) is not None:
        raise HTTPException(status_code=409, detail=KODE_DUPLIKAT)
    gejala = Gejala(kode=data.kode, nama=data.nama, kategori=data.kategori, aktif=data.aktif)
    db.add(gejala)
    simpan(db, KODE_DUPLIKAT)
    return gejala


@router.put("/gejala/{gejala_id}", response_model=GejalaOut)
def ubah_gejala(
    gejala_id: IdPath,
    data: GejalaUbah,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    gejala = ambil_atau_404(db, Gejala, gejala_id, "Gejala tidak ditemukan.")
    if data.kode is not None and data.kode != gejala.kode:
        raise HTTPException(status_code=400, detail="Kode gejala tidak dapat diubah.")
    gejala.nama = data.nama
    gejala.kategori = data.kategori
    gejala.aktif = data.aktif
    simpan(db, KODE_DUPLIKAT)
    return gejala
