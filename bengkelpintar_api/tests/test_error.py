import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.database import get_db
from app.main import app
from tests.conftest import header, masuk, token_bawaan


def adm(klien):
    return header(token_bawaan(klien, "admin"))


def aman():
    """Klien yang mengembalikan respons 500 apa adanya, seperti server sungguhan."""
    return TestClient(app, raise_server_exceptions=False)


def pastikan_format(res):
    assert res.headers["content-type"].startswith("application/json"), res.text
    isi = res.json()
    assert isinstance(isi["detail"], str) and isi["detail"], isi
    assert set(isi) <= {"detail", "errors"}, isi


# ----------------------------------------------------------- error validasi
def test_422_berbentuk_detail_teks_dan_tidak_membocorkan_masukan(klien):
    res = klien.post("/auth/login", json={"password": "RAHASIA-123"})
    assert res.status_code == 422
    isi = res.json()
    assert set(isi) == {"detail", "errors"}
    assert isi["detail"] == "username wajib diisi."
    assert isi["errors"] == [{"field": "username", "pesan": "wajib diisi."}]
    for kata in ("RAHASIA", "input", "ctx", "loc", "Field required"):
        assert kata not in res.text, kata


def test_422_banyak_kesalahan_diringkas(klien):
    res = klien.post("/produk", json={"nama": "  ", "kategori_id": 1, "harga": -5}, headers=adm(klien))
    isi = res.json()
    assert res.status_code == 422
    assert isi["detail"].endswith("(dan 1 kesalahan lain)")
    assert {e["field"] for e in isi["errors"]} == {"nama", "harga"}


@pytest.mark.parametrize(
    "metode, path, body, harapan",
    [
        ("post", "/produk", {"nama": "x", "kategori_id": 1, "harga": -5}, "harga tidak boleh kurang dari 0."),
        ("post", "/produk", {"nama": "x", "kategori_id": 1, "harga": 1.5}, "harga harus berupa bilangan bulat."),
        ("post", "/produk", {"nama": "x", "kategori_id": 1, "harga": 10**9}, "harga tidak boleh lebih dari 100000000."),
        ("post", "/kategori", {"nama": "a" * 81}, "nama maksimal 80 karakter."),
        ("post", "/kategori", {"nama": "   "}, "nama tidak boleh kosong."),
        ("post", "/kategori", {"nama": "a\u0000b"}, "nama tidak boleh mengandung karakter NUL."),
        ("post", "/transaksi", {"nama_pelanggan": "a", "plat_nomor": "", "items": [{"tipe": "produk", "id": 1, "jumlah": 0}]}, "items[0].jumlah tidak boleh kurang dari 1."),
        ("post", "/transaksi", {"nama_pelanggan": "a", "plat_nomor": "", "items": []}, "items minimal 1 item."),
        ("post", "/transaksi", {"nama_pelanggan": None, "plat_nomor": "", "items": [{"tipe": "produk", "id": 1, "jumlah": 1}]}, "nama_pelanggan harus berupa teks."),
        ("post", "/transaksi", {"nama_pelanggan": "a", "plat_nomor": "", "items": [{"tipe": "barang", "id": 1, "jumlah": 1}]}, "items[0].tipe harus salah satu dari: 'produk' atau 'jasa'."),
        ("post", "/diagnosis/predict", {"gejala_ids": []}, "gejala_ids minimal 1 item."),
        ("post", "/diagnosis/predict", {"gejala_ids": [0]}, "gejala_ids[0] tidak boleh kurang dari 1."),
        ("post", "/pengguna/3/reset-password", {"password_baru": "abc"}, "password_baru minimal 6 karakter."),
        ("post", "/produk/1/stok", {"jumlah": 0, "alasan": "x"}, "jumlah tidak boleh nol."),
        ("post", "/pengguna/3/reset-password", {"password_baru": "é" * 40}, "password_baru terlalu panjang (maksimal 72 byte)."),
        ("get", "/transaksi/abc", None, "transaksi_id harus berupa bilangan bulat."),
        ("get", "/transaksi/0", None, "transaksi_id tidak boleh kurang dari 1."),
        ("get", "/transaksi/99999999999999999999", None, "transaksi_id tidak boleh lebih dari 2147483647."),
        ("get", "/laporan/penjualan?periode_mulai=23-10-2026&periode_selesai=2026-10-24", None, "periode_mulai formatnya harus YYYY-MM-DD."),
        ("get", "/laporan/penjualan?periode_selesai=2026-10-24", None, "periode_mulai wajib diisi."),
    ],
)
def test_pesan_validasi_berbahasa_indonesia(klien, metode, path, body, harapan):
    kw = {"json": body} if body is not None else {}
    res = getattr(klien, metode)(path, headers=adm(klien), **kw)
    assert res.status_code == 422, res.text
    assert res.json()["detail"].startswith(harapan.rstrip(".")), res.json()


def test_body_bukan_json(klien):
    res = klien.post("/kategori", content=b"{rusak", headers={**adm(klien), "Content-Type": "application/json"})
    assert res.status_code == 422
    assert res.json()["detail"] == "Isi permintaan bukan JSON yang valid."
    assert "rusak" not in res.text and "decode" not in res.text.lower()


# ------------------------------------------------- 404, 405, dan error domain
def test_404_dan_405_berbahasa_indonesia_dengan_format_seragam(klien):
    h = adm(klien)
    r404 = klien.get("/tidak-ada", headers=h)
    r405 = klien.delete("/produk/1", headers=h)
    assert (r404.status_code, r404.json()) == (404, {"detail": "Endpoint tidak ditemukan."})
    assert (r405.status_code, r405.json()) == (405, {"detail": "Metode HTTP tidak diizinkan untuk endpoint ini."})


def test_error_domain_tetap_seragam_dan_header_401_terjaga(klien):
    r401 = klien.get("/auth/me", headers=header(None))
    assert r401.status_code == 401 and r401.headers.get("www-authenticate") == "Bearer"
    pastikan_format(r401)
    for res in (
        klien.get("/laporan/penjualan?periode_mulai=2026-10-24&periode_selesai=2026-10-23", headers=adm(klien)),
        klien.get("/transaksi/999", headers=adm(klien)),
        klien.post("/produk/10/stok", json={"jumlah": -1, "alasan": "x"}, headers=adm(klien)),
        klien.get("/pengguna", headers=header(token_bawaan(klien, "budi"))),
        masuk(klien, "admin", "salah"),
    ):
        assert res.status_code in (400, 403, 404, 409, 401)
        pastikan_format(res)


# ------------------------------------------- nilai ekstrem tidak boleh 500
@pytest.mark.parametrize(
    "metode, path, body",
    [
        ("get", "/transaksi/99999999999999999999", None),
        ("put", "/produk/99999999999999999999", {"nama": "x", "kategori_id": 1, "harga": 1, "stok_minimum": 0, "aktif": True}),
        ("post", "/produk", {"nama": "y", "kategori_id": 10**20, "harga": 1}),
        ("post", "/diagnosis/predict", {"gejala_ids": [10**20]}),
        ("post", "/transaksi", {"nama_pelanggan": "a", "plat_nomor": "", "items": [{"tipe": "produk", "id": 10**20, "jumlah": 1}]}),
        ("post", "/transaksi", {"nama_pelanggan": "a", "plat_nomor": "", "riwayat_diagnosis_id": 10**20, "items": [{"tipe": "produk", "id": 1, "jumlah": 1}]}),
        ("post", "/kerusakan", {"kode": "K98", "nama": "x", "urgensi": "rendah", "solusi": "s", "estimasi_waktu_menit": 1, "komponen_terkait": [{"produk_id": 10**20}]}),
        ("post", "/auth/login", {"username": "a\u0000b", "password": "x"}),
        ("post", "/produk", {"nama": "a\u0000b", "kategori_id": 1, "harga": 1}),
        ("post", "/transaksi", {"nama_pelanggan": "a\u0000", "plat_nomor": "", "items": [{"tipe": "produk", "id": 1, "jumlah": 1}]}),
    ],
)
def test_nilai_ekstrem_ditolak_bukan_500(klien, metode, path, body):
    kw = {"json": body} if body is not None else {}
    res = getattr(aman(), metode)(path, headers=adm(klien), **kw)
    assert res.status_code in (400, 401, 404, 422), (res.status_code, res.text)
    pastikan_format(res)


def test_nul_pada_pencarian_ditolak_dengan_json(klien):
    res = aman().get("/produk", params={"q": "a\u0000b"}, headers=adm(klien))
    assert res.status_code == 400
    assert res.json() == {"detail": "Nilai pada data tidak valid atau di luar batas."}


def test_stok_tidak_boleh_melebihi_batas(klien):
    h = adm(klien)
    ok = klien.post("/produk/1/stok", json={"jumlah": 1_000_000 - 4, "alasan": "isi penuh"}, headers=h)
    assert ok.status_code == 200 and ok.json() == {"stok_baru": 1_000_000}
    lebih = klien.post("/produk/1/stok", json={"jumlah": 1, "alasan": "lebih"}, headers=h)
    assert lebih.status_code == 409 and "batas" in lebih.json()["detail"]
    assert klien.post("/produk", json={"nama": "Stok Besar", "kategori_id": 1, "harga": 1, "stok": 1_000_001}, headers=h).status_code == 422


# -------------------------------------------- database mati dan error tak terduga
def test_database_mati_memberi_503_json_tanpa_pesan_driver(klien):
    h = adm(klien)

    def rusak():
        raise OperationalError("SELECT 1", {}, Exception("koneksi ditolak password=RAHASIA-DB host=10.0.0.5"))
        yield

    app.dependency_overrides[get_db] = rusak
    res = aman().get("/kategori", headers=h)
    assert res.status_code == 503
    assert res.json() == {"detail": "Database tidak dapat dihubungi. Coba lagi sebentar."}
    assert "RAHASIA" not in res.text and "10.0.0.5" not in res.text


def test_kesalahan_tak_terduga_memberi_500_json_tanpa_detail_internal(klien):
    h = adm(klien)

    def rusak():
        raise RuntimeError("detail-internal-rahasia /srv/kode.py")
        yield

    app.dependency_overrides[get_db] = rusak
    res = aman().get("/kategori", headers=h)
    assert res.status_code == 500
    assert res.json() == {"detail": "Terjadi kesalahan pada server."}
    assert "rahasia" not in res.text


def test_jwt_secret_pendek_memberi_500_json(klien, monkeypatch):
    from app import config

    monkeypatch.setattr(config, "JWT_SECRET", "pendek")
    res = aman().post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 500 and res.json() == {"detail": "Terjadi kesalahan pada server."}
