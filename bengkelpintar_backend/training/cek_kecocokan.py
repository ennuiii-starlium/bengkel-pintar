r"""Membandingkan kode gejala dan kerusakan di model_meta.json dengan data master di database.

Penyaring awal, bukan hakim akhir: kode yang sama dengan nama yang mirip dianggap MIRIP,
sisanya ditandai untuk ditinjau manusia. Kode yang sama dengan arti berbeda adalah risiko
terbesar, karena API akan menafsirkan gejala secara salah tanpa pesan error.

Cara memakai (dari folder bengkelpintar_backend), dengan dua berkas JSON hasil API:
    curl -H "Authorization: Bearer <token>" -H "X-API-Key: <kunci>" http://localhost:8000/gejala    > gejala_db.json
    curl -H "Authorization: Bearer <token>" -H "X-API-Key: <kunci>" http://localhost:8000/kerusakan > kerusakan_db.json
    python training\cek_kecocokan.py --meta models_pengembangan\model_meta.json ^
        --gejala-json gejala_db.json --kerusakan-json kerusakan_db.json

Kode keluar 0 bila semuanya cocok, 1 bila ada yang tidak cocok.
"""

import argparse
import csv
import difflib
import json
import re
import sys
from pathlib import Path

AMBANG_MIRIP = 0.75
STATUS_BAIK = "MIRIP"


def normal(kode: str) -> str:
    """K1 dan K01 dianggap kode yang sama secara numerik."""
    m = re.match(r"^([A-Za-z]+)0*(\d+)$", kode.strip())
    return f"{m.group(1).upper()}{int(m.group(2))}" if m else kode.strip().upper()


def kemiripan(a: str, b: str):
    x, y = " ".join(a.lower().split()), " ".join(b.lower().split())
    rasio = difflib.SequenceMatcher(None, x, y).ratio()
    return rasio, (x in y or y in x)


def bandingkan_jenis(jenis, kode_model, nama_model, daftar_db):
    db = {normal(r["kode"]): r for r in daftar_db}
    baris, terpakai = [], set()
    for kode in kode_model:
        kunci = normal(kode)
        nama = nama_model.get(kode, "")
        rec = db.get(kunci)
        if rec is None:
            baris.append([jenis, kode, nama, "", "", "", "HANYA_DI_MODEL"])
            continue
        terpakai.add(kunci)
        rasio, memuat = kemiripan(nama, rec["nama"]) if nama else (0.0, False)
        status = STATUS_BAIK if (rasio >= AMBANG_MIRIP or memuat) else "BERBEDA"
        if kode != rec["kode"]:
            status += "+FORMAT_KODE_BEDA"
        baris.append([jenis, kode, nama, rec["kode"], rec["nama"], f"{rasio:.2f}", status])
    for kunci, rec in db.items():
        if kunci not in terpakai:
            baris.append([jenis, "", "", rec["kode"], rec["nama"], "", "HANYA_DI_DATABASE"])
    return baris


def bandingkan(meta: dict, gejala_db: list, kerusakan_db: list) -> dict:
    baris = bandingkan_jenis("gejala", meta["kode_gejala"], meta.get("nama_gejala", {}), gejala_db)
    baris += bandingkan_jenis("kerusakan", meta["kode_kelas"], meta.get("nama_kelas", {}), kerusakan_db)
    ringkas = {}
    for r in baris:
        ringkas.setdefault(r[0], {}).setdefault(r[6], 0)
        ringkas[r[0]][r[6]] += 1
    cocok = all(r[6] == STATUS_BAIK for r in baris)
    return {"cocok": cocok, "baris": baris, "ringkasan": ringkas}


def tulis_hasil(folder: Path, hasil: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    judul = ["jenis", "kode_model", "nama_model", "kode_database", "nama_database", "kemiripan_nama", "status"]
    with open(folder / "kecocokan_database.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(judul)
        w.writerows(hasil["baris"])
    teks = ["# Kecocokan model dengan database", ""]
    teks.append("**HASIL: " + ("COCOK" if hasil["cocok"] else "TIDAK COCOK. Model ini tidak boleh dipasang ke API.") + "**")
    teks += ["", "Alat ini penyaring awal; nama yang tampak berbeda perlu ditinjau manusia.", "", "## Ringkasan", ""]
    for jenis, hitung in hasil["ringkasan"].items():
        teks.append(f"- {jenis}: " + ", ".join(f"{s} = {n}" for s, n in sorted(hitung.items())))
    teks += ["", "## Rincian", "", "| Jenis | Kode model | Nama di model | Kode DB | Nama di database | Mirip | Status |", "|---|---|---|---|---|---:|---|"]
    for r in hasil["baris"]:
        teks.append("| " + " | ".join(str(c) for c in r) + " |")
    teks += [
        "",
        "Arti status: MIRIP = kode dan nama sepadan; BERBEDA = kode sama tetapi nama jauh berbeda (risiko salah tafsir); "
        "FORMAT_KODE_BEDA = angka sama tetapi penulisan berbeda (K1 vs K01); HANYA_DI_MODEL / HANYA_DI_DATABASE = tidak ada pasangan.",
        "",
    ]
    (folder / "kecocokan_database.md").write_text("\n".join(teks), encoding="utf-8")


def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Cek kecocokan model_meta.json dengan data master database.")
    ap.add_argument("--meta", required=True)
    ap.add_argument("--gejala-json", required=True, help="hasil GET /gejala")
    ap.add_argument("--kerusakan-json", required=True, help="hasil GET /kerusakan")
    ap.add_argument("--hasil", default=str(Path(__file__).resolve().parent / "hasil"))
    a = ap.parse_args(argv)
    try:
        meta = json.loads(Path(a.meta).read_text(encoding="utf-8"))
        gejala = json.loads(Path(a.gejala_json).read_text(encoding="utf-8-sig"))
        kerusakan = json.loads(Path(a.kerusakan_json).read_text(encoding="utf-8-sig"))
        for nama, isi in (("gejala", gejala), ("kerusakan", kerusakan)):
            if not isinstance(isi, list) or not all("kode" in r and "nama" in r for r in isi):
                raise ValueError(f"Berkas {nama} harus berupa daftar objek dengan 'kode' dan 'nama' (hasil API).")
    except (OSError, ValueError, KeyError) as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 2
    hasil = bandingkan(meta, gejala, kerusakan)
    tulis_hasil(Path(a.hasil), hasil)
    for jenis, hitung in hasil["ringkasan"].items():
        print(f"{jenis}: " + ", ".join(f"{s}={n}" for s, n in sorted(hitung.items())))
    print("HASIL:", "COCOK" if hasil["cocok"] else "TIDAK COCOK")
    return 0 if hasil["cocok"] else 1


if __name__ == "__main__":
    sys.exit(jalankan())
