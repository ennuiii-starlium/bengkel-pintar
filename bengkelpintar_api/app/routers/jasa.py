from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import Jasa, Pengguna
from app.schemas import JasaBuat, JasaOut, JasaUbah
from app.util import IdPath, ambil_atau_404, nama_sudah_ada, pola_cari, simpan

router = APIRouter(tags=["Jasa"])
NAMA_DUPLIKAT = "Nama jasa sudah dipakai."


@router.get("/jasa", response_model=list[JasaOut])
def daftar_jasa(
    q: str | None = None,
    _: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = select(Jasa).order_by(Jasa.id)
    if q:
        kueri = kueri.where(Jasa.nama.ilike(pola_cari(q), escape="\\"))
    return db.scalars(kueri).all()


@router.post("/jasa", response_model=JasaOut, status_code=201)
def tambah_jasa(
    data: JasaBuat,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if nama_sudah_ada(db, Jasa, Jasa.nama, data.nama):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    jasa = Jasa(nama=data.nama, harga=data.harga, aktif=data.aktif)
    db.add(jasa)
    simpan(db, NAMA_DUPLIKAT)
    return jasa


@router.put("/jasa/{jasa_id}", response_model=JasaOut)
def ubah_jasa(
    jasa_id: IdPath,
    data: JasaUbah,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    jasa = ambil_atau_404(db, Jasa, jasa_id, "Jasa tidak ditemukan.")
    if nama_sudah_ada(db, Jasa, Jasa.nama, data.nama, kecuali_id=jasa.id):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    jasa.nama = data.nama
    jasa.harga = data.harga
    jasa.aktif = data.aktif
    simpan(db, NAMA_DUPLIKAT)
    return jasa
