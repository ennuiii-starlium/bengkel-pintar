"""Alur utama dari awal sampai akhir, hanya lewat API: login, diagnosis, draft, finalisasi, nota, laporan."""

from datetime import datetime, timezone

from sqlalchemy import text

from app.util import ke_wib
from tests.conftest import header, masuk


def test_alur_utama_bengkel(klien):
    # 1. server hidup dan kedua peran bisa masuk
    assert klien.get("/health").json() == {"status": "ok", "versi": "1.0"}
    admin = header(masuk(klien, "admin", "admin123").json()["access_token"])
    budi_masuk = masuk(klien, "budi", "budi123").json()
    assert budi_masuk["user"] == {"id": 2, "nama": "Budi Santoso", "peran": "mekanik"}
    budi = header(budi_masuk["access_token"])
    assert klien.get("/auth/me", headers=admin).json()["peran"] == "admin"

    # 2. admin menyiapkan produk dan jasa baru
    produk = klien.post("/produk", json={"nama": "Filter Oli", "kategori_id": 6, "harga": 30000, "stok": 10, "stok_minimum": 3}, headers=admin)
    jasa = klien.post("/jasa", json={"nama": "Ganti filter oli", "harga": 15000}, headers=admin)
    assert (produk.status_code, jasa.status_code) == (201, 201)
    produk_id, jasa_id = produk.json()["id"], jasa.json()["id"]

    # 3. mekanik mendiagnosis dan hasilnya tersimpan di riwayatnya
    hasil = klien.post("/diagnosis/predict", json={"gejala_ids": [1, 3, 4]}, headers=budi).json()
    assert hasil["kerusakan_utama"]["nama"] == "Busi kotor / aus"
    assert [r["id"] for r in klien.get("/diagnosis/riwayat", headers=budi).json()] == [hasil["riwayat_id"]]

    # 4. mekanik membuat draft dari hasil diagnosis lalu mengubahnya
    draft = klien.post(
        "/transaksi",
        json={"riwayat_diagnosis_id": hasil["riwayat_id"], "nama_pelanggan": "Dedi", "plat_nomor": "D 4321 YY",
              "items": [{"tipe": "produk", "id": produk_id, "jumlah": 2}, {"tipe": "jasa", "id": jasa_id, "jumlah": 1}]},
        headers=budi,
    )
    assert draft.status_code == 201
    draft = draft.json()
    assert draft["nomor"] == "TRX-0106" and draft["status"] == "draft" and draft["total"] == 2 * 30000 + 15000
    ubah = klien.put(
        f"/transaksi/{draft['id']}",
        json={"nama_pelanggan": "Dedi", "plat_nomor": "D 4321 YY",
              "items": [{"tipe": "produk", "id": produk_id, "jumlah": 3}, {"tipe": "jasa", "id": jasa_id, "jumlah": 1}]},
        headers=budi,
    )
    assert ubah.status_code == 200 and ubah.json()["total"] == 3 * 30000 + 15000
    total = ubah.json()["total"]

    # 5. stok belum berubah dan mekanik tidak boleh memfinalkan atau mencetak nota
    stok = {p["id"]: p["stok"] for p in klien.get("/produk", headers=admin).json()}
    assert stok[produk_id] == 10
    bayar = {"metode_bayar": "tunai", "jumlah_dibayar": total + 5000}
    assert klien.post(f"/transaksi/{draft['id']}/finalisasi", json=bayar, headers=budi).status_code == 403

    # 6. admin memfinalkan: stok terpotong, kembalian benar, mutasi tercatat
    final = klien.post(f"/transaksi/{draft['id']}/finalisasi", json=bayar, headers=admin)
    assert final.status_code == 200
    final = final.json()
    assert (final["status"], final["kembalian"], final["difinalkan_oleh"]) == ("final", 5000, "Andi Pratama")
    stok = {p["id"]: p["stok"] for p in klien.get("/produk", headers=admin).json()}
    assert stok[produk_id] == 7
    mutasi = klien.get(f"/produk/{produk_id}/mutasi", headers=admin).json()
    assert [(m["jumlah"], m["alasan"]) for m in mutasi] == [(-3, "Penjualan TRX-0106"), (10, "Stok awal")]

    # 7. transaksi final terkunci, nota hanya untuk admin
    ubah_final = klien.put(
        f"/transaksi/{draft['id']}",
        json={"nama_pelanggan": "X", "plat_nomor": "", "items": [{"tipe": "jasa", "id": jasa_id, "jumlah": 1}]},
        headers=admin,
    )
    assert ubah_final.status_code == 409 and ubah_final.json()["detail"] == "Transaksi final tidak bisa diubah."
    assert klien.get(f"/transaksi/{draft['id']}/nota", headers=budi).status_code == 403
    nota = klien.get(f"/transaksi/{draft['id']}/nota", headers=admin).json()
    assert nota["nomor"] == "TRX-0106" and nota["total"] == total and len(nota["items"]) == 2
    assert klien.get("/pengaturan-bengkel", headers=budi).json()["nama"] == "Bengkel Maju Jaya"

    # 8. laporan hari ini memuat transaksi tersebut
    with klien.mesin.connect() as c:
        waktu_final = c.execute(text("SELECT waktu_final FROM transaksi WHERE id = :i"), {"i": draft["id"]}).scalar()
    hari = ke_wib(waktu_final).date().isoformat()
    assert abs((datetime.now(timezone.utc) - waktu_final).total_seconds()) < 120
    laporan = klien.get("/laporan/penjualan", params={"periode_mulai": hari, "periode_selesai": hari}, headers=admin).json()
    assert (laporan["total_penjualan"], laporan["jumlah_transaksi"], laporan["rata_rata"]) == (total, 1, total)
    assert laporan["penjualan_per_hari"] == [{"tanggal": hari, "total": total, "jumlah": 1}]
    terlaris = {(t["tipe"], t["id"]): (t["jumlah"], t["total"]) for t in laporan["terlaris"]}
    assert terlaris == {("produk", produk_id): (3, 90000), ("jasa", jasa_id): (1, 15000)}

    # 9. statistik diagnosis dan pembukuan stok tetap konsisten
    stat = klien.get("/diagnosis/statistik", headers=admin).json()
    assert stat["total"] == 1 and stat["items"][0]["nama"] == "Busi kotor / aus"
    with klien.mesin.connect() as c:
        selisih = c.execute(text(
            "SELECT p.id FROM produk p LEFT JOIN mutasi_stok m ON m.produk_id = p.id "
            "GROUP BY p.id, p.stok HAVING p.stok <> COALESCE(SUM(m.jumlah), 0)")).all()
    assert selisih == []
