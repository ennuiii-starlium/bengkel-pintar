import bcrypt
import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import seed
from app import models_db as m
from app.config import DATABASE_URL, TEST_DATABASE_URL

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL or TEST_DATABASE_URL == DATABASE_URL,
    reason="TEST_DATABASE_URL harus diisi dan berbeda dari DATABASE_URL",
)


@pytest.fixture(scope="module")
def mesin():
    e = create_engine(TEST_DATABASE_URL)
    m.Base.metadata.drop_all(e)
    seed.jalankan(e)
    yield e
    e.dispose()


def hitung(sesi, model):
    return sesi.scalar(select(func.count()).select_from(model))


def test_jumlah_data_awal(mesin):
    with Session(mesin) as s:
        assert hitung(s, m.PengaturanBengkel) == 1
        assert hitung(s, m.Pengguna) == 3
        assert hitung(s, m.Kategori) == 6
        assert hitung(s, m.Produk) == 12
        assert hitung(s, m.Jasa) == 9
        assert hitung(s, m.Gejala) == 18
        assert hitung(s, m.Kerusakan) == 10
        assert hitung(s, m.Transaksi) == 4


def test_seed_ulang_tanpa_duplikasi(mesin):
    with Session(mesin) as s:
        sebelum = {t: hitung(s, t) for t in (m.Pengguna, m.Produk, m.Transaksi, m.ItemTransaksi, m.MutasiStok, m.KerusakanProduk, m.KerusakanJasa)}
    seed.jalankan(mesin)
    with Session(mesin) as s:
        sesudah = {t: hitung(s, t) for t in sebelum}
    assert sebelum == sesudah


def test_total_transaksi_contoh(mesin):
    harapan = {
        "TRX-0105": 45000,
        "TRX-0104": 135000,
        "TRX-0103": 300000,
        "TRX-0102": 295000,
    }
    with Session(mesin) as s:
        for trx in s.scalars(select(m.Transaksi)):
            dari_item = sum(i.jumlah * i.harga_satuan for i in trx.items)
            assert trx.total == dari_item == harapan[trx.nomor]
        assert s.scalar(select(m.Transaksi.status).where(m.Transaksi.nomor == "TRX-0105")) == "draft"


def test_nomor_berikutnya_setelah_seed(mesin):
    with Session(mesin) as s:
        baru = m.Transaksi(nomor="TRX-0106", dibuat_oleh=2)
        s.add(baru)
        s.flush()
        assert baru.id == 106
        s.rollback()


def test_stok_sama_dengan_total_mutasi(mesin):
    with Session(mesin) as s:
        for p in s.scalars(select(m.Produk)):
            total = s.scalar(
                select(func.coalesce(func.sum(m.MutasiStok.jumlah), 0)).where(
                    m.MutasiStok.produk_id == p.id
                )
            )
            assert total == p.stok, p.nama


def test_stok_menipis_dan_habis(mesin):
    with Session(mesin) as s:
        menipis = s.scalars(
            select(m.Produk.nama).where(m.Produk.stok > 0, m.Produk.stok <= m.Produk.stok_minimum)
        ).all()
        habis = s.scalars(select(m.Produk.nama).where(m.Produk.stok == 0)).all()
    assert sorted(menipis) == ["Busi NGK Standar", "CDI"]
    assert habis == ["Kampas Rem Belakang"]


def test_penautan_kerusakan_k01(mesin):
    with Session(mesin) as s:
        k = s.scalar(select(m.Kerusakan).where(m.Kerusakan.kode == "K01"))
        assert sorted(p.nama for p in k.komponen) == ["Busi NGK Standar", "Kabel Busi"]
        assert [j.nama for j in k.jasa] == ["Ganti busi"]


def test_password_tersimpan_sebagai_hash(mesin):
    with Session(mesin) as s:
        admin = s.scalar(select(m.Pengguna).where(m.Pengguna.username == "admin"))
        assert "admin123" not in admin.password_hash
        assert bcrypt.checkpw(b"admin123", admin.password_hash.encode())


def test_stok_negatif_ditolak_database(mesin):
    with Session(mesin) as s:
        with pytest.raises(IntegrityError):
            s.execute(text("UPDATE produk SET stok = -1 WHERE id = 1"))
        s.rollback()


def test_final_tanpa_pembayaran_ditolak_database(mesin):
    with Session(mesin) as s:
        with pytest.raises(IntegrityError):
            s.execute(text("UPDATE transaksi SET status = 'final' WHERE id = 105"))
        s.rollback()
