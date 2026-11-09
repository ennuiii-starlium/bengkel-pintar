from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app import auth
from app.database import get_db
from app.models_db import Jasa, Kerusakan, Pengguna, Produk
from app.schemas import (
    JasaTerkaitOut,
    KerusakanBuat,
    KerusakanOut,
    KerusakanUbah,
    KomponenTerkaitOut,
)
from app.util import IdPath, ambil_atau_404, pola_cari, simpan

router = APIRouter(tags=["Kerusakan"])
KODE_DUPLIKAT = "Kode kerusakan sudah dipakai."


def _keluar(k: Kerusakan) -> KerusakanOut:
    return KerusakanOut(
        id=k.id,
        kode=k.kode,
        nama=k.nama,
        urgensi=k.urgensi,
        solusi=k.solusi,
        estimasi_waktu_menit=k.estimasi_waktu_menit,
        aktif=k.aktif,
        komponen_terkait=[
            KomponenTerkaitOut(produk_id=p.id, nama=p.nama, harga=p.harga)
            for p in sorted(k.komponen, key=lambda x: x.id)
        ],
        jasa_terkait=[
            JasaTerkaitOut(jasa_id=j.id, nama=j.nama, harga=j.harga)
            for j in sorted(k.jasa, key=lambda x: x.id)
        ],
    )


def _muat(db: Session, model, ids: list[int], label: str) -> list:
    unik = sorted(set(ids))
    if not unik:
        return []
    ditemukan = db.scalars(select(model).where(model.id.in_(unik))).all()
    hilang = sorted(set(unik) - {m.id for m in ditemukan})
    if hilang:
        raise HTTPException(
            status_code=400,
            detail=f"{label} dengan id {', '.join(map(str, hilang))} tidak ditemukan.",
        )
    return list(ditemukan)


@router.get("/kerusakan", response_model=list[KerusakanOut])
def daftar_kerusakan(
    q: str | None = None,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    kueri = (
        select(Kerusakan)
        .options(selectinload(Kerusakan.komponen), selectinload(Kerusakan.jasa))
        .order_by(Kerusakan.id)
    )
    if q:
        pola = pola_cari(q)
        kueri = kueri.where(
            Kerusakan.kode.ilike(pola, escape="\\") | Kerusakan.nama.ilike(pola, escape="\\")
        )
    return [_keluar(k) for k in db.scalars(kueri).all()]


@router.post("/kerusakan", response_model=KerusakanOut, status_code=201)
def tambah_kerusakan(
    data: KerusakanBuat,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if db.scalar(select(Kerusakan.id).where(Kerusakan.kode == data.kode)) is not None:
        raise HTTPException(status_code=409, detail=KODE_DUPLIKAT)
    komponen = _muat(db, Produk, [r.produk_id for r in data.komponen_terkait], "Produk")
    jasa = _muat(db, Jasa, [r.jasa_id for r in data.jasa_terkait], "Jasa")
    kerusakan = Kerusakan(
        kode=data.kode,
        nama=data.nama,
        urgensi=data.urgensi,
        solusi=data.solusi,
        estimasi_waktu_menit=data.estimasi_waktu_menit,
        aktif=data.aktif,
        komponen=komponen,
        jasa=jasa,
    )
    db.add(kerusakan)
    simpan(db, KODE_DUPLIKAT)
    return _keluar(kerusakan)


@router.put("/kerusakan/{kerusakan_id}", response_model=KerusakanOut)
def ubah_kerusakan(
    kerusakan_id: IdPath,
    data: KerusakanUbah,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    kerusakan = ambil_atau_404(db, Kerusakan, kerusakan_id, "Kerusakan tidak ditemukan.")
    if data.kode is not None and data.kode != kerusakan.kode:
        raise HTTPException(status_code=400, detail="Kode kerusakan tidak dapat diubah.")
    kerusakan.komponen = _muat(db, Produk, [r.produk_id for r in data.komponen_terkait], "Produk")
    kerusakan.jasa = _muat(db, Jasa, [r.jasa_id for r in data.jasa_terkait], "Jasa")
    kerusakan.nama = data.nama
    kerusakan.urgensi = data.urgensi
    kerusakan.solusi = data.solusi
    kerusakan.estimasi_waktu_menit = data.estimasi_waktu_menit
    kerusakan.aktif = data.aktif
    simpan(db, KODE_DUPLIKAT)
    db.refresh(kerusakan)
    return _keluar(kerusakan)
