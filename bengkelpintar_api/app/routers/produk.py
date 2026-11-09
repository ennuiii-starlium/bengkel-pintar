from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app import auth
from app.database import get_db
from app.models_db import Kategori, MutasiStok, Pengguna, Produk
from app.schemas import (
    BATAS_STOK,
    MutasiStokOut,
    PenyesuaianStokRequest,
    ProdukBuat,
    ProdukOut,
    ProdukUbah,
    StokBaruResponse,
)
from app.util import IdPath, ambil_atau_404, ke_wib, nama_sudah_ada, pola_cari, simpan

router = APIRouter(tags=["Produk"])
NAMA_DUPLIKAT = "Nama produk sudah dipakai."


def _keluar(produk: Produk) -> ProdukOut:
    return ProdukOut(
        id=produk.id,
        nama=produk.nama,
        kategori_id=produk.kategori_id,
        kategori_nama=produk.kategori.nama,
        harga=produk.harga,
        stok=produk.stok,
        stok_minimum=produk.stok_minimum,
        aktif=produk.aktif,
    )


def _kategori_valid(db: Session, kategori_id: int, wajib_aktif: bool) -> Kategori:
    kategori = db.get(Kategori, kategori_id)
    if kategori is None:
        raise HTTPException(status_code=400, detail="Kategori tidak ditemukan.")
    if wajib_aktif and not kategori.aktif:
        raise HTTPException(status_code=400, detail="Kategori sudah nonaktif.")
    return kategori


@router.get("/produk", response_model=list[ProdukOut])
def daftar_produk(
    q: str | None = None,
    stok: Literal["menipis", "habis"] | None = None,
    _: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = select(Produk).options(joinedload(Produk.kategori)).order_by(Produk.id)
    if q:
        kueri = kueri.where(Produk.nama.ilike(pola_cari(q), escape="\\"))
    if stok == "habis":
        kueri = kueri.where(Produk.stok == 0)
    elif stok == "menipis":
        kueri = kueri.where(Produk.stok > 0, Produk.stok <= Produk.stok_minimum)
    return [_keluar(p) for p in db.scalars(kueri).all()]


@router.post("/produk", response_model=ProdukOut, status_code=201)
def tambah_produk(
    data: ProdukBuat,
    admin: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    _kategori_valid(db, data.kategori_id, wajib_aktif=data.aktif)
    if nama_sudah_ada(db, Produk, Produk.nama, data.nama):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    produk = Produk(
        nama=data.nama,
        kategori_id=data.kategori_id,
        harga=data.harga,
        stok=data.stok,
        stok_minimum=data.stok_minimum,
        aktif=data.aktif,
    )
    db.add(produk)
    db.flush()
    if data.stok > 0:
        db.add(
            MutasiStok(
                produk_id=produk.id,
                jumlah=data.stok,
                alasan="Stok awal",
                pengguna_id=admin.id,
            )
        )
    simpan(db, NAMA_DUPLIKAT)
    return _keluar(produk)


@router.put("/produk/{produk_id}", response_model=ProdukOut)
def ubah_produk(
    produk_id: IdPath,
    data: ProdukUbah,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    produk = ambil_atau_404(db, Produk, produk_id, "Produk tidak ditemukan.")
    _kategori_valid(
        db,
        data.kategori_id,
        wajib_aktif=data.aktif or data.kategori_id != produk.kategori_id,
    )
    if nama_sudah_ada(db, Produk, Produk.nama, data.nama, kecuali_id=produk.id):
        raise HTTPException(status_code=409, detail=NAMA_DUPLIKAT)
    produk.nama = data.nama
    produk.kategori_id = data.kategori_id
    produk.harga = data.harga
    produk.stok_minimum = data.stok_minimum
    produk.aktif = data.aktif
    simpan(db, NAMA_DUPLIKAT)
    db.refresh(produk)
    return _keluar(produk)


@router.post("/produk/{produk_id}/stok", response_model=StokBaruResponse)
def sesuaikan_stok(
    produk_id: IdPath,
    data: PenyesuaianStokRequest,
    admin: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    produk = db.scalar(select(Produk).where(Produk.id == produk_id).with_for_update())
    if produk is None:
        raise HTTPException(status_code=404, detail="Produk tidak ditemukan.")
    stok_baru = produk.stok + data.jumlah
    if stok_baru < 0:
        raise HTTPException(
            status_code=409,
            detail=f"Stok tidak boleh negatif. Stok saat ini {produk.stok}.",
        )
    if stok_baru > BATAS_STOK:
        raise HTTPException(
            status_code=409,
            detail=f"Stok melebihi batas {BATAS_STOK}. Stok saat ini {produk.stok}.",
        )
    produk.stok = stok_baru
    db.add(
        MutasiStok(
            produk_id=produk.id,
            jumlah=data.jumlah,
            alasan=data.alasan,
            pengguna_id=admin.id,
        )
    )
    db.commit()
    return StokBaruResponse(stok_baru=stok_baru)


@router.get("/produk/{produk_id}/mutasi", response_model=list[MutasiStokOut])
def riwayat_mutasi(
    produk_id: IdPath,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    ambil_atau_404(db, Produk, produk_id, "Produk tidak ditemukan.")
    baris = db.execute(
        select(MutasiStok, Pengguna.nama)
        .join(Pengguna, Pengguna.id == MutasiStok.pengguna_id)
        .where(MutasiStok.produk_id == produk_id)
        .order_by(MutasiStok.waktu.desc(), MutasiStok.id.desc())
    ).all()
    return [
        MutasiStokOut(
            id=m.id,
            produk_id=m.produk_id,
            jumlah=m.jumlah,
            alasan=m.alasan,
            waktu=ke_wib(m.waktu),
            dibuat_oleh=nama,
        )
        for m, nama in baris
    ]
