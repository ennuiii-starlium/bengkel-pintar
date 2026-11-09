import re
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from tests.conftest import header, token_bawaan

FORMAT_WAKTU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")


def adm(klien):
    return header(token_bawaan(klien, "admin"))


def mek(klien):
    return header(token_bawaan(klien, "budi"))


def stok_produk(klien, produk_id):
    daftar = klien.get("/produk", headers=adm(klien)).json()
    return next(p for p in daftar if p["id"] == produk_id)["stok"]


def jumlah_mutasi(klien, produk_id):
    with klien.mesin.connect() as c:
        return c.execute(text("SELECT COUNT(*) FROM mutasi_stok WHERE produk_id=:i"), {"i": produk_id}).scalar()


def selisih_buku(klien):
    """Produk yang stoknya tidak sama dengan total mutasinya (harus kosong)."""
    with klien.mesin.connect() as c:
        return c.execute(
            text(
                "SELECT p.id FROM produk p LEFT JOIN mutasi_stok m ON m.produk_id = p.id "
                "GROUP BY p.id, p.stok HAVING p.stok <> COALESCE(SUM(m.jumlah), 0)"
            )
        ).all()


def test_contoh_prd_busi_4_ditambah_10_menjadi_14(klien):
    h = adm(klien)
    assert stok_produk(klien, 1) == 4
    res = klien.post("/produk/1/stok", json={"jumlah": 10, "alasan": "Barang masuk"}, headers=h)
    assert res.status_code == 200
    assert res.json() == {"stok_baru": 14}
    assert stok_produk(klien, 1) == 14


def test_penyesuaian_tercatat_sebagai_mutasi(klien):
    h = adm(klien)
    klien.post("/produk/1/stok", json={"jumlah": 10, "alasan": "  Barang masuk  "}, headers=h)
    mutasi = klien.get("/produk/1/mutasi", headers=h).json()
    terbaru = mutasi[0]
    assert set(terbaru) == {"id", "produk_id", "jumlah", "alasan", "waktu", "dibuat_oleh"}
    assert terbaru["produk_id"] == 1 and terbaru["jumlah"] == 10
    assert terbaru["alasan"] == "Barang masuk"
    assert terbaru["dibuat_oleh"] == "Andi Pratama"
    assert FORMAT_WAKTU.match(terbaru["waktu"])


def test_mutasi_terbaru_di_atas_dan_ada_stok_awal(klien):
    h = adm(klien)
    klien.post("/produk/1/stok", json={"jumlah": 2, "alasan": "A"}, headers=h)
    klien.post("/produk/1/stok", json={"jumlah": -1, "alasan": "B"}, headers=h)
    mutasi = klien.get("/produk/1/mutasi", headers=h).json()
    assert [m["alasan"] for m in mutasi] == ["B", "A", "Stok awal"]
    assert [m["jumlah"] for m in mutasi] == [-1, 2, 4]


def test_stok_sama_dengan_total_mutasi_setelah_penyesuaian(klien):
    h = adm(klien)
    klien.post("/produk/1/stok", json={"jumlah": 10, "alasan": "masuk"}, headers=h)
    klien.post("/produk/1/stok", json={"jumlah": -5, "alasan": "rusak"}, headers=h)
    klien.post("/produk/10/stok", json={"jumlah": 3, "alasan": "masuk"}, headers=h)
    assert selisih_buku(klien) == []


def test_pengurangan_sampai_tepat_nol_boleh(klien):
    res = klien.post("/produk/1/stok", json={"jumlah": -4, "alasan": "habis terjual"}, headers=adm(klien))
    assert res.status_code == 200 and res.json() == {"stok_baru": 0}


def test_stok_tidak_boleh_negatif_dan_tidak_meninggalkan_jejak(klien):
    h = adm(klien)
    sebelum = jumlah_mutasi(klien, 1)
    res = klien.post("/produk/1/stok", json={"jumlah": -5, "alasan": "salah hitung"}, headers=h)
    assert res.status_code == 409
    assert "negatif" in res.json()["detail"] and "4" in res.json()["detail"]
    assert stok_produk(klien, 1) == 4
    assert jumlah_mutasi(klien, 1) == sebelum


def test_produk_stok_nol_tidak_bisa_dikurangi(klien):
    res = klien.post("/produk/10/stok", json={"jumlah": -1, "alasan": "x"}, headers=adm(klien))
    assert res.status_code == 409


def test_validasi_jumlah_dan_alasan(klien):
    h = adm(klien)
    kasus = [
        {"jumlah": 0, "alasan": "x"},
        {"jumlah": 1.5, "alasan": "x"},
        {"jumlah": True, "alasan": "x"},
        {"jumlah": "5", "alasan": "x"},
        {"jumlah": 1_000_001, "alasan": "x"},
        {"jumlah": 5, "alasan": "   "},
        {"jumlah": 5, "alasan": "x" * 256},
        {"jumlah": 5},
        {"alasan": "x"},
    ]
    for body in kasus:
        assert klien.post("/produk/1/stok", json=body, headers=h).status_code == 422, body
    assert stok_produk(klien, 1) == 4


def test_mekanik_dan_tanpa_token_ditolak(klien):
    body = {"jumlah": 1, "alasan": "x"}
    assert klien.post("/produk/1/stok", json=body, headers=mek(klien)).status_code == 403
    assert klien.get("/produk/1/mutasi", headers=mek(klien)).status_code == 403
    assert klien.post("/produk/1/stok", json=body, headers=header(None)).status_code == 401
    assert klien.get("/produk/1/mutasi", headers=header(None)).status_code == 401
    assert stok_produk(klien, 1) == 4


def test_produk_tidak_ada(klien):
    h = adm(klien)
    assert klien.post("/produk/999/stok", json={"jumlah": 1, "alasan": "x"}, headers=h).status_code == 404
    assert klien.get("/produk/999/mutasi", headers=h).status_code == 404


def test_produk_nonaktif_tetap_bisa_disesuaikan(klien):
    h = adm(klien)
    p = next(p for p in klien.get("/produk", headers=h).json() if p["id"] == 2)
    klien.put("/produk/2", json={"nama": p["nama"], "kategori_id": p["kategori_id"], "harga": p["harga"], "stok_minimum": p["stok_minimum"], "aktif": False}, headers=h)
    res = klien.post("/produk/2/stok", json={"jumlah": 1, "alasan": "koreksi"}, headers=h)
    assert res.status_code == 200


def test_filter_stok_menipis_dan_habis(klien):
    h = adm(klien)
    menipis = klien.get("/produk", params={"stok": "menipis"}, headers=h).json()
    habis = klien.get("/produk", params={"stok": "habis"}, headers=h).json()
    assert sorted(p["nama"] for p in menipis) == ["Busi NGK Standar", "CDI"]
    assert [p["nama"] for p in habis] == ["Kampas Rem Belakang"]
    assert klien.get("/produk", params={"stok": "aneh"}, headers=h).status_code == 422
    klien.post("/produk/1/stok", json={"jumlah": 10, "alasan": "masuk"}, headers=h)
    menipis = klien.get("/produk", params={"stok": "menipis"}, headers=h).json()
    assert [p["nama"] for p in menipis] == ["CDI"]


def test_penyesuaian_bersamaan_tidak_membuat_stok_salah(klien):
    h = adm(klien)

    def kurangi(_):
        with TestClient(app) as c:
            return c.post("/produk/1/stok", json={"jumlah": -1, "alasan": "uji"}, headers=h).status_code

    with ThreadPoolExecutor(max_workers=12) as kolam:
        kode = list(kolam.map(kurangi, range(12)))
    assert sorted(kode) == [200] * 4 + [409] * 8
    assert stok_produk(klien, 1) == 0
    assert selisih_buku(klien) == []
