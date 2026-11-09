from collections import defaultdict
from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import BigInteger, cast, func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import ItemTransaksi, Jasa, Pengguna, Produk, Transaksi
from app.schemas import LaporanPenjualanOut, PenjualanPerHariOut, TerlarisOut
from app.util import WIB, ke_wib

router = APIRouter(tags=["Laporan"])

BATAS_HARI = 366
JUMLAH_TERLARIS = 5

# Waktu penjualan = saat difinalkan. coalesce menjaga baris lama yang belum terisi.
WAKTU_JUAL = func.coalesce(Transaksi.waktu_final, Transaksi.waktu)


def _bagi_bulat_setengah_naik(pembilang: int, penyebut: int) -> int:
    return (2 * pembilang + penyebut) // (2 * penyebut)


@router.get("/laporan/penjualan", response_model=LaporanPenjualanOut)
def laporan_penjualan(
    periode_mulai: date,
    periode_selesai: date,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    if periode_mulai > periode_selesai:
        raise HTTPException(status_code=400, detail="Tanggal mulai tidak boleh setelah tanggal selesai.")
    if (periode_selesai - periode_mulai).days >= BATAS_HARI:
        raise HTTPException(status_code=400, detail=f"Rentang laporan maksimal {BATAS_HARI} hari.")

    awal = datetime.combine(periode_mulai, time.min, tzinfo=WIB)
    akhir = datetime.combine(periode_selesai + timedelta(days=1), time.min, tzinfo=WIB)
    dalam_periode = (Transaksi.status == "final", WAKTU_JUAL >= awal, WAKTU_JUAL < akhir)

    transaksi = db.execute(select(WAKTU_JUAL, Transaksi.total).where(*dalam_periode)).all()
    per_hari: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    total = 0
    for waktu, nilai in transaksi:
        hari = per_hari[ke_wib(waktu).date().isoformat()]
        hari[0] += nilai
        hari[1] += 1
        total += nilai
    jumlah = len(transaksi)

    jumlah_terjual = func.sum(ItemTransaksi.jumlah)
    nilai_terjual = func.sum(cast(ItemTransaksi.jumlah, BigInteger) * ItemTransaksi.harga_satuan)
    nama_saat_ini = func.coalesce(Produk.nama, Jasa.nama, func.max(ItemTransaksi.nama))
    terlaris = db.execute(
        select(
            ItemTransaksi.tipe,
            ItemTransaksi.produk_id,
            ItemTransaksi.jasa_id,
            nama_saat_ini,
            jumlah_terjual,
            nilai_terjual,
        )
        .join(Transaksi, Transaksi.id == ItemTransaksi.transaksi_id)
        .outerjoin(Produk, Produk.id == ItemTransaksi.produk_id)
        .outerjoin(Jasa, Jasa.id == ItemTransaksi.jasa_id)
        .where(*dalam_periode)
        .group_by(
            ItemTransaksi.tipe,
            ItemTransaksi.produk_id,
            ItemTransaksi.jasa_id,
            Produk.nama,
            Jasa.nama,
        )
        .order_by(jumlah_terjual.desc(), nilai_terjual.desc(), nama_saat_ini.asc())
        .limit(JUMLAH_TERLARIS)
    ).all()

    return LaporanPenjualanOut(
        periode_mulai=periode_mulai.isoformat(),
        periode_selesai=periode_selesai.isoformat(),
        total_penjualan=total,
        jumlah_transaksi=jumlah,
        rata_rata=_bagi_bulat_setengah_naik(total, jumlah) if jumlah else 0,
        penjualan_per_hari=[
            PenjualanPerHariOut(tanggal=tgl, total=nilai[0], jumlah=nilai[1])
            for tgl, nilai in sorted(per_hari.items())
        ],
        terlaris=[
            TerlarisOut(
                tipe=tipe,
                id=produk_id if tipe == "produk" else jasa_id,
                nama=nama,
                jumlah=int(jml),
                total=int(nilai),
            )
            for tipe, produk_id, jasa_id, nama, jml, nilai in terlaris
        ],
    )
