import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.main import app
from tests.conftest import header, token_bawaan

FORMAT_WAKTU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
KUNCI_BENTUK = {
    "id", "nomor", "status", "nama_pelanggan", "plat_nomor", "total", "metode_bayar",
    "jumlah_dibayar", "kembalian", "dibuat_oleh", "dibuat_oleh_id", "difinalkan_oleh",
    "riwayat_diagnosis_id", "waktu", "items",
}


def adm(klien):
    return header(token_bawaan(klien, "admin"))


def budi(klien):
    return header(token_bawaan(klien, "budi"))


def rina(klien):
    return header(token_bawaan(klien, "rina"))


def draft(klien, h, items, nama="Dedi", plat="D 1234 XX", **tambahan):
    return klien.post("/transaksi", json={"nama_pelanggan": nama, "plat_nomor": plat, "items": items, **tambahan}, headers=h)


BUSI = {"tipe": "produk", "id": 1, "jumlah": 1}
GANTI_BUSI = {"tipe": "jasa", "id": 1, "jumlah": 1}


def stok(klien, produk_id):
    return next(p for p in klien.get("/produk", headers=adm(klien)).json() if p["id"] == produk_id)["stok"]


def hitung(klien, sql, **param):
    with klien.mesin.connect() as c:
        return c.execute(text(sql), param).scalar()


def selisih_buku(klien):
    with klien.mesin.connect() as c:
        return c.execute(
            text(
                "SELECT p.id FROM produk p LEFT JOIN mutasi_stok m ON m.produk_id = p.id "
                "GROUP BY p.id, p.stok HAVING p.stok <> COALESCE(SUM(m.jumlah), 0)"
            )
        ).all()


# ----------------------------------------------------------------- draft
def test_buat_draft_bentuk_dan_nomor(klien):
    res = draft(klien, budi(klien), [BUSI, GANTI_BUSI])
    assert res.status_code == 201
    t = res.json()
    assert set(t) == KUNCI_BENTUK
    assert t["nomor"] == "TRX-0106" and t["status"] == "draft"
    assert t["total"] == 45000
    assert t["dibuat_oleh"] == "Budi Santoso" and t["dibuat_oleh_id"] == 2
    assert t["metode_bayar"] is None and t["kembalian"] is None and t["difinalkan_oleh"] is None
    assert FORMAT_WAKTU.match(t["waktu"])
    assert set(t["items"][0]) == {"id", "tipe", "produk_id", "jasa_id", "nama", "jumlah", "harga_satuan", "subtotal"}
    assert [(i["nama"], i["harga_satuan"], i["subtotal"]) for i in t["items"]] == [
        ("Busi NGK Standar", 25000, 25000),
        ("Ganti busi", 20000, 20000),
    ]


def test_nomor_berurutan(klien):
    h = budi(klien)
    a = draft(klien, h, [BUSI]).json()["nomor"]
    b = draft(klien, h, [BUSI]).json()["nomor"]
    assert (a, b) == ("TRX-0106", "TRX-0107")


def test_draft_tidak_mengubah_stok(klien):
    draft(klien, budi(klien), [{"tipe": "produk", "id": 1, "jumlah": 2}])
    assert stok(klien, 1) == 4


def test_nama_dan_plat_wajib_string_bukan_null(klien):
    h = budi(klien)
    for body in (
        {"nama_pelanggan": None, "plat_nomor": "D 1 X", "items": [BUSI]},
        {"nama_pelanggan": "Dedi", "plat_nomor": None, "items": [BUSI]},
        {"plat_nomor": "D 1 X", "items": [BUSI]},
        {"nama_pelanggan": "Dedi", "items": [BUSI]},
    ):
        assert klien.post("/transaksi", json=body, headers=h).status_code == 422, body


def test_nama_kosong_menjadi_pelanggan_umum_dan_plat_boleh_kosong(klien):
    t = draft(klien, budi(klien), [BUSI], nama="   ", plat="").json()
    assert t["nama_pelanggan"] == "Pelanggan Umum" and t["plat_nomor"] == ""


def test_validasi_item(klien):
    h = budi(klien)
    salah = [
        [],
        [{"tipe": "produk", "id": 1, "jumlah": 0}],
        [{"tipe": "produk", "id": 1, "jumlah": -1}],
        [{"tipe": "produk", "id": 1, "jumlah": 1.5}],
        [{"tipe": "produk", "id": 1, "jumlah": True}],
        [{"tipe": "produk", "id": 1, "jumlah": 10_001}],
        [{"tipe": "barang", "id": 1, "jumlah": 1}],
        [{"tipe": "produk", "jumlah": 1}],
    ]
    for items in salah:
        assert draft(klien, h, items).status_code == 422, items
    assert draft(klien, h, [{"tipe": "produk", "id": 999, "jumlah": 1}]).status_code == 400
    assert draft(klien, h, [{"tipe": "jasa", "id": 999, "jumlah": 1}]).status_code == 400


def test_produk_nonaktif_tidak_bisa_masuk_draft(klien):
    p = next(p for p in klien.get("/produk", headers=adm(klien)).json() if p["id"] == 2)
    klien.put("/produk/2", json={"nama": p["nama"], "kategori_id": p["kategori_id"], "harga": p["harga"], "stok_minimum": p["stok_minimum"], "aktif": False}, headers=adm(klien))
    res = draft(klien, budi(klien), [{"tipe": "produk", "id": 2, "jumlah": 1}])
    assert res.status_code == 400 and "nonaktif" in res.json()["detail"]


def test_total_terlalu_besar_ditolak(klien):
    h = adm(klien)
    mahal = klien.post("/produk", json={"nama": "Mesin Utuh", "kategori_id": 1, "harga": 100_000_000, "stok": 50}, headers=h).json()
    res = draft(klien, h, [{"tipe": "produk", "id": mahal["id"], "jumlah": 30}])
    assert res.status_code == 400 and "terlalu besar" in res.json()["detail"]


def test_tanpa_token_ditolak(klien):
    assert klien.get("/transaksi", headers=header(None)).status_code == 401
    assert klien.post("/transaksi", json={}, headers=header(None)).status_code == 401


# ------------------------------------------------------------- visibilitas
def test_mekanik_hanya_melihat_draft_miliknya(klien):
    d_budi = draft(klien, budi(klien), [BUSI]).json()
    d_rina = draft(klien, rina(klien), [BUSI]).json()
    daftar = klien.get("/transaksi", headers=budi(klien)).json()
    assert [t["nomor"] for t in daftar] == [d_budi["nomor"], "TRX-0105"]
    assert d_rina["nomor"] not in [t["nomor"] for t in daftar]
    assert klien.get(f"/transaksi/{d_rina['id']}", headers=budi(klien)).status_code == 404
    assert klien.get(f"/transaksi/{d_budi['id']}", headers=budi(klien)).status_code == 200


def test_mekanik_tidak_bisa_mengubah_draft_orang_lain(klien):
    d_rina = draft(klien, rina(klien), [BUSI]).json()
    res = klien.put(f"/transaksi/{d_rina['id']}", json={"nama_pelanggan": "X", "plat_nomor": "", "items": [BUSI]}, headers=budi(klien))
    assert res.status_code == 404


def test_mekanik_bisa_melihat_detail_transaksi_finalnya_sendiri(klien):
    assert klien.get("/transaksi/104", headers=rina(klien)).status_code == 200
    assert klien.get("/transaksi/104", headers=budi(klien)).status_code == 404
    assert [t["id"] for t in klien.get("/transaksi", headers=rina(klien)).json()] == []


def test_admin_melihat_semua_dengan_filter_dan_pencarian(klien):
    h = adm(klien)
    semua = klien.get("/transaksi", headers=h).json()
    assert len(semua) == 4
    assert [t["nomor"] for t in semua][0] == "TRX-0105"
    finals = klien.get("/transaksi", params={"status": "final"}, headers=h).json()
    assert sorted(t["nomor"] for t in finals) == ["TRX-0102", "TRX-0103", "TRX-0104"]
    assert [t["nomor"] for t in klien.get("/transaksi", params={"q": "siti"}, headers=h).json()] == ["TRX-0104"]
    assert [t["nomor"] for t in klien.get("/transaksi", params={"q": "d 1234"}, headers=h).json()] == ["TRX-0105"]
    assert [t["nomor"] for t in klien.get("/transaksi", params={"q": "0103"}, headers=h).json()] == ["TRX-0103"]
    assert klien.get("/transaksi", params={"status": "batal"}, headers=h).status_code == 422
    assert klien.get("/transaksi/999", headers=h).status_code == 404


def test_data_seed_sama_dengan_mock_flutter(klien):
    mock = Path(__file__).resolve().parents[2] / "bengkelpintar" / "assets" / "mock" / "transaksi.json"
    if not mock.is_file():
        pytest.skip(f"berkas mock Flutter tidak ditemukan di {mock}")
    harapan = json.loads(mock.read_text(encoding="utf-8"))

    def tanpa_id_item(t):
        return {**t, "items": [{k: v for k, v in i.items() if k != "id"} for i in t["items"]]}

    api = {t["id"]: tanpa_id_item(t) for t in klien.get("/transaksi", headers=adm(klien)).json()}
    assert api == {t["id"]: tanpa_id_item(t) for t in harapan}


# ------------------------------------------------------------------- ubah
def test_ubah_draft_menghitung_ulang_total_dan_harga_terbaru(klien):
    h = budi(klien)
    t = draft(klien, h, [BUSI]).json()
    p = next(p for p in klien.get("/produk", headers=adm(klien)).json() if p["id"] == 1)
    klien.put("/produk/1", json={"nama": p["nama"], "kategori_id": p["kategori_id"], "harga": 30000, "stok_minimum": 5, "aktif": True}, headers=adm(klien))
    res = klien.put(f"/transaksi/{t['id']}", json={"nama_pelanggan": "Edo", "plat_nomor": "B 9 Z", "items": [{"tipe": "produk", "id": 1, "jumlah": 2}, GANTI_BUSI]}, headers=h)
    assert res.status_code == 200
    isi = res.json()
    assert isi["nomor"] == t["nomor"] and isi["nama_pelanggan"] == "Edo"
    assert isi["total"] == 2 * 30000 + 20000
    assert len(isi["items"]) == 2
    assert hitung(klien, "SELECT COUNT(*) FROM item_transaksi WHERE transaksi_id=:i", i=t["id"]) == 2


def test_nama_item_final_tidak_berubah_walau_produk_diganti_namanya(klien):
    h = adm(klien)
    p = next(p for p in klien.get("/produk", headers=h).json() if p["id"] == 1)
    t = draft(klien, h, [BUSI]).json()
    klien.post(f"/transaksi/{t['id']}/finalisasi", json={"metode_bayar": "tunai", "jumlah_dibayar": 25000}, headers=h)
    klien.put("/produk/1", json={"nama": "Busi Iridium", "kategori_id": p["kategori_id"], "harga": 99000, "stok_minimum": 5, "aktif": True}, headers=h)
    item = klien.get(f"/transaksi/{t['id']}", headers=h).json()["items"][0]
    assert item["nama"] == "Busi NGK Standar" and item["harga_satuan"] == 25000


def test_ubah_draft_menjaga_riwayat_diagnosis(klien):
    with klien.mesin.begin() as c:
        rid = c.execute(text("INSERT INTO riwayat_diagnosis (pengguna_id, gejala, hasil, keyakinan) VALUES (2, '[]'::jsonb, '{}'::jsonb, 0.9) RETURNING id")).scalar()
    h = budi(klien)
    t = draft(klien, h, [BUSI], riwayat_diagnosis_id=rid).json()
    assert t["riwayat_diagnosis_id"] == rid
    res = klien.put(f"/transaksi/{t['id']}", json={"nama_pelanggan": "A", "plat_nomor": "", "items": [GANTI_BUSI]}, headers=h)
    assert res.json()["riwayat_diagnosis_id"] == rid


def test_riwayat_diagnosis_orang_lain_atau_tidak_ada_ditolak(klien):
    with klien.mesin.begin() as c:
        rid = c.execute(text("INSERT INTO riwayat_diagnosis (pengguna_id, gejala, hasil, keyakinan) VALUES (3, '[]'::jsonb, '{}'::jsonb, 0.9) RETURNING id")).scalar()
    assert draft(klien, budi(klien), [BUSI], riwayat_diagnosis_id=rid).status_code == 400
    assert draft(klien, budi(klien), [BUSI], riwayat_diagnosis_id=9999).status_code == 400
    assert draft(klien, adm(klien), [BUSI], riwayat_diagnosis_id=rid).status_code == 201


# -------------------------------------------------------------- finalisasi
def bayar(klien, trx_id, jumlah, metode="tunai", h=None):
    return klien.post(f"/transaksi/{trx_id}/finalisasi", json={"metode_bayar": metode, "jumlah_dibayar": jumlah}, headers=h or adm(klien))


def test_finalisasi_mengurangi_stok_tepat_dan_mencatat_mutasi(klien):
    t = draft(klien, budi(klien), [{"tipe": "produk", "id": 1, "jumlah": 3}, GANTI_BUSI, {"tipe": "produk", "id": 4, "jumlah": 1}]).json()
    assert t["total"] == 3 * 25000 + 20000 + klien.get("/produk", headers=adm(klien)).json()[3]["harga"]
    res = bayar(klien, t["id"], t["total"] + 5000)
    assert res.status_code == 200
    f = res.json()
    assert f["status"] == "final" and f["metode_bayar"] == "tunai"
    assert f["jumlah_dibayar"] == t["total"] + 5000 and f["kembalian"] == 5000
    assert f["difinalkan_oleh"] == "Andi Pratama" and f["dibuat_oleh"] == "Budi Santoso"
    assert stok(klien, 1) == 1 and stok(klien, 4) == 2
    assert hitung(klien, "SELECT jumlah FROM mutasi_stok WHERE transaksi_id=:i AND produk_id=1", i=t["id"]) == -3
    assert hitung(klien, "SELECT alasan FROM mutasi_stok WHERE transaksi_id=:i AND produk_id=1", i=t["id"]) == f"Penjualan {t['nomor']}"
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=t["id"]) == 2
    assert selisih_buku(klien) == []


def test_finalisasi_transfer_dan_hanya_jasa(klien):
    t = draft(klien, budi(klien), [GANTI_BUSI]).json()
    res = bayar(klien, t["id"], 20000, metode="transfer")
    assert res.status_code == 200 and res.json()["metode_bayar"] == "transfer" and res.json()["kembalian"] == 0
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=t["id"]) == 0


def test_stok_kurang_ditolak_dan_stok_tidak_berubah(klien):
    t = draft(klien, budi(klien), [{"tipe": "produk", "id": 1, "jumlah": 5}]).json()
    res = bayar(klien, t["id"], 999_999)
    assert res.status_code == 409
    assert "Busi NGK Standar" in res.json()["detail"] and "tersedia 4" in res.json()["detail"]
    assert stok(klien, 1) == 4
    assert klien.get(f"/transaksi/{t['id']}", headers=adm(klien)).json()["status"] == "draft"
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=t["id"]) == 0


def test_satu_produk_kurang_membatalkan_semua_produk(klien):
    t = draft(klien, budi(klien), [BUSI, {"tipe": "produk", "id": 4, "jumlah": 5}]).json()
    assert bayar(klien, t["id"], 9_999_999).status_code == 409
    assert stok(klien, 1) == 4 and stok(klien, 4) == 3
    assert selisih_buku(klien) == []


def test_baris_ganda_produk_yang_sama_dijumlahkan(klien):
    h = budi(klien)
    lebih = draft(klien, h, [{"tipe": "produk", "id": 1, "jumlah": 3}, {"tipe": "produk", "id": 1, "jumlah": 2}]).json()
    assert bayar(klien, lebih["id"], 999_999).status_code == 409
    pas = draft(klien, h, [{"tipe": "produk", "id": 1, "jumlah": 2}, {"tipe": "produk", "id": 1, "jumlah": 2}]).json()
    assert bayar(klien, pas["id"], pas["total"]).status_code == 200
    assert stok(klien, 1) == 0
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=pas["id"]) == 1


def test_jumlah_dibayar_kurang_ditolak(klien):
    t = draft(klien, budi(klien), [BUSI]).json()
    res = bayar(klien, t["id"], 24999)
    assert res.status_code == 400
    assert stok(klien, 1) == 4
    assert klien.get(f"/transaksi/{t['id']}", headers=adm(klien)).json()["status"] == "draft"


def test_validasi_pembayaran(klien):
    t = draft(klien, budi(klien), [BUSI]).json()
    h = adm(klien)
    for body in (
        {"metode_bayar": "kartu", "jumlah_dibayar": 30000},
        {"metode_bayar": "tunai", "jumlah_dibayar": -1},
        {"metode_bayar": "tunai", "jumlah_dibayar": 1.5},
        {"metode_bayar": "tunai", "jumlah_dibayar": 3_000_000_000},
        {"metode_bayar": "tunai"},
    ):
        assert klien.post(f"/transaksi/{t['id']}/finalisasi", json=body, headers=h).status_code == 422, body


def test_hanya_admin_boleh_finalisasi(klien):
    t = draft(klien, budi(klien), [BUSI]).json()
    res = bayar(klien, t["id"], 25000, h=budi(klien))
    assert res.status_code == 403
    assert stok(klien, 1) == 4


def test_transaksi_final_tidak_bisa_diubah_atau_difinalkan_lagi(klien):
    t = draft(klien, budi(klien), [BUSI]).json()
    assert bayar(klien, t["id"], 25000).status_code == 200
    assert stok(klien, 1) == 3
    ubah = klien.put(f"/transaksi/{t['id']}", json={"nama_pelanggan": "X", "plat_nomor": "", "items": [BUSI]}, headers=adm(klien))
    assert ubah.status_code == 409 and ubah.json()["detail"] == "Transaksi final tidak bisa diubah."
    assert bayar(klien, t["id"], 25000).status_code == 409
    assert stok(klien, 1) == 3


def test_transaksi_seed_final_juga_tidak_bisa_diubah(klien):
    res = klien.put("/transaksi/104", json={"nama_pelanggan": "X", "plat_nomor": "", "items": [BUSI]}, headers=adm(klien))
    assert res.status_code == 409


def test_kegagalan_di_akhir_finalisasi_membatalkan_semuanya(klien):
    t = draft(klien, budi(klien), [BUSI, {"tipe": "produk", "id": 4, "jumlah": 1}]).json()

    def commit_gagal(self):
        self.flush()
        raise RuntimeError("gagal buatan setelah semua perubahan terkirim")

    with pytest.MonkeyPatch.context() as m:
        m.setattr(Session, "commit", commit_gagal)
        with pytest.raises(RuntimeError):
            bayar(klien, t["id"], 999_999)
    assert stok(klien, 1) == 4 and stok(klien, 4) == 3
    assert klien.get(f"/transaksi/{t['id']}", headers=adm(klien)).json()["status"] == "draft"
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=t["id"]) == 0
    assert selisih_buku(klien) == []


def test_finalisasi_ganda_bersamaan_hanya_mengurangi_stok_sekali(klien):
    t = draft(klien, budi(klien), [{"tipe": "produk", "id": 1, "jumlah": 2}]).json()
    h = adm(klien)

    def coba(_):
        c = TestClient(app)
        return c.post(f"/transaksi/{t['id']}/finalisasi", json={"metode_bayar": "tunai", "jumlah_dibayar": 50000}, headers=h).status_code

    with ThreadPoolExecutor(max_workers=6) as kolam:
        kode = list(kolam.map(coba, range(6)))
    assert sorted(kode) == [200] + [409] * 5
    assert stok(klien, 1) == 2
    assert hitung(klien, "SELECT COUNT(*) FROM mutasi_stok WHERE transaksi_id=:i", i=t["id"]) == 1
    assert selisih_buku(klien) == []


def test_dua_transaksi_bersamaan_tidak_membuat_stok_negatif(klien):
    h = adm(klien)
    ids = [draft(klien, budi(klien), [{"tipe": "produk", "id": 1, "jumlah": 1}]).json()["id"] for _ in range(8)]

    def coba(trx_id):
        c = TestClient(app)
        return c.post(f"/transaksi/{trx_id}/finalisasi", json={"metode_bayar": "tunai", "jumlah_dibayar": 25000}, headers=h).status_code

    with ThreadPoolExecutor(max_workers=8) as kolam:
        kode = list(kolam.map(coba, ids))
    assert sorted(kode) == [200] * 4 + [409] * 4
    assert stok(klien, 1) == 0
    assert selisih_buku(klien) == []


# -------------------------------------------------------------------- nota
def test_nota_hanya_admin_dan_hanya_final(klien):
    h = adm(klien)
    nota = klien.get("/transaksi/104/nota", headers=h)
    assert nota.status_code == 200 and set(nota.json()) == KUNCI_BENTUK
    assert nota.json()["kembalian"] == 0 and nota.json()["status"] == "final"
    assert klien.get("/transaksi/105/nota", headers=h).status_code == 409
    assert klien.get("/transaksi/999/nota", headers=h).status_code == 404
    assert klien.get("/transaksi/104/nota", headers=rina(klien)).status_code == 403
    assert klien.get("/transaksi/104/nota", headers=header(None)).status_code == 401
