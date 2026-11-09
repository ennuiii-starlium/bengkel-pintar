from sqlalchemy import text

from tests.conftest import header, masuk, token_bawaan


def adm(klien):
    return header(token_bawaan(klien, "admin"))


def mek(klien):
    return header(token_bawaan(klien, "budi"))


# ------------------------------------------------------------------ peran
def test_semua_peran_boleh_baca_data_master_umum(klien):
    h = mek(klien)
    for path in ("/kategori", "/produk", "/jasa", "/gejala", "/pengaturan-bengkel"):
        assert klien.get(path, headers=h).status_code == 200, path


def test_mekanik_tidak_boleh_baca_kerusakan_dan_pengguna(klien):
    h = mek(klien)
    assert klien.get("/kerusakan", headers=h).status_code == 403
    assert klien.get("/pengguna", headers=h).status_code == 403


def test_mekanik_tidak_boleh_menulis_data_master(klien):
    h = mek(klien)
    cek = [
        ("post", "/kategori", {"nama": "X"}),
        ("put", "/kategori/1", {"nama": "X", "aktif": True}),
        ("post", "/produk", {"nama": "X", "kategori_id": 1, "harga": 1000}),
        ("put", "/produk/1", {"nama": "X", "kategori_id": 1, "harga": 1000, "stok_minimum": 1, "aktif": True}),
        ("post", "/jasa", {"nama": "X", "harga": 1000}),
        ("put", "/jasa/1", {"nama": "X", "harga": 1000, "aktif": True}),
        ("post", "/gejala", {"kode": "G99", "nama": "X", "kategori": "Mesin"}),
        ("put", "/gejala/1", {"nama": "X", "kategori": "Mesin", "aktif": True}),
        ("post", "/kerusakan", {"kode": "K99", "nama": "X", "urgensi": "rendah", "solusi": "x", "estimasi_waktu_menit": 5}),
        ("post", "/pengguna", {"nama": "X", "username": "xxx", "peran": "mekanik", "password": "abcdef"}),
        ("put", "/pengguna/3", {"nama": "X", "username": "xxx", "peran": "admin", "aktif": True}),
        ("put", "/pengaturan-bengkel", {"nama": "X", "alamat": "X", "telepon": "1"}),
    ]
    for metode, path, body in cek:
        res = getattr(klien, metode)(path, json=body, headers=h)
        assert res.status_code == 403, (metode, path)


def test_tanpa_token_ditolak_di_semua_master(klien):
    for path in ("/kategori", "/produk", "/jasa", "/gejala", "/kerusakan", "/pengguna", "/pengaturan-bengkel"):
        assert klien.get(path, headers=header(None)).status_code == 401, path


# --------------------------------------------------------------- kategori
def test_kategori_daftar_cari_tambah(klien):
    h = adm(klien)
    assert len(klien.get("/kategori", headers=h).json()) == 6
    hasil = klien.get("/kategori", params={"q": "PELUM"}, headers=h).json()
    assert [k["nama"] for k in hasil] == ["Pelumas"]
    res = klien.post("/kategori", json={"nama": "  Aksesoris  "}, headers=h)
    assert res.status_code == 201
    assert res.json()["nama"] == "Aksesoris" and res.json()["aktif"] is True


def test_kategori_nama_ganda_ditolak_tanpa_peduli_huruf(klien):
    h = adm(klien)
    assert klien.post("/kategori", json={"nama": "pelumas"}, headers=h).status_code == 409


def test_kategori_pencarian_tidak_menganggap_persen_sebagai_wildcard(klien):
    assert klien.get("/kategori", params={"q": "%"}, headers=adm(klien)).json() == []


def test_kategori_dipakai_produk_aktif_tidak_bisa_dinonaktifkan(klien):
    h = adm(klien)
    res = klien.put("/kategori/1", json={"nama": "Pengapian", "aktif": False}, headers=h)
    assert res.status_code == 409
    assert "masih dipakai" in res.json()["detail"]


def test_kategori_kosong_bisa_dinonaktifkan_dan_tidak_dihapus(klien):
    h = adm(klien)
    baru = klien.post("/kategori", json={"nama": "Sementara"}, headers=h).json()
    res = klien.put(f"/kategori/{baru['id']}", json={"nama": "Sementara", "aktif": False}, headers=h)
    assert res.status_code == 200 and res.json()["aktif"] is False
    ids = [k["id"] for k in klien.get("/kategori", headers=h).json()]
    assert baru["id"] in ids


def test_kategori_tidak_ditemukan(klien):
    res = klien.put("/kategori/999", json={"nama": "X", "aktif": True}, headers=adm(klien))
    assert res.status_code == 404


# ----------------------------------------------------------------- produk
def test_produk_daftar_memuat_nonaktif_dan_nama_kategori(klien):
    h = adm(klien)
    klien.put("/produk/1", json={"nama": "Busi NGK Standar", "kategori_id": 1, "harga": 25000, "stok_minimum": 5, "aktif": False}, headers=h)
    semua = klien.get("/produk", headers=h).json()
    assert len(semua) == 12
    p1 = next(p for p in semua if p["id"] == 1)
    assert p1["aktif"] is False and p1["kategori_nama"]


def test_produk_tambah_dengan_stok_awal_membuat_mutasi(klien):
    h = adm(klien)
    res = klien.post("/produk", json={"nama": "Filter Bensin", "kategori_id": 1, "harga": 40000, "stok": 7, "stok_minimum": 2}, headers=h)
    assert res.status_code == 201
    isi = res.json()
    assert isi["stok"] == 7 and isi["kategori_nama"] == "Pengapian"
    with klien.mesin.connect() as c:
        total = c.execute(text("SELECT COALESCE(SUM(jumlah),0) FROM mutasi_stok WHERE produk_id=:i"), {"i": isi["id"]}).scalar()
    assert total == 7


def test_produk_tambah_tanpa_stok_tidak_membuat_mutasi(klien):
    h = adm(klien)
    isi = klien.post("/produk", json={"nama": "Spion", "kategori_id": 1, "harga": 30000}, headers=h).json()
    with klien.mesin.connect() as c:
        n = c.execute(text("SELECT COUNT(*) FROM mutasi_stok WHERE produk_id=:i"), {"i": isi["id"]}).scalar()
    assert isi["stok"] == 0 and n == 0


def test_produk_validasi_input(klien):
    h = adm(klien)
    dasar = {"nama": "Baru", "kategori_id": 1, "harga": 1000}
    for ubah in ({"harga": -1}, {"harga": 1.5}, {"harga": True}, {"stok": -3}, {"nama": "   "}, {"harga": 10**9}):
        res = klien.post("/produk", json={**dasar, **ubah}, headers=h)
        assert res.status_code == 422, ubah
    assert klien.post("/produk", json={**dasar, "kategori_id": 999}, headers=h).status_code == 400


def test_produk_nama_ganda_ditolak(klien):
    h = adm(klien)
    res = klien.post("/produk", json={"nama": "busi ngk standar", "kategori_id": 1, "harga": 1000}, headers=h)
    assert res.status_code == 409


def test_produk_kategori_nonaktif_ditolak(klien):
    h = adm(klien)
    kat = klien.post("/kategori", json={"nama": "Mati", "aktif": False}, headers=h).json()
    res = klien.post("/produk", json={"nama": "Baru", "kategori_id": kat["id"], "harga": 1000}, headers=h)
    assert res.status_code == 400


def test_produk_put_tidak_mengubah_stok(klien):
    h = adm(klien)
    sebelum = next(p for p in klien.get("/produk", headers=h).json() if p["id"] == 1)
    res = klien.put(
        "/produk/1",
        json={"nama": sebelum["nama"], "kategori_id": sebelum["kategori_id"], "harga": 27000, "stok_minimum": 3, "stok": 9999, "kategori_nama": "palsu", "aktif": True},
        headers=h,
    )
    assert res.status_code == 200
    isi = res.json()
    assert isi["harga"] == 27000 and isi["stok_minimum"] == 3
    assert isi["stok"] == sebelum["stok"] and isi["kategori_nama"] == sebelum["kategori_nama"]


def test_produk_nonaktif_tidak_dihapus_dan_bisa_diaktifkan_lagi(klien):
    h = adm(klien)
    p = next(p for p in klien.get("/produk", headers=h).json() if p["id"] == 2)
    body = {"nama": p["nama"], "kategori_id": p["kategori_id"], "harga": p["harga"], "stok_minimum": p["stok_minimum"]}
    assert klien.put("/produk/2", json={**body, "aktif": False}, headers=h).json()["aktif"] is False
    assert klien.put("/produk/2", json={**body, "aktif": True}, headers=h).json()["aktif"] is True


def test_produk_cari_dan_tidak_ditemukan(klien):
    h = adm(klien)
    assert all("busi" in p["nama"].lower() for p in klien.get("/produk", params={"q": "BUSI"}, headers=h).json())
    res = klien.put("/produk/999", json={"nama": "X", "kategori_id": 1, "harga": 1, "stok_minimum": 0, "aktif": True}, headers=h)
    assert res.status_code == 404


# ------------------------------------------------------------------- jasa
def test_jasa_tambah_ubah_nonaktif_duplikat(klien):
    h = adm(klien)
    assert len(klien.get("/jasa", headers=h).json()) == 9
    baru = klien.post("/jasa", json={"nama": "Servis AC", "harga": 150000}, headers=h)
    assert baru.status_code == 201
    jid = baru.json()["id"]
    assert klien.put(f"/jasa/{jid}", json={"nama": "Servis AC", "harga": 175000, "aktif": False}, headers=h).json() == {
        "id": jid, "nama": "Servis AC", "harga": 175000, "aktif": False,
    }
    assert klien.post("/jasa", json={"nama": "servis ac", "harga": 1}, headers=h).status_code == 409
    assert klien.put("/jasa/999", json={"nama": "X", "harga": 1, "aktif": True}, headers=h).status_code == 404


# ----------------------------------------------------------------- gejala
def test_gejala_tambah_kode_dinormalkan_dan_unik(klien):
    h = adm(klien)
    res = klien.post("/gejala", json={"kode": " g99 ", "nama": "Bunyi aneh", "kategori": "Mesin"}, headers=h)
    assert res.status_code == 201 and res.json()["kode"] == "G99"
    assert klien.post("/gejala", json={"kode": "G99", "nama": "Lain", "kategori": "Mesin"}, headers=h).status_code == 409
    assert klien.post("/gejala", json={"kode": "bad code", "nama": "x", "kategori": "Mesin"}, headers=h).status_code == 422


def test_gejala_kode_tidak_bisa_diubah(klien):
    h = adm(klien)
    g = klien.get("/gejala", headers=h).json()[0]
    ubah = {"nama": "Nama baru", "kategori": g["kategori"], "aktif": False}
    assert klien.put(f"/gejala/{g['id']}", json={**ubah, "kode": "ZZ9"}, headers=h).status_code == 400
    res = klien.put(f"/gejala/{g['id']}", json={**ubah, "kode": g["kode"]}, headers=h)
    assert res.status_code == 200 and res.json()["nama"] == "Nama baru" and res.json()["aktif"] is False
    res = klien.put(f"/gejala/{g['id']}", json=ubah, headers=h)
    assert res.status_code == 200


# -------------------------------------------------------------- kerusakan
def test_kerusakan_k01_memuat_penautan(klien):
    k = klien.get("/kerusakan", headers=adm(klien)).json()[0]
    assert k["kode"] == "K01"
    assert [c["nama"] for c in k["komponen_terkait"]] == ["Busi NGK Standar", "Kabel Busi"]
    assert [j["nama"] for j in k["jasa_terkait"]] == ["Ganti busi"]
    assert set(k["komponen_terkait"][0]) == {"produk_id", "nama", "harga"}


def test_kerusakan_tambah_dengan_penautan_dan_validasi(klien):
    h = adm(klien)
    body = {
        "kode": "k99", "nama": "Rantai kendor", "urgensi": "sedang", "solusi": "Setel rantai",
        "estimasi_waktu_menit": 20,
        "komponen_terkait": [{"produk_id": 1, "nama": "abaikan"}, {"produk_id": 1}],
        "jasa_terkait": [{"jasa_id": 1}],
    }
    res = klien.post("/kerusakan", json=body, headers=h)
    assert res.status_code == 201
    isi = res.json()
    assert isi["kode"] == "K99" and isi["aktif"] is True
    assert len(isi["komponen_terkait"]) == 1 and isi["jasa_terkait"][0]["jasa_id"] == 1
    assert klien.post("/kerusakan", json=body, headers=h).status_code == 409
    salah = {**body, "kode": "K98", "komponen_terkait": [{"produk_id": 999}]}
    res = klien.post("/kerusakan", json=salah, headers=h)
    assert res.status_code == 400 and "999" in res.json()["detail"]
    assert klien.post("/kerusakan", json={**body, "kode": "K97", "urgensi": "gawat"}, headers=h).status_code == 422


def test_kerusakan_ubah_mengganti_penautan_dan_kode_terkunci(klien):
    h = adm(klien)
    k = klien.get("/kerusakan", headers=h).json()[0]
    body = {
        "nama": k["nama"], "urgensi": "tinggi", "solusi": k["solusi"],
        "estimasi_waktu_menit": 45, "aktif": True,
        "komponen_terkait": [{"produk_id": 3}], "jasa_terkait": [],
    }
    res = klien.put(f"/kerusakan/{k['id']}", json=body, headers=h)
    assert res.status_code == 200
    isi = res.json()
    assert isi["urgensi"] == "tinggi" and [c["produk_id"] for c in isi["komponen_terkait"]] == [3]
    assert isi["jasa_terkait"] == []
    assert klien.put(f"/kerusakan/{k['id']}", json={**body, "kode": "K77"}, headers=h).status_code == 400
    assert klien.put("/kerusakan/999", json=body, headers=h).status_code == 404


# --------------------------------------------------------------- pengguna
def test_pengguna_daftar_tanpa_password(klien):
    res = klien.get("/pengguna", headers=adm(klien))
    assert res.status_code == 200 and len(res.json()) == 3
    assert "password" not in res.text


def test_pengguna_tambah_username_huruf_kecil_dan_bisa_login(klien):
    h = adm(klien)
    res = klien.post("/pengguna", json={"nama": "Doni", "username": "  Doni.K  ", "peran": "mekanik", "password": "rahasia1"}, headers=h)
    assert res.status_code == 201
    assert res.json()["username"] == "doni.k" and res.json()["aktif"] is True
    assert masuk(klien, "DONI.K", "rahasia1").status_code == 200


def test_pengguna_username_ganda_dan_format(klien):
    h = adm(klien)
    dasar = {"nama": "X", "peran": "mekanik", "password": "abcdef"}
    assert klien.post("/pengguna", json={**dasar, "username": "BUDI"}, headers=h).status_code == 409
    for u in ("ab", "dengan spasi", "a" * 51, "a/b"):
        assert klien.post("/pengguna", json={**dasar, "username": u}, headers=h).status_code == 422, u
    assert klien.post("/pengguna", json={**dasar, "username": "baru1", "password": "abc"}, headers=h).status_code == 422
    assert klien.post("/pengguna", json={**dasar, "username": "baru2", "peran": "owner"}, headers=h).status_code == 422


def test_admin_tidak_boleh_menonaktifkan_atau_menurunkan_dirinya(klien):
    h = adm(klien)
    dasar = {"nama": "Andi Pratama", "username": "admin", "peran": "admin", "aktif": True}
    assert klien.put("/pengguna/1", json={**dasar, "aktif": False}, headers=h).status_code == 400
    assert klien.put("/pengguna/1", json={**dasar, "peran": "mekanik"}, headers=h).status_code == 400
    assert klien.put("/pengguna/1", json={**dasar, "nama": "Andi P."}, headers=h).status_code == 200


def test_nonaktifkan_pengguna_langsung_mematikan_aksesnya(klien):
    token_budi = token_bawaan(klien, "budi")
    h = adm(klien)
    res = klien.put("/pengguna/2", json={"nama": "Budi Santoso", "username": "budi", "peran": "mekanik", "aktif": False}, headers=h)
    assert res.status_code == 200
    assert klien.get("/auth/me", headers=header(token_budi)).status_code == 401
    assert masuk(klien, "budi", "budi123").status_code == 401


def test_perubahan_peran_langsung_berlaku(klien):
    token_budi = token_bawaan(klien, "budi")
    assert klien.get("/pengguna", headers=header(token_budi)).status_code == 403
    klien.put("/pengguna/2", json={"nama": "Budi Santoso", "username": "budi", "peran": "admin", "aktif": True}, headers=adm(klien))
    assert klien.get("/pengguna", headers=header(token_budi)).status_code == 200


def test_pengguna_ubah_username_ganda_ditolak_dan_tidak_ditemukan(klien):
    h = adm(klien)
    res = klien.put("/pengguna/2", json={"nama": "Budi", "username": "rina", "peran": "mekanik", "aktif": True}, headers=h)
    assert res.status_code == 409
    res = klien.put("/pengguna/999", json={"nama": "X", "username": "xyz", "peran": "mekanik", "aktif": True}, headers=h)
    assert res.status_code == 404


def test_pengguna_cari(klien):
    hasil = klien.get("/pengguna", params={"q": "rina"}, headers=adm(klien)).json()
    assert [p["username"] for p in hasil] == ["rina"]


# -------------------------------------------------------------- pengaturan
def test_pengaturan_baca_dan_ubah(klien):
    h = adm(klien)
    awal = klien.get("/pengaturan-bengkel", headers=mek(klien)).json()
    assert awal["id"] == 1 and awal["nama"] == "Bengkel Maju Jaya"
    res = klien.put("/pengaturan-bengkel", json={"nama": "Bengkel Baru", "alamat": "Jl. A No. 1", "telepon": "0811"}, headers=h)
    assert res.status_code == 200
    assert klien.get("/pengaturan-bengkel", headers=mek(klien)).json()["nama"] == "Bengkel Baru"
    assert klien.put("/pengaturan-bengkel", json={"nama": " ", "alamat": "x", "telepon": "1"}, headers=h).status_code == 422


def test_pengaturan_dibuat_jika_belum_ada(klien):
    with klien.mesin.begin() as c:
        c.execute(text("DELETE FROM pengaturan_bengkel"))
    h = adm(klien)
    assert klien.get("/pengaturan-bengkel", headers=h).status_code == 404
    res = klien.put("/pengaturan-bengkel", json={"nama": "B", "alamat": "A", "telepon": "1"}, headers=h)
    assert res.status_code == 200 and res.json()["id"] == 1
