from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import Kategori, Pengguna, Produk
from app.schemas import KategoriBuat, KategoriOut, KategoriUbah
from app.util import IdPath, ambil_atau_404, nama_sudah_ada, pola_cari, simpan

router = APIRouter(tags=["Kategori"])
NAMA_DUPLIKAT = "Nama kategori sudah dipakai."


@router.get("/kategori", response_model=list[KategoriOut])
def daftar_kategori(
    q: str | None = None,
    _: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = select(Kategori).order_by(Kategori.id)
    if q:
        kueri = kueri.where(Kategori.nama.ilike(pola_cari(q), escape="\\"))
    return db.scalars(kueri).all()


@router.post("/kategori", response_model=KategoriOut, status_code=201)
def tambah_kategori(
    data: KategoriBuat,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if nama_sudah_ada(db, Kategori, Kategori.nama, data.nama):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    kategori = Kategori(nama=data.nama, aktif=data.aktif)
    db.add(kategori)
    simpan(db, NAMA_DUPLIKAT)
    return kategori


@router.put("/kategori/{kategori_id}", response_model=KategoriOut)
def ubah_kategori(
    kategori_id: IdPath,
    data: KategoriUbah,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    kategori = ambil_atau_404(db, Kategori, kategori_id, "Kategori tidak ditemukan.")
    if nama_sudah_ada(db, Kategori, Kategori.nama, data.nama, kecuali_id=kategori.id):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    if kategori.aktif and not data.aktif:
        dipakai = db.scalar(
            select(func.count())
            .select_from(Produk)
            .where(Produk.kategori_id == kategori.id, Produk.aktif.is_(True))
        )
        if dipakai:
            raise HTTPException(
                status_code=409,
                detail=f"Kategori masih dipakai {dipakai} produk aktif dan tidak bisa dinonaktifkan.",
            )
    kategori.nama = data.nama
    kategori.aktif = data.aktif
    simpan(db, NAMA_DUPLIKAT)
    return kategori
