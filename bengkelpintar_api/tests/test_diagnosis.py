import re

import pytest
from sqlalchemy import text

from app.main import app
from app.services import aturan_tiruan as at
from app.services.classifier import ambil_pengklasifikasi
from tests.conftest import header, token_bawaan

FORMAT_WAKTU = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
KUNCI_PRD = {
    "riwayat_id", "kerusakan_utama", "kemungkinan_lain", "urgensi", "urgensi_keterangan", "solusi",
    "estimasi_waktu_menit", "komponen_terkait", "jasa_terkait", "estimasi_biaya", "waktu",
}
CONTOH_PRD = [1, 3, 4]  # G01, G03, G04


# ---------------------------------------------------- fungsi skor (tanpa database)
def vektor(*kode):
    return [1 if k in kode else 0 for k in at.KODE_GEJALA]


def peringkat(*kode):
    p = at.AturanTiruan().predict_proba(vektor(*kode))
    return sorted(zip(at.KODE_KERUSAKAN, p), key=lambda x: -x[1])


def test_probabilitas_berjumlah_satu_dan_tidak_negatif():
    m = at.AturanTiruan()
    for kombinasi in ([], ["G01"], ["G01", "G03", "G04"], list(at.KODE_GEJALA)):
        p = m.predict_proba(vektor(*kombinasi))
        assert len(p) == len(at.KODE_KERUSAKAN)
        assert all(0 <= x <= 1 for x in p)
        assert sum(p) == pytest.approx(1.0)


def test_deterministik_antar_instans():
    a = at.AturanTiruan().predict_proba(vektor("G01", "G03", "G04"))
    b = at.AturanTiruan().predict_proba(vektor("G01", "G03", "G04"))
    assert a == b


def test_panjang_vektor_salah_ditolak():
    with pytest.raises(ValueError):
        at.AturanTiruan().predict_proba([1, 0, 1])


def test_matriks_bobot_konsisten_dengan_daftar_gejala_dan_kelas():
    assert set(at.BOBOT) == set(at.KODE_KERUSAKAN)
    dipakai = set()
    for kelas, bobot in at.BOBOT.items():
        assert bobot, kelas
        assert set(bobot) <= set(at.KODE_GEJALA), kelas
        assert all(0 < w <= 1 for w in bobot.values()), kelas
        dipakai |= set(bobot)
    assert dipakai == set(at.KODE_GEJALA)


@pytest.mark.parametrize(
    "gejala, kelas",
    [(["G10"], "K04"), (["G12"], "K05"), (["G11"], "K06"), (["G17"], "K08"), (["G07"], "K03"), (["G16"], "K03"), (["G05", "G09", "G18"], "K02")],
)
def test_gejala_spesifik_menunjuk_kelas_yang_sesuai(gejala, kelas):
    assert peringkat(*gejala)[0][0] == kelas


def test_contoh_prd_kerusakan_utama_k01_lalu_k02():
    urutan = [k for k, _ in peringkat("G01", "G03", "G04")]
    assert urutan[:2] == ["K01", "K02"]


def test_bukti_bertambah_keyakinan_naik():
    satu = dict(peringkat("G07"))["K03"]
    tiga = dict(peringkat("G07", "G08", "G16"))["K03"]
    assert tiga > satu


def test_gejala_bertentangan_membagi_probabilitas():
    sendiri = peringkat("G10")[0][1]
    bertentangan = peringkat("G10", "G12")
    assert bertentangan[0][1] < sendiri
    assert {bertentangan[0][0], bertentangan[1][0]} == {"K04", "K05"}


# --------------------------------------------------------------------- API
def adm(klien):
    return header(token_bawaan(klien, "admin"))


def budi(klien):
    return header(token_bawaan(klien, "budi"))


def rina(klien):
    return header(token_bawaan(klien, "rina"))


def prediksi(klien, ids, h=None):
    return klien.post("/diagnosis/predict", json={"gejala_ids": ids}, headers=h or budi(klien))


def test_contoh_prd_9_3_bentuk_respons(klien):
    res = prediksi(klien, CONTOH_PRD)
    assert res.status_code == 200
    h = res.json()
    assert set(h) == KUNCI_PRD
    assert isinstance(h["riwayat_id"], int)
    assert set(h["kerusakan_utama"]) == {"id", "nama", "keyakinan"}
    assert (h["kerusakan_utama"]["id"], h["kerusakan_utama"]["nama"]) == (1, "Busi kotor / aus")
    assert isinstance(h["kerusakan_utama"]["keyakinan"], float)
    assert 1 <= len(h["kemungkinan_lain"]) <= 2
    assert all(set(k) == {"id", "nama", "keyakinan"} for k in h["kemungkinan_lain"])
    assert h["urgensi"] == "sedang" and h["urgensi_keterangan"] == "Masih bisa dipakai, segera cek"
    assert h["solusi"] == "Bersihkan atau ganti busi" and h["estimasi_waktu_menit"] == 15
    assert h["komponen_terkait"] == [
        {"produk_id": 1, "nama": "Busi NGK Standar", "harga": 25000},
        {"produk_id": 2, "nama": "Kabel Busi", "harga": 35000},
    ]
    assert h["jasa_terkait"] == [{"jasa_id": 1, "nama": "Ganti busi", "harga": 20000}]
    assert set(h["estimasi_biaya"]) == {"min", "max", "keterangan"}
    assert h["estimasi_biaya"]["keterangan"] == "Perkiraan"
    assert FORMAT_WAKTU.match(h["waktu"])


def test_estimasi_biaya_dihitung_dari_harga_database(klien):
    h = prediksi(klien, CONTOH_PRD).json()
    assert (h["estimasi_biaya"]["min"], h["estimasi_biaya"]["max"]) == (20000 + 25000, 20000 + 25000 + 35000)
    admin = adm(klien)
    p = next(p for p in klien.get("/produk", headers=admin).json() if p["id"] == 1)
    klien.put("/produk/1", json={"nama": p["nama"], "kategori_id": p["kategori_id"], "harga": 40000, "stok_minimum": 5, "aktif": True}, headers=admin)
    h = prediksi(klien, CONTOH_PRD).json()
    assert (h["estimasi_biaya"]["min"], h["estimasi_biaya"]["max"]) == (20000 + 35000, 20000 + 40000 + 35000)


def test_produk_dan_jasa_nonaktif_tidak_disarankan(klien):
    admin = adm(klien)
    kabel = next(p for p in klien.get("/produk", headers=admin).json() if p["id"] == 2)
    klien.put("/produk/2", json={"nama": kabel["nama"], "kategori_id": kabel["kategori_id"], "harga": kabel["harga"], "stok_minimum": kabel["stok_minimum"], "aktif": False}, headers=admin)
    klien.put("/jasa/1", json={"nama": "Ganti busi", "harga": 20000, "aktif": False}, headers=admin)
    h = prediksi(klien, CONTOH_PRD).json()
    assert [k["produk_id"] for k in h["komponen_terkait"]] == [1]
    assert h["jasa_terkait"] == []
    assert (h["estimasi_biaya"]["min"], h["estimasi_biaya"]["max"]) == (25000, 25000)


def test_hasil_sama_untuk_masukan_sama_dan_urutan_tidak_berpengaruh(klien):
    a = prediksi(klien, [4, 1, 3]).json()
    b = prediksi(klien, [1, 3, 4, 1, 3]).json()
    for kunci in ("kerusakan_utama", "kemungkinan_lain", "komponen_terkait", "estimasi_biaya"):
        assert a[kunci] == b[kunci]
    assert a["riwayat_id"] != b["riwayat_id"]


def test_keyakinan_tidak_melebihi_satu(klien):
    h = prediksi(klien, CONTOH_PRD).json()
    total = h["kerusakan_utama"]["keyakinan"] + sum(k["keyakinan"] for k in h["kemungkinan_lain"])
    assert 0 < h["kerusakan_utama"]["keyakinan"] <= 1
    assert total <= 1.01
    assert h["kerusakan_utama"]["keyakinan"] >= max(k["keyakinan"] for k in h["kemungkinan_lain"])


def test_riwayat_tersimpan_dan_cocok_dengan_hasil(klien):
    hasil = prediksi(klien, CONTOH_PRD).json()
    daftar = klien.get("/diagnosis/riwayat", headers=budi(klien)).json()
    assert len(daftar) == 1
    r = daftar[0]
    assert set(r) == {"id", "pengguna_id", "pengguna_nama", "gejala", "hasil", "keyakinan", "waktu"}
    assert r["id"] == hasil["riwayat_id"] and r["hasil"] == hasil
    assert (r["pengguna_id"], r["pengguna_nama"]) == (2, "Budi Santoso")
    assert r["keyakinan"] == hasil["kerusakan_utama"]["keyakinan"]
    assert FORMAT_WAKTU.match(r["waktu"]) and r["waktu"] == hasil["waktu"]
    assert [g["kode"] for g in r["gejala"]] == ["G01", "G03", "G04"]
    assert set(r["gejala"][0]) == {"id", "kode", "nama", "kategori", "aktif"}
    assert klien.get(f"/diagnosis/riwayat/{r['id']}", headers=budi(klien)).json() == r


def test_riwayat_menyimpan_salinan_gejala_walau_gejala_diganti_nama(klien):
    prediksi(klien, CONTOH_PRD)
    admin = adm(klien)
    g = klien.get("/gejala", headers=admin).json()[0]
    klien.put(f"/gejala/{g['id']}", json={"nama": "Nama baru", "kategori": g["kategori"], "aktif": True}, headers=admin)
    r = klien.get("/diagnosis/riwayat", headers=budi(klien)).json()[0]
    assert r["gejala"][0]["nama"] == "Mesin susah dihidupkan"


def test_riwayat_mekanik_hanya_miliknya_admin_semua(klien):
    a = prediksi(klien, [10], h=budi(klien)).json()
    b = prediksi(klien, [12], h=rina(klien)).json()
    assert [r["id"] for r in klien.get("/diagnosis/riwayat", headers=budi(klien)).json()] == [a["riwayat_id"]]
    assert [r["id"] for r in klien.get("/diagnosis/riwayat", headers=rina(klien)).json()] == [b["riwayat_id"]]
    semua = klien.get("/diagnosis/riwayat", headers=adm(klien)).json()
    assert [r["id"] for r in semua] == [b["riwayat_id"], a["riwayat_id"]]
    assert klien.get(f"/diagnosis/riwayat/{b['riwayat_id']}", headers=budi(klien)).status_code == 404
    assert klien.get(f"/diagnosis/riwayat/{b['riwayat_id']}", headers=adm(klien)).status_code == 200
    assert klien.get("/diagnosis/riwayat/9999", headers=adm(klien)).status_code == 404


def test_validasi_masukan(klien):
    h = budi(klien)
    for body in ({"gejala_ids": []}, {"gejala_ids": [1.5]}, {"gejala_ids": [True]}, {"gejala_ids": ["1"]}, {"gejala_ids": list(range(1, 52))}, {}):
        assert klien.post("/diagnosis/predict", json=body, headers=h).status_code == 422, body
    salah = prediksi(klien, [1, 999])
    assert salah.status_code == 400 and "999" in salah.json()["detail"]
    assert klien.post("/diagnosis/predict", json={"gejala_ids": [1]}, headers=header(None)).status_code == 401


def test_gejala_nonaktif_ditolak(klien):
    admin = adm(klien)
    g = klien.get("/gejala", headers=admin).json()[0]
    klien.put(f"/gejala/{g['id']}", json={"nama": g["nama"], "kategori": g["kategori"], "aktif": False}, headers=admin)
    res = prediksi(klien, [g["id"]])
    assert res.status_code == 400 and "nonaktif" in res.json()["detail"]
    assert klien.get("/diagnosis/riwayat", headers=budi(klien)).json() == []


def test_gejala_baru_yang_tidak_dikenal_model_diabaikan(klien):
    admin = adm(klien)
    baru = klien.post("/gejala", json={"kode": "G19", "nama": "Bunyi baru", "kategori": "Mesin"}, headers=admin).json()
    sendiri = prediksi(klien, [baru["id"]])
    assert sendiri.status_code == 400 and "belum dikenali" in sendiri.json()["detail"]
    campur = prediksi(klien, [baru["id"], 10]).json()
    murni = prediksi(klien, [10]).json()
    assert campur["kerusakan_utama"] == murni["kerusakan_utama"]
    assert campur["kemungkinan_lain"] == murni["kemungkinan_lain"]


def test_kerusakan_nonaktif_dikeluarkan_dan_probabilitas_dinormalkan(klien):
    admin = adm(klien)
    k1 = klien.get("/kerusakan", headers=admin).json()[0]
    klien.put(
        f"/kerusakan/{k1['id']}",
        json={"nama": k1["nama"], "urgensi": k1["urgensi"], "solusi": k1["solusi"], "estimasi_waktu_menit": k1["estimasi_waktu_menit"], "aktif": False, "komponen_terkait": [], "jasa_terkait": []},
        headers=admin,
    )
    h = prediksi(klien, CONTOH_PRD).json()
    nama = [h["kerusakan_utama"]["nama"]] + [k["nama"] for k in h["kemungkinan_lain"]]
    assert "Busi kotor / aus" not in nama and h["kerusakan_utama"]["nama"] == "Karburator kotor"
    p = dict(zip(at.KODE_KERUSAKAN, at.AturanTiruan().predict_proba(vektor("G01", "G03", "G04"))))
    assert h["kerusakan_utama"]["keyakinan"] == round(p["K02"] / (1 - p["K01"]), 2)
    total = h["kerusakan_utama"]["keyakinan"] + sum(k["keyakinan"] for k in h["kemungkinan_lain"])
    assert total <= 1.01


def test_hasil_bisa_dipakai_untuk_draft_transaksi(klien):
    h = prediksi(klien, CONTOH_PRD).json()
    res = klien.post(
        "/transaksi",
        json={"nama_pelanggan": "Dedi", "plat_nomor": "D 1 X", "riwayat_diagnosis_id": h["riwayat_id"], "items": [{"tipe": "produk", "id": 1, "jumlah": 1}]},
        headers=budi(klien),
    )
    assert res.status_code == 201 and res.json()["riwayat_diagnosis_id"] == h["riwayat_id"]


def test_statistik_membaca_riwayat_nyata(klien):
    prediksi(klien, CONTOH_PRD)
    prediksi(klien, CONTOH_PRD)
    prediksi(klien, [10])
    isi = klien.get("/diagnosis/statistik", headers=adm(klien)).json()
    assert isi["total"] == 3
    assert [(i["nama"], i["jumlah"]) for i in isi["items"]] == [("Busi kotor / aus", 2), ("Kampas rem aus", 1)]
    assert isi["items"][0]["persentase"] == pytest.approx(2 / 3)


def test_pengklasifikasi_bisa_diganti_tanpa_mengubah_bentuk_respons(klien):
    class Palsu:
        kode_gejala = at.KODE_GEJALA
        kode_kerusakan = at.KODE_KERUSAKAN

        def predict_proba(self, v):
            return [0.9 if k == "K04" else (0.1 if k == "K05" else 0.0) for k in self.kode_kerusakan]

    app.dependency_overrides[ambil_pengklasifikasi] = lambda: Palsu()
    try:
        h = prediksi(klien, CONTOH_PRD).json()
    finally:
        app.dependency_overrides.pop(ambil_pengklasifikasi, None)
    assert set(h) == KUNCI_PRD
    assert h["kerusakan_utama"] == {"id": 4, "nama": "Kampas rem aus", "keyakinan": 0.9}
    assert h["kemungkinan_lain"][0]["nama"] == "Kampas kopling aus"
    assert h["urgensi"] == "tinggi"


def test_riwayat_orang_lain_tidak_bisa_dipakai_di_transaksi(klien):
    h = prediksi(klien, CONTOH_PRD, h=rina(klien)).json()
    res = klien.post(
        "/transaksi",
        json={"nama_pelanggan": "X", "plat_nomor": "", "riwayat_diagnosis_id": h["riwayat_id"], "items": [{"tipe": "produk", "id": 1, "jumlah": 1}]},
        headers=budi(klien),
    )
    assert res.status_code == 400
