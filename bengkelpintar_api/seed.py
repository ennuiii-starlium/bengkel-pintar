import os
import sys
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert

import seed_data as data
from app import models_db as m
from app.auth import hash_password
from app.database import engine, pastikan_skema

PASSWORD_BAWAAN = {"admin": "admin123", "budi": "budi123", "rina": "rina123"}

TABEL_BERID = [
    "pengaturan_bengkel",
    "pengguna",
    "kategori",
    "produk",
    "jasa",
    "gejala",
    "kerusakan",
    "transaksi",
    "item_transaksi",
    "mutasi_stok",
]


def _sisipkan(conn, model, baris):
    if baris:
        conn.execute(insert(model).values(baris).on_conflict_do_nothing())


def _password(username):
    nilai = os.getenv(f"SEED_PASSWORD_{username.upper()}", "")
    if nilai:
        return nilai, False
    return PASSWORD_BAWAAN[username], True


def jalankan(mesin=None):
    mesin = mesin or engine
    if mesin is None:
        raise RuntimeError("DATABASE_URL belum diisi di .env")

    m.Base.metadata.create_all(mesin)
    pastikan_skema(mesin)
    pakai_bawaan = []

    with mesin.begin() as conn:
        _sisipkan(conn, m.PengaturanBengkel, [{"id": 1, **data.BENGKEL}])

        pengguna = []
        for id_, nama, username, peran, aktif in data.PENGGUNA:
            sandi, bawaan = _password(username)
            if bawaan:
                pakai_bawaan.append(username)
            pengguna.append(
                dict(
                    id=id_,
                    nama=nama,
                    username=username,
                    peran=peran,
                    aktif=aktif,
                    password_hash=hash_password(sandi),
                )
            )
        _sisipkan(conn, m.Pengguna, pengguna)

        _sisipkan(
            conn,
            m.Kategori,
            [dict(id=i, nama=n, aktif=a) for i, n, a in data.KATEGORI],
        )
        _sisipkan(
            conn,
            m.Produk,
            [
                dict(id=i, nama=n, kategori_id=k, harga=h, stok=s, stok_minimum=sm, aktif=a)
                for i, n, k, h, s, sm, a in data.PRODUK
            ],
        )
        _sisipkan(
            conn,
            m.Jasa,
            [dict(id=i, nama=n, harga=h, aktif=a) for i, n, h, a in data.JASA],
        )
        _sisipkan(
            conn,
            m.Gejala,
            [dict(id=i, kode=k, nama=n, kategori=c, aktif=a) for i, k, n, c, a in data.GEJALA],
        )

        kerusakan, k_produk, k_jasa = [], [], []
        for k in data.KERUSAKAN:
            kerusakan.append(
                {c: k[c] for c in ("id", "kode", "nama", "urgensi", "solusi", "estimasi_waktu_menit", "aktif")}
            )
            k_produk += [dict(kerusakan_id=k["id"], produk_id=p) for p in k["produk_ids"]]
            k_jasa += [dict(kerusakan_id=k["id"], jasa_id=j) for j in k["jasa_ids"]]
        _sisipkan(conn, m.Kerusakan, kerusakan)
        _sisipkan(conn, m.KerusakanProduk, k_produk)
        _sisipkan(conn, m.KerusakanJasa, k_jasa)

        nama_produk = {p[0]: p[1] for p in data.PRODUK}
        nama_jasa = {j[0]: j[1] for j in data.JASA}
        transaksi, item = [], []
        nomor_item = 1
        for t in data.TRANSAKSI:
            total = sum(jumlah * harga for _, _, _, jumlah, harga in t["items"])
            transaksi.append(
                dict(
                    id=t["id"],
                    nomor=t["nomor"],
                    status=t["status"],
                    nama_pelanggan=t["nama_pelanggan"],
                    plat_nomor=t["plat_nomor"],
                    total=total,
                    metode_bayar=t["metode_bayar"],
                    jumlah_dibayar=t["jumlah_dibayar"],
                    dibuat_oleh=t["dibuat_oleh"],
                    difinalkan_oleh=t["difinalkan_oleh"],
                    waktu=datetime.fromisoformat(t["waktu"]),
                    waktu_final=datetime.fromisoformat(t["waktu"]) if t["status"] == "final" else None,
                )
            )
            for tipe, produk_id, jasa_id, jumlah, harga in t["items"]:
                item.append(
                    dict(
                        id=nomor_item,
                        transaksi_id=t["id"],
                        tipe=tipe,
                        produk_id=produk_id,
                        jasa_id=jasa_id,
                        nama=nama_produk[produk_id] if tipe == "produk" else nama_jasa[jasa_id],
                        jumlah=jumlah,
                        harga_satuan=harga,
                    )
                )
                nomor_item += 1
        _sisipkan(conn, m.Transaksi, transaksi)
        _sisipkan(conn, m.ItemTransaksi, item)

        mutasi = [
            dict(id=i, produk_id=i, jumlah=stok, alasan="Stok awal", pengguna_id=1)
            for i, _, _, _, stok, _, _ in data.PRODUK
            if stok > 0
        ]
        _sisipkan(conn, m.MutasiStok, mutasi)

        for tabel in TABEL_BERID:
            conn.execute(
                text(
                    f"SELECT setval(pg_get_serial_sequence('{tabel}', 'id'), "
                    f"GREATEST((SELECT COALESCE(MAX(id), 1) FROM {tabel}), 1))"
                )
            )

    return pakai_bawaan


if __name__ == "__main__":
    bawaan = jalankan()
    print("Seed selesai.")
    if bawaan:
        print(
            "PERINGATAN: password bawaan dipakai untuk: " + ", ".join(bawaan)
            + ". Isi SEED_PASSWORD_<USERNAME> di .env sebelum dipakai di server."
        )
    sys.exit(0)
