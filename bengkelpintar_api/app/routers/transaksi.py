import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app import auth
from app.database import get_db
from app.models_db import (
    ItemTransaksi,
    Jasa,
    MutasiStok,
    Pengguna,
    Produk,
    RiwayatDiagnosis,
    Transaksi,
)
from app.schemas import (
    FinalisasiRequest,
    ItemTransaksiOut,
    ItemTransaksiRequest,
    TransaksiBuat,
    TransaksiOut,
    TransaksiUbah,
)
from app.util import IdPath, ke_wib, pola_cari

router = APIRouter(tags=["Transaksi"])

BATAS_TOTAL = 2_000_000_000
PELANGGAN_UMUM = "Pelanggan Umum"
SUDAH_FINAL = "Transaksi final tidak bisa diubah."


def _keluar(t: Transaksi) -> TransaksiOut:
    final = t.status == "final"
    return TransaksiOut(
        id=t.id,
        nomor=t.nomor,
        status=t.status,
        nama_pelanggan=t.nama_pelanggan or PELANGGAN_UMUM,
        plat_nomor=t.plat_nomor or "",
        total=t.total,
        metode_bayar=t.metode_bayar,
        jumlah_dibayar=t.jumlah_dibayar,
        kembalian=(t.jumlah_dibayar - t.total) if final and t.jumlah_dibayar is not None else None,
        dibuat_oleh=t.pembuat.nama,
        dibuat_oleh_id=t.dibuat_oleh,
        difinalkan_oleh=t.penyelesai.nama if t.penyelesai else None,
        riwayat_diagnosis_id=t.riwayat_diagnosis_id,
        waktu=ke_wib(t.waktu),
        items=[
            ItemTransaksiOut(
                id=i.id,
                tipe=i.tipe,
                produk_id=i.produk_id,
                jasa_id=i.jasa_id,
                nama=i.nama or (i.produk.nama if i.produk else i.jasa.nama),
                jumlah=i.jumlah,
                harga_satuan=i.harga_satuan,
                subtotal=i.jumlah * i.harga_satuan,
            )
            for i in t.items
        ],
    )


def _opsi_muat():
    return (
        selectinload(Transaksi.items),
        selectinload(Transaksi.pembuat),
        selectinload(Transaksi.penyelesai),
    )


def _ambil_terlihat(db: Session, transaksi_id: int, pengguna: Pengguna, kunci: bool = False) -> Transaksi:
    kueri = select(Transaksi).where(Transaksi.id == transaksi_id).options(*_opsi_muat())
    if kunci:
        kueri = kueri.with_for_update(of=Transaksi)
    t = db.scalar(kueri)
    if t is None or (pengguna.peran != "admin" and t.dibuat_oleh != pengguna.id):
        raise HTTPException(status_code=404, detail="Transaksi tidak ditemukan.")
    return t


def _susun_item(db: Session, permintaan: list[ItemTransaksiRequest]) -> tuple[list[ItemTransaksi], int]:
    id_produk = {r.id for r in permintaan if r.tipe == "produk"}
    id_jasa = {r.id for r in permintaan if r.tipe == "jasa"}
    produk = {p.id: p for p in db.scalars(select(Produk).where(Produk.id.in_(id_produk)))} if id_produk else {}
    jasa = {j.id: j for j in db.scalars(select(Jasa).where(Jasa.id.in_(id_jasa)))} if id_jasa else {}

    item: list[ItemTransaksi] = []
    total = 0
    for r in permintaan:
        sumber = produk.get(r.id) if r.tipe == "produk" else jasa.get(r.id)
        label = "Produk" if r.tipe == "produk" else "Jasa"
        if sumber is None:
            raise HTTPException(status_code=400, detail=f"{label} dengan id {r.id} tidak ditemukan.")
        if not sumber.aktif:
            raise HTTPException(status_code=400, detail=f"{label} '{sumber.nama}' sudah nonaktif.")
        total += sumber.harga * r.jumlah
        item.append(
            ItemTransaksi(
                tipe=r.tipe,
                produk_id=sumber.id if r.tipe == "produk" else None,
                jasa_id=sumber.id if r.tipe == "jasa" else None,
                nama=sumber.nama,
                jumlah=r.jumlah,
                harga_satuan=sumber.harga,
            )
        )
    if total > BATAS_TOTAL:
        raise HTTPException(status_code=400, detail="Total transaksi terlalu besar.")
    return item, total


def _nama_pelanggan(nilai: str) -> str:
    return nilai or PELANGGAN_UMUM


@router.get("/transaksi", response_model=list[TransaksiOut])
def daftar_transaksi(
    status: Literal["draft", "final"] | None = None,
    q: str | None = None,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = (
        select(Transaksi)
        .options(*_opsi_muat())
        .order_by(Transaksi.waktu.desc(), Transaksi.id.desc())
    )
    if pengguna.peran != "admin":
        kueri = kueri.where(Transaksi.dibuat_oleh == pengguna.id, Transaksi.status == "draft")
    if status:
        kueri = kueri.where(Transaksi.status == status)
    if q:
        pola = pola_cari(q)
        kueri = kueri.where(
            or_(
                Transaksi.nomor.ilike(pola, escape="\\"),
                Transaksi.nama_pelanggan.ilike(pola, escape="\\"),
                Transaksi.plat_nomor.ilike(pola, escape="\\"),
            )
        )
    return [_keluar(t) for t in db.scalars(kueri).all()]


@router.post("/transaksi", response_model=TransaksiOut, status_code=201)
def buat_draft(
    data: TransaksiBuat,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    if data.riwayat_diagnosis_id is not None:
        riwayat = db.get(RiwayatDiagnosis, data.riwayat_diagnosis_id)
        if riwayat is None or (pengguna.peran != "admin" and riwayat.pengguna_id != pengguna.id):
            raise HTTPException(status_code=400, detail="Riwayat diagnosis tidak ditemukan.")
    item, total = _susun_item(db, data.items)
    t = Transaksi(
        nomor=f"TMP-{uuid.uuid4().hex[:12]}",
        status="draft",
        nama_pelanggan=_nama_pelanggan(data.nama_pelanggan),
        plat_nomor=data.plat_nomor,
        total=total,
        dibuat_oleh=pengguna.id,
        riwayat_diagnosis_id=data.riwayat_diagnosis_id,
        items=item,
    )
    db.add(t)
    db.flush()
    t.nomor = f"TRX-{t.id:04d}"
    db.commit()
    return _keluar(_ambil_terlihat(db, t.id, pengguna))


@router.get("/transaksi/{transaksi_id}", response_model=TransaksiOut)
def detail_transaksi(
    transaksi_id: IdPath,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    return _keluar(_ambil_terlihat(db, transaksi_id, pengguna))


@router.put("/transaksi/{transaksi_id}", response_model=TransaksiOut)
def ubah_draft(
    transaksi_id: IdPath,
    data: TransaksiUbah,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    t = _ambil_terlihat(db, transaksi_id, pengguna, kunci=True)
    if t.status != "draft":
        raise HTTPException(status_code=409, detail=SUDAH_FINAL)
    item, total = _susun_item(db, data.items)
    t.nama_pelanggan = _nama_pelanggan(data.nama_pelanggan)
    t.plat_nomor = data.plat_nomor
    t.items = item
    t.total = total
    db.commit()
    return _keluar(_ambil_terlihat(db, transaksi_id, pengguna))


@router.post("/transaksi/{transaksi_id}/finalisasi", response_model=TransaksiOut)
def finalisasi(
    transaksi_id: IdPath,
    data: FinalisasiRequest,
    admin: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    t = _ambil_terlihat(db, transaksi_id, admin, kunci=True)
    if t.status != "draft":
        raise HTTPException(status_code=409, detail=SUDAH_FINAL)
    if data.jumlah_dibayar < t.total:
        raise HTTPException(status_code=400, detail="Jumlah dibayar kurang dari total.")

    kebutuhan: dict[int, int] = {}
    for i in t.items:
        if i.tipe == "produk":
            kebutuhan[i.produk_id] = kebutuhan.get(i.produk_id, 0) + i.jumlah

    if kebutuhan:
        produk = db.scalars(
            select(Produk).where(Produk.id.in_(kebutuhan)).order_by(Produk.id).with_for_update()
        ).all()
        kurang = [
            f"{p.nama} (tersedia {p.stok}, dibutuhkan {kebutuhan[p.id]})"
            for p in produk
            if p.stok < kebutuhan[p.id]
        ]
        if kurang:
            raise HTTPException(
                status_code=409,
                detail="Stok tidak mencukupi untuk " + "; ".join(kurang) + ".",
            )
        for p in produk:
            p.stok -= kebutuhan[p.id]
            db.add(
                MutasiStok(
                    produk_id=p.id,
                    jumlah=-kebutuhan[p.id],
                    alasan=f"Penjualan {t.nomor}",
                    pengguna_id=admin.id,
                    transaksi_id=t.id,
                )
            )

    t.status = "final"
    t.metode_bayar = data.metode_bayar
    t.jumlah_dibayar = data.jumlah_dibayar
    t.difinalkan_oleh = admin.id
    t.waktu_final = func.now()
    db.commit()
    return _keluar(_ambil_terlihat(db, transaksi_id, admin))


@router.get("/transaksi/{transaksi_id}/nota", response_model=TransaksiOut)
def nota(
    transaksi_id: IdPath,
    admin: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    t = _ambil_terlihat(db, transaksi_id, admin)
    if t.status != "final":
        raise HTTPException(status_code=409, detail="Nota hanya tersedia untuk transaksi final.")
    return _keluar(t)
