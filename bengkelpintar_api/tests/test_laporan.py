from datetime import datetime

from sqlalchemy import text

from app.util import WIB, ke_wib
from tests.conftest import header, token_bawaan

SEMUA = {"periode_mulai": "2026-10-23", "periode_selesai": "2026-10-24"}


def adm(klien):
    return header(token_bawaan(klien, "admin"))


def mek(klien):
    return header(token_bawaan(klien, "budi"))


def lapor(klien, mulai, selesai, h=None):
    return klien.get("/laporan/penjualan", params={"periode_mulai": mulai, "periode_selesai": selesai}, headers=h or adm(klien))


def final(klien, items, waktu_final=None, nama="Pelanggan", bayar=None):
    """Buat transaksi lewat API, finalkan, lalu (opsional) geser waktu_final lewat SQL."""
    h = adm(klien)
    t = klien.post("/transaksi", json={"nama_pelanggan": nama, "plat_nomor": "", "items": items}, headers=h).json()
    res = klien.post(
        f"/transaksi/{t['id']}/finalisasi",
        json={"metode_bayar": "tunai", "jumlah_dibayar": bayar or t["total"]},
        headers=h,
    )
    assert res.status_code == 200, res.text
    if waktu_final:
        with klien.mesin.begin() as c:
            c.execute(text("UPDATE transaksi SET waktu_final = :w WHERE id = :i"), {"w": waktu_final, "i": t["id"]})
    return t


def sql(klien, kueri, **param):
    with klien.mesin.connect() as c:
        return c.execute(text(kueri), param).all()


def test_laporan_data_baku_dua_hari(klien):
    res = lapor(klien, "2026-10-23", "2026-10-24")
    assert res.status_code == 200
    isi = res.json()
    assert isi["periode_mulai"] == "2026-10-23" and isi["periode_selesai"] == "2026-10-24"
    assert isi["total_penjualan"] == 295000 + 300000 + 135000
    assert isi["jumlah_transaksi"] == 3
    assert isi["rata_rata"] == 243333
    assert isi["penjualan_per_hari"] == [
        {"tanggal": "2026-10-23", "total": 595000, "jumlah": 2},
        {"tanggal": "2026-10-24", "total": 135000, "jumlah": 1},
    ]
    assert [(t["tipe"], t["nama"], t["jumlah"], t["total"]) for t in isi["terlaris"]] == [
        ("produk", "Aki 12V", 1, 280000),
        ("produk", "Set Rantai dan Gear", 1, 250000),
        ("produk", "Oli Mesin 1 Liter", 1, 55000),
        ("jasa", "Ganti rantai dan gear", 1, 50000),
        ("produk", "Kampas Rem Depan", 1, 45000),
    ]
    assert set(isi["terlaris"][0]) == {"tipe", "id", "nama", "jumlah", "total"}


def test_draft_tidak_masuk_laporan(klien):
    isi = lapor(klien, "2026-10-24", "2026-10-24").json()
    assert isi["jumlah_transaksi"] == 1 and isi["total_penjualan"] == 135000


def test_satu_hari_dan_hari_kosong(klien):
    satu = lapor(klien, "2026-10-23", "2026-10-23").json()
    assert satu["total_penjualan"] == 595000 and satu["jumlah_transaksi"] == 2 and satu["rata_rata"] == 297500
    kosong = lapor(klien, "2026-10-01", "2026-10-22").json()
    assert kosong["total_penjualan"] == 0 and kosong["jumlah_transaksi"] == 0 and kosong["rata_rata"] == 0
    assert kosong["penjualan_per_hari"] == [] and kosong["terlaris"] == []


def test_laporan_memakai_waktu_final_bukan_waktu_pembuatan(klien):
    t = final(klien, [{"tipe": "jasa", "id": 1, "jumlah": 1}], nama="Nginap")
    with klien.mesin.begin() as c:
        c.execute(text("UPDATE transaksi SET waktu = '2030-03-01 08:00+07' WHERE id = :i"), {"i": t["id"]})
        waktu_final = c.execute(text("SELECT waktu_final FROM transaksi WHERE id = :i"), {"i": t["id"]}).scalar()
    hari_final = ke_wib(waktu_final).date().isoformat()
    assert hari_final != "2030-03-01"
    assert lapor(klien, hari_final, hari_final).json()["jumlah_transaksi"] == 1
    assert lapor(klien, "2030-03-01", "2030-03-01").json()["jumlah_transaksi"] == 0


def test_batas_hari_mengikuti_tengah_malam_wib(klien):
    final(klien, [{"tipe": "jasa", "id": 1, "jumlah": 1}], waktu_final="2030-05-01 23:59:59+07")
    final(klien, [{"tipe": "jasa", "id": 2, "jumlah": 1}], waktu_final="2030-05-02 00:00:00+07")
    hari1 = lapor(klien, "2030-05-01", "2030-05-01").json()
    hari2 = lapor(klien, "2030-05-02", "2030-05-02").json()
    assert (hari1["jumlah_transaksi"], hari1["total_penjualan"]) == (1, 20000)
    assert (hari2["jumlah_transaksi"], hari2["total_penjualan"]) == (1, 10000)
    gabung = lapor(klien, "2030-05-01", "2030-05-02").json()
    assert [h["tanggal"] for h in gabung["penjualan_per_hari"]] == ["2030-05-01", "2030-05-02"]


def test_angka_laporan_cocok_dengan_database(klien):
    final(klien, [{"tipe": "produk", "id": 4, "jumlah": 2}, {"tipe": "jasa", "id": 1, "jumlah": 3}], waktu_final="2026-10-24 15:00+07")
    final(klien, [{"tipe": "produk", "id": 1, "jumlah": 3}, {"tipe": "jasa", "id": 1, "jumlah": 2}], waktu_final="2026-10-23 09:00+07")
    final(klien, [{"tipe": "produk", "id": 1, "jumlah": 1}], waktu_final="2026-10-25 10:00+07")
    isi = lapor(klien, "2026-10-23", "2026-10-24").json()

    total, jumlah = sql(
        klien,
        "SELECT COALESCE(SUM(total),0), COUNT(*) FROM transaksi WHERE status='final' "
        "AND waktu_final >= '2026-10-23 00:00+07' AND waktu_final < '2026-10-25 00:00+07'",
    )[0]
    assert (isi["total_penjualan"], isi["jumlah_transaksi"]) == (total, jumlah)
    assert sum(h["total"] for h in isi["penjualan_per_hari"]) == total
    assert sum(h["jumlah"] for h in isi["penjualan_per_hari"]) == jumlah

    for item in isi["terlaris"]:
        kolom = "produk_id" if item["tipe"] == "produk" else "jasa_id"
        jml, nilai = sql(
            klien,
            f"SELECT SUM(i.jumlah), SUM(i.jumlah * i.harga_satuan) FROM item_transaksi i "
            f"JOIN transaksi t ON t.id = i.transaksi_id WHERE t.status='final' "
            f"AND t.waktu_final >= '2026-10-23 00:00+07' AND t.waktu_final < '2026-10-25 00:00+07' "
            f"AND i.tipe = :tipe AND i.{kolom} = :id",
            tipe=item["tipe"], id=item["id"],
        )[0]
        assert (item["jumlah"], item["total"]) == (jml, nilai), item
    jumlah_terjual = [t["jumlah"] for t in isi["terlaris"]]
    assert jumlah_terjual == sorted(jumlah_terjual, reverse=True)
    assert isi["terlaris"][0]["nama"] == "Ganti busi" and isi["terlaris"][0]["jumlah"] == 5


def test_terlaris_maksimal_lima_dan_gabungan_produk_jasa(klien):
    isi = lapor(klien, "2026-10-23", "2026-10-24").json()
    assert len(isi["terlaris"]) == 5
    assert {t["tipe"] for t in isi["terlaris"]} == {"produk", "jasa"}


def test_terlaris_memakai_nama_terkini_dan_tidak_menggabung_id_berbeda(klien):
    h = adm(klien)
    final(klien, [{"tipe": "produk", "id": 1, "jumlah": 1}], waktu_final="2031-01-10 10:00+07")
    p = next(p for p in klien.get("/produk", headers=h).json() if p["id"] == 1)
    klien.put("/produk/1", json={"nama": "Busi Iridium", "kategori_id": p["kategori_id"], "harga": 90000, "stok_minimum": 5, "aktif": True}, headers=h)
    final(klien, [{"tipe": "produk", "id": 1, "jumlah": 1}, {"tipe": "jasa", "id": 1, "jumlah": 1}], waktu_final="2031-01-11 10:00+07")
    isi = lapor(klien, "2031-01-10", "2031-01-11").json()
    busi = next(t for t in isi["terlaris"] if t["tipe"] == "produk")
    assert busi["nama"] == "Busi Iridium" and busi["jumlah"] == 2 and busi["total"] == 25000 + 90000
    jasa = next(t for t in isi["terlaris"] if t["tipe"] == "jasa")
    assert jasa["id"] == 1 and jasa["jumlah"] == 1


def test_rata_rata_dibulatkan_setengah_naik(klien):
    h = adm(klien)
    j2 = klien.post("/jasa", json={"nama": "Jasa Dua", "harga": 2}, headers=h).json()["id"]
    j3 = klien.post("/jasa", json={"nama": "Jasa Tiga", "harga": 3}, headers=h).json()["id"]
    final(klien, [{"tipe": "jasa", "id": j2, "jumlah": 1}], waktu_final="2032-02-02 10:00+07")
    final(klien, [{"tipe": "jasa", "id": j3, "jumlah": 1}], waktu_final="2032-02-02 11:00+07")
    isi = lapor(klien, "2032-02-02", "2032-02-02").json()
    assert isi["total_penjualan"] == 5 and isi["jumlah_transaksi"] == 2 and isi["rata_rata"] == 3


def test_waktu_final_terisi_saat_finalisasi_dan_draft_kosong(klien):
    t = final(klien, [{"tipe": "jasa", "id": 1, "jumlah": 1}])
    baris = dict(sql(klien, "SELECT id, waktu_final FROM transaksi"))
    assert baris[t["id"]] is not None
    assert baris[105] is None
    assert all(baris[i] is not None for i in (102, 103, 104))
    assert abs((datetime.now(WIB) - baris[t["id"]]).total_seconds()) < 60


def test_validasi_parameter(klien):
    h = adm(klien)
    assert klien.get("/laporan/penjualan", headers=h).status_code == 422
    assert klien.get("/laporan/penjualan", params={"periode_mulai": "2026-10-23"}, headers=h).status_code == 422
    assert lapor(klien, "23-10-2026", "2026-10-24").status_code == 422
    assert lapor(klien, "2026-02-30", "2026-03-01").status_code == 422
    sebalik = lapor(klien, "2026-10-24", "2026-10-23")
    assert sebalik.status_code == 400 and "mulai" in sebalik.json()["detail"]
    assert lapor(klien, "2026-01-01", "2027-01-02").status_code == 400
    assert lapor(klien, "2026-01-01", "2027-01-01").status_code == 200


def test_laporan_hanya_admin(klien):
    assert lapor(klien, "2026-10-23", "2026-10-24", h=mek(klien)).status_code == 403
    assert lapor(klien, "2026-10-23", "2026-10-24", h=header(None)).status_code == 401


# ------------------------------------------------------------ statistik
def isi_riwayat(klien, nama_kerusakan, jumlah, pengguna=2):
    with klien.mesin.begin() as c:
        for _ in range(jumlah):
            c.execute(
                text("INSERT INTO riwayat_diagnosis (pengguna_id, gejala, hasil, keyakinan) VALUES (:p, '[]'::jsonb, CAST(:h AS jsonb), 0.8)"),
                {"p": pengguna, "h": '{"kerusakan_utama": {"id": 1, "nama": "%s", "keyakinan": 0.8}}' % nama_kerusakan},
            )


def test_statistik_diagnosis_kosong(klien):
    res = klien.get("/diagnosis/statistik", headers=adm(klien))
    assert res.status_code == 200 and res.json() == {"total": 0, "items": []}


def test_statistik_diagnosis_urut_dan_persentase(klien):
    isi_riwayat(klien, "Aki lemah", 1)
    isi_riwayat(klien, "Busi kotor / aus", 3, pengguna=3)
    with klien.mesin.begin() as c:
        c.execute(text("INSERT INTO riwayat_diagnosis (pengguna_id, gejala, hasil, keyakinan) VALUES (2, '[]'::jsonb, '{}'::jsonb, 0.5)"))
    isi = klien.get("/diagnosis/statistik", headers=adm(klien)).json()
    assert isi["total"] == 4
    assert [(i["nama"], i["jumlah"], i["persentase"]) for i in isi["items"]] == [
        ("Busi kotor / aus", 3, 0.75),
        ("Aki lemah", 1, 0.25),
    ]


def test_statistik_diagnosis_hanya_admin(klien):
    assert klien.get("/diagnosis/statistik", headers=mek(klien)).status_code == 403
    assert klien.get("/diagnosis/statistik", headers=header(None)).status_code == 401
