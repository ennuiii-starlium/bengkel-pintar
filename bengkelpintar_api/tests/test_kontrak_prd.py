"""Bentuk respons API harus memuat semua field yang ada pada contoh di docs/PRD.md bagian 9.

Yang dibandingkan adalah nama field dan jenis nilainya (teks, angka, true/false, daftar, objek),
bukan isinya. Field tambahan pada respons API diizinkan. Nilai null pada contoh PRD berarti
'bebas'. Tes dilewati bila docs/PRD.md tidak ditemukan.
"""

import json
import re
from pathlib import Path

import pytest

from tests.conftest import header, masuk, token_bawaan

PRD = Path(__file__).resolve().parents[2] / "docs" / "PRD.md"


def contoh_prd() -> dict:
    if not PRD.is_file():
        pytest.skip(f"docs/PRD.md tidak ditemukan di {PRD}")
    teks = PRD.read_text(encoding="utf-8")
    bagian = teks[teks.index("## 9. Kontrak API") : teks.index("## 10.")]
    sub = {s.splitlines()[0][:7]: s for s in re.split(r"\n(?=### 9\.)", bagian)[1:]}
    blok = {k: [json.loads(b) for b in re.findall(r"```json\n(.*?)```", v, re.S)] for k, v in sub.items()}
    tambahan = blok["### 9.5"]

    def cari(kunci):
        return next(b for b in tambahan if isinstance(b, dict) and set(b) == kunci)

    return {
        "login": blok["### 9.2"][1],
        "diagnosis": blok["### 9.3"][1],
        "draft": blok["### 9.4"][1],
        "health": cari({"status", "versi"}),
        "ganti_password": cari({"pesan"}),
        "pengaturan": cari({"nama", "alamat", "telepon"}),
        "stok": cari({"stok_baru"}),
    }


def jenis(nilai):
    if nilai is None:
        return None
    if isinstance(nilai, bool):
        return "true/false"
    if isinstance(nilai, (int, float)):
        return "angka"
    return {str: "teks", list: "daftar", dict: "objek"}[type(nilai)]


def cocokkan(contoh, nyata, jalur="$"):
    if contoh is None:
        return
    assert jenis(contoh) == jenis(nyata), f"{jalur}: PRD {jenis(contoh)}, API {jenis(nyata)}"
    if isinstance(contoh, dict):
        for kunci, nilai in contoh.items():
            assert kunci in nyata, f"{jalur}.{kunci} ada di PRD tetapi tidak ada di respons API"
            cocokkan(nilai, nyata[kunci], f"{jalur}.{kunci}")
    elif isinstance(contoh, list) and contoh:
        assert nyata, f"{jalur}: PRD memberi contoh daftar berisi, API mengembalikan daftar kosong"
        for i, elemen in enumerate(nyata):
            cocokkan(contoh[0], elemen, f"{jalur}[{i}]")


def test_penguji_kontrak_sendiri_memang_bisa_gagal():
    cocokkan({"a": 1, "b": [{"c": "x"}]}, {"a": 5, "b": [{"c": "y", "d": 1}], "e": 2})
    with pytest.raises(AssertionError, match=r"\$\.b\[0\]\.c ada di PRD"):
        cocokkan({"b": [{"c": "x"}]}, {"b": [{"z": "y"}]})
    with pytest.raises(AssertionError, match="PRD angka, API teks"):
        cocokkan({"a": 1}, {"a": "1"})
    with pytest.raises(AssertionError, match="daftar kosong"):
        cocokkan({"b": [1]}, {"b": []})


def test_login_cocok_prd(klien):
    cocokkan(contoh_prd()["login"], masuk(klien, "budi", "budi123").json())


def test_health_cocok_prd(klien):
    cocokkan(contoh_prd()["health"], klien.get("/health").json())


def test_diagnosis_cocok_prd(klien):
    contoh = contoh_prd()["diagnosis"]
    res = klien.post("/diagnosis/predict", json={"gejala_ids": [1, 3, 4]}, headers=header(token_bawaan(klien, "budi")))
    assert res.status_code == 200
    cocokkan(contoh, res.json())


def test_draft_transaksi_cocok_prd(klien):
    contoh = contoh_prd()["draft"]
    res = klien.post(
        "/transaksi",
        json={"riwayat_diagnosis_id": None, "nama_pelanggan": "", "plat_nomor": "", "items": [{"tipe": "produk", "id": 1, "jumlah": 1}, {"tipe": "jasa", "id": 1, "jumlah": 1}]},
        headers=header(token_bawaan(klien, "budi")),
    )
    assert res.status_code == 201
    cocokkan(contoh, res.json())


def test_endpoint_tambahan_cocok_prd(klien):
    contoh = contoh_prd()
    admin = header(token_bawaan(klien, "admin"))
    cocokkan(contoh["pengaturan"], klien.get("/pengaturan-bengkel", headers=admin).json())
    cocokkan(contoh["stok"], klien.post("/produk/1/stok", json={"jumlah": 10, "alasan": "Barang masuk"}, headers=admin).json())
    res = klien.post("/auth/ganti-password", json={"password_lama": "admin123", "password_baru": "sandibaru1"}, headers=admin)
    cocokkan(contoh["ganti_password"], res.json())
