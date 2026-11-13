r"""Pelatihan Random Forest untuk diagnosis kerusakan motor (B-10).

Jalankan dari folder bengkelpintar_backend:

    python training\train_model.py

Keluaran:
    models_pengembangan\rf_model.pkl, model_meta.json   (model dan metadatanya)
    training\hasil\laporan_evaluasi.md, metrik.json, confusion_matrix.csv, ...

Aturan yang dijaga skrip ini:
- Tidak ada angka yang dikarang: semua metrik dihitung dari data uji hasil pembagian berstrata.
- Baris duplikat (gejala sama, label sama) dibuang sebelum dibagi, supaya baris yang identik
  tidak berada di data latih dan data uji sekaligus.
- Data uji tidak dipakai untuk memilih parameter. Pencarian parameter (opsional) hanya
  memakai data latih.
- Kalau data bertanda SINTETIS, laporan dan metadata diberi peringatan, dan skrip menolak
  menyimpan hasilnya ke folder "models" (folder yang dibaca API) kecuali dipaksa.
"""

import argparse
import csv
import hashlib
import json
import math
import platform
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import confusion_matrix, precision_recall_fscore_support
from sklearn.model_selection import GridSearchCV, StratifiedKFold, cross_validate, train_test_split

AKAR = Path(__file__).resolve().parent.parent
RANDOM_STATE = 42
POLA_GEJALA = re.compile(r"^[Gg]\d+$")
KOLOM_LABEL_UMUM = ("kerusakan", "kelas")
PARAMETER_BAWAAN = {
    "n_estimators": 300,
    "max_depth": None,
    "min_samples_leaf": 1,
    "max_features": "sqrt",
    "class_weight": None,
}
GRID_PARAMETER = {
    "n_estimators": [200, 400],
    "max_depth": [None, 10, 20],
    "min_samples_leaf": [1, 2, 4],
}
BANNER_SINTETIS = (
    "PERINGATAN: DATA SINTETIS. Dataset ini dibuat dari artikel web dan sampel acak, bukan dari kasus "
    "bengkel sungguhan, dan labelnya belum divalidasi mekanik. Angka di bawah hanya mengukur seberapa "
    "baik model menebak ulang data buatan itu. JANGAN dilaporkan sebagai kemampuan mendiagnosis motor "
    "sungguhan."
)


class DataTidakValid(Exception):
    """Dataset tidak memenuhi syarat untuk dilatih."""


@dataclass
class Dataset:
    kode_gejala: list
    X: np.ndarray
    y: np.ndarray
    id_kasus: list
    sumber_data: Counter
    status_verifikasi: Counter
    kolom_label: str
    peringatan: list = field(default_factory=list)
    baris_awal: int = 0

    @property
    def jumlah(self) -> int:
        return len(self.y)

    @property
    def data_sintetis(self):
        """True bila ada baris bertanda sintetis, False bila ada catatan asal dan tidak ada yang sintetis,
        None bila asal data tidak dicatat."""
        if not self.sumber_data:
            return None
        return any("SINTETIS" in asal.upper() for asal in self.sumber_data)


# ------------------------------------------------------------------ membaca data
def baca_dataset(path, kolom_label=None) -> Dataset:
    path = Path(path)
    if not path.is_file():
        raise DataTidakValid(f"Berkas dataset tidak ditemukan: {path}")
    with path.open(encoding="utf-8-sig", newline="") as f:
        pembaca = csv.reader(f)
        header = [h.strip() for h in next(pembaca, [])]
        baris_mentah = [(no, r) for no, r in enumerate(pembaca, start=2) if any(c.strip() for c in r)]
    if not header:
        raise DataTidakValid("Berkas dataset kosong.")

    huruf_kecil = [h.lower() for h in header]
    if kolom_label:
        if kolom_label.lower() not in huruf_kecil:
            raise DataTidakValid(f"Kolom label '{kolom_label}' tidak ada. Kolom yang ada: {header}")
        idx_label = huruf_kecil.index(kolom_label.lower())
    else:
        kandidat = [huruf_kecil.index(k) for k in KOLOM_LABEL_UMUM if k in huruf_kecil]
        if not kandidat:
            raise DataTidakValid(f"Kolom label tidak ditemukan. Harus bernama salah satu dari {KOLOM_LABEL_UMUM}.")
        idx_label = kandidat[0]

    idx_gejala = [i for i, h in enumerate(header) if POLA_GEJALA.match(h)]
    kode_gejala = [header[i].upper() for i in idx_gejala]
    if len(kode_gejala) < 2:
        raise DataTidakValid("Dataset harus punya minimal 2 kolom gejala bernama seperti G01, G02, dan seterusnya.")
    ganda = [k for k, n in Counter(kode_gejala).items() if n > 1]
    if ganda:
        raise DataTidakValid(f"Kolom gejala ganda: {ganda}")

    def indeks_opsional(*nama):
        for n in nama:
            if n in huruf_kecil:
                return huruf_kecil.index(n)
        return None

    idx_id = indeks_opsional("id_kasus", "id")
    idx_sumber = indeks_opsional("sumber_data")
    idx_status = indeks_opsional("status_verifikasi")

    kolom_dibutuhkan = max(idx_gejala + [idx_label]) + 1
    masalah, X, y, ids, sumber, status, peringatan = [], [], [], [], Counter(), Counter(), []
    nol_semua = []
    for no, r in baris_mentah:
        if len(r) < kolom_dibutuhkan:
            masalah.append(f"baris {no}: jumlah kolom kurang ({len(r)} dari {kolom_dibutuhkan})")
            continue
        label = r[idx_label].strip()
        if not label:
            masalah.append(f"baris {no}: label kosong")
            continue
        vektor, salah = [], False
        for i, kode in zip(idx_gejala, kode_gejala):
            nilai = r[i].strip()
            if nilai not in ("0", "1"):
                masalah.append(f"baris {no}, kolom {kode}: nilai '{nilai}' (harus 0 atau 1)")
                salah = True
                break
            vektor.append(int(nilai))
        if salah:
            continue
        id_baris = r[idx_id].strip() if idx_id is not None and idx_id < len(r) else f"baris{no}"
        if not any(vektor):
            nol_semua.append(id_baris)
            continue
        X.append(vektor)
        y.append(label)
        ids.append(id_baris)
        if idx_sumber is not None and idx_sumber < len(r):
            sumber[r[idx_sumber].strip() or "(kosong)"] += 1
        if idx_status is not None and idx_status < len(r):
            status[r[idx_status].strip() or "(kosong)"] += 1

    if masalah:
        contoh = "\n".join(f"  - {m}" for m in masalah[:5])
        sisa = f"\n  ... dan {len(masalah) - 5} masalah lain" if len(masalah) > 5 else ""
        raise DataTidakValid(f"Dataset mengandung {len(masalah)} masalah:\n{contoh}{sisa}")
    if nol_semua:
        peringatan.append(
            f"{len(nol_semua)} baris tanpa satu pun gejala aktif dibuang (contoh: {', '.join(nol_semua[:3])})."
        )
    if len(set(y)) < 2:
        raise DataTidakValid("Dataset harus memuat minimal 2 kelas kerusakan.")

    return Dataset(
        kode_gejala=kode_gejala,
        X=np.array(X, dtype=np.int8),
        y=np.array(y, dtype=str),
        id_kasus=ids,
        sumber_data=sumber,
        status_verifikasi=status,
        kolom_label=header[idx_label],
        peringatan=peringatan,
        baris_awal=len(baris_mentah),
    )


def baca_daftar(path):
    """Membaca daftar kode,nama (dua kolom pertama, baris pertama adalah judul)."""
    path = Path(path)
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as f:
        pembaca = csv.reader(f)
        next(pembaca, None)
        return {r[0].strip().upper(): r[1].strip() for r in pembaca if len(r) >= 2 and r[0].strip()}


def sha256_berkas(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for blok in iter(lambda: f.read(65536), b""):
            h.update(blok)
    return h.hexdigest()


# ------------------------------------------------------------------ pembersihan
def hapus_duplikat(d: Dataset):
    """Membuang baris dengan gejala dan label yang sama persis. Vektor yang sama dengan label
    berbeda dipertahankan (itu ketidakpastian nyata) tetapi dihitung dan dilaporkan."""
    terlihat, simpan, label_per_vektor = set(), [], {}
    for i in range(d.jumlah):
        vektor = d.X[i].tobytes()
        label_per_vektor.setdefault(vektor, set()).add(d.y[i])
        kunci = (vektor, str(d.y[i]))
        if kunci in terlihat:
            continue
        terlihat.add(kunci)
        simpan.append(i)
    lintas = sum(1 for s in label_per_vektor.values() if len(s) > 1)
    info = {"duplikat_dibuang": d.jumlah - len(simpan), "vektor_lintas_kelas": lintas}
    bersih = Dataset(
        kode_gejala=d.kode_gejala,
        X=d.X[simpan],
        y=d.y[simpan],
        id_kasus=[d.id_kasus[i] for i in simpan],
        sumber_data=d.sumber_data,
        status_verifikasi=d.status_verifikasi,
        kolom_label=d.kolom_label,
        peringatan=list(d.peringatan),
        baris_awal=d.baris_awal,
    )
    return bersih, info


# ----------------------------------------------------------- pembagian dan model
def bagi_data(y, porsi_uji, seed):
    indeks = np.arange(len(y))
    try:
        latih, uji = train_test_split(indeks, test_size=porsi_uji, stratify=y, random_state=seed)
    except ValueError as e:
        raise DataTidakValid(
            "Data tidak bisa dibagi berstrata. Biasanya ada kelas dengan sampel terlalu sedikit "
            f"atau porsi uji terlalu kecil untuk jumlah kelas. Detail: {e}"
        )
    return np.sort(latih), np.sort(uji)


def buat_model(params, seed):
    return RandomForestClassifier(**params, random_state=seed, n_jobs=1)


def lipatan_aman(y, diminta):
    return max(2, min(diminta, min(Counter(y).values())))


def latih(X, y, seed, cari_parameter=False, lipatan=5):
    info = None
    if cari_parameter:
        k = lipatan_aman(y, lipatan)
        pencarian = GridSearchCV(
            buat_model(PARAMETER_BAWAAN, seed),
            GRID_PARAMETER,
            cv=StratifiedKFold(k, shuffle=True, random_state=seed),
            scoring="f1_macro",
            n_jobs=1,
        )
        pencarian.fit(X, y)
        params = {**PARAMETER_BAWAAN, **pencarian.best_params_}
        urut = np.argsort(pencarian.cv_results_["rank_test_score"])[:5]
        info = {
            "lipatan": k,
            "kriteria": "f1_macro (hanya pada data latih)",
            "lima_terbaik": [
                {"parameter": pencarian.cv_results_["params"][i], "f1_macro_rata2": float(pencarian.cv_results_["mean_test_score"][i])}
                for i in urut
            ],
        }
        return pencarian.best_estimator_, params, info
    model = buat_model(PARAMETER_BAWAAN, seed).fit(X, y)
    return model, dict(PARAMETER_BAWAAN), info


def wilson(p, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    penyebut = 1 + z * z / n
    pusat = (p + z * z / (2 * n)) / penyebut
    lebar = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / penyebut
    return (max(0.0, pusat - lebar), min(1.0, pusat + lebar))


def evaluasi(model, X_uji, y_uji, y_latih):
    kelas = [str(k) for k in model.classes_]
    prediksi = model.predict(X_uji)
    peluang = model.predict_proba(X_uji)
    n = len(y_uji)
    akurasi = float(np.mean(prediksi == y_uji))
    k = min(3, len(kelas))
    urut = np.argsort(-peluang, axis=1, kind="stable")[:, :k]
    top_k = float(np.mean([y_uji[i] in {kelas[j] for j in urut[i]} for i in range(n)]))
    p, r, f, s = precision_recall_fscore_support(y_uji, prediksi, labels=kelas, zero_division=0)
    makro = precision_recall_fscore_support(y_uji, prediksi, labels=kelas, average="macro", zero_division=0)[:3]
    berbobot = precision_recall_fscore_support(y_uji, prediksi, labels=kelas, average="weighted", zero_division=0)[:3]
    cm = confusion_matrix(y_uji, prediksi, labels=kelas)
    mayoritas = Counter(y_latih).most_common(1)[0][0]
    batas = wilson(akurasi, n)
    return {
        "jumlah_uji": n,
        "akurasi": akurasi,
        "akurasi_selang_95": [batas[0], batas[1]],
        "akurasi_top_k": top_k,
        "k_top": k,
        "baseline_kelas_mayoritas": float(np.mean(y_uji == mayoritas)),
        "baseline_acak": 1 / len(kelas),
        "makro": {"precision": float(makro[0]), "recall": float(makro[1]), "f1": float(makro[2])},
        "berbobot": {"precision": float(berbobot[0]), "recall": float(berbobot[1]), "f1": float(berbobot[2])},
        "per_kelas": [
            {"kelas": kelas[i], "precision": float(p[i]), "recall": float(r[i]), "f1": float(f[i]), "support": int(s[i])}
            for i in range(len(kelas))
        ],
        "kelas": kelas,
        "confusion_matrix": cm.tolist(),
    }


def validasi_silang(X, y, params, seed, lipatan=5):
    k = lipatan_aman(y, lipatan)
    hasil = cross_validate(
        buat_model(params, seed),
        X,
        y,
        cv=StratifiedKFold(k, shuffle=True, random_state=seed),
        scoring=["accuracy", "f1_macro"],
        n_jobs=1,
    )
    return {
        "lipatan": k,
        "akurasi_rata2": float(hasil["test_accuracy"].mean()),
        "akurasi_simpangan": float(hasil["test_accuracy"].std()),
        "f1_makro_rata2": float(hasil["test_f1_macro"].mean()),
        "f1_makro_simpangan": float(hasil["test_f1_macro"].std()),
    }


def pasangan_tertukar(metrik, jumlah=5):
    kelas, cm = metrik["kelas"], metrik["confusion_matrix"]
    pasangan = [
        (cm[i][j], kelas[i], kelas[j])
        for i in range(len(kelas))
        for j in range(len(kelas))
        if i != j and cm[i][j] > 0
    ]
    return sorted(pasangan, key=lambda x: (-x[0], x[1], x[2]))[:jumlah]


# ---------------------------------------------------------------------- laporan
def _persen(x):
    return f"{x * 100:.1f}%"


def tulis_laporan(path, ctx):
    d, m, cv = ctx["data"], ctx["metrik"], ctx["silang"]
    nama_kelas, nama_gejala = ctx["nama_kelas"], ctx["nama_gejala"]
    baris = ["# Laporan Evaluasi Model Random Forest", ""]
    if d.data_sintetis:
        baris += [f"> **{BANNER_SINTETIS}**", ""]
    elif d.data_sintetis is None:
        baris += ["> Asal data tidak tercatat di dataset (tidak ada kolom `sumber_data`). Cantumkan asal data di skripsi.", ""]
    if d.status_verifikasi and "belum_diverifikasi" in d.status_verifikasi:
        baris += [
            f"> Label belum divalidasi mekanik pada {d.status_verifikasi['belum_diverifikasi']} dari {sum(d.status_verifikasi.values())} baris.",
            "",
        ]
    for p in ctx["peringatan"]:
        baris.append(f"- Peringatan: {p}")
    if ctx["peringatan"]:
        baris.append("")

    baris += ["## 1. Data", ""]
    baris += [
        f"- Berkas: `{ctx['dataset']['berkas']}` (SHA-256 `{ctx['dataset']['sha256'][:16]}...`)",
        f"- Baris dibaca: {d.baris_awal}; setelah membuang duplikat gejala+label: {d.jumlah} "
        f"({ctx['bersih']['duplikat_dibuang']} dibuang)",
        f"- Vektor gejala yang sama tetapi berlabel berbeda: {ctx['bersih']['vektor_lintas_kelas']} (dipertahankan)",
        f"- Jumlah gejala (fitur): {len(d.kode_gejala)}; jumlah kelas: {len(m['kelas'])}",
    ]
    if d.sumber_data:
        baris.append(f"- `sumber_data`: {dict(d.sumber_data)}")
    if d.status_verifikasi:
        baris.append(f"- `status_verifikasi`: {dict(d.status_verifikasi)}")
    sebaran = Counter(d.y)
    rasio = max(sebaran.values()) / min(sebaran.values())
    baris += ["", "### Distribusi kelas", "", "| Kelas | Nama | Jumlah | Persen |", "|---|---|---:|---:|"]
    for k in sorted(sebaran):
        baris.append(f"| {k} | {nama_kelas.get(k.upper(), '-')} | {sebaran[k]} | {_persen(sebaran[k] / d.jumlah)} |")
    baris += ["", f"Rasio kelas terbanyak terhadap tersedikit: {rasio:.2f}.", ""]

    baris += ["## 2. Pengaturan", ""]
    baris += [
        f"- Pembagian: {ctx['jumlah_latih']} latih / {m['jumlah_uji']} uji (berstrata, random_state={ctx['seed']}).",
        f"- Parameter: `{json.dumps(ctx['parameter'], ensure_ascii=False)}`",
    ]
    if ctx["pencarian"]:
        baris.append(
            f"- Parameter dipilih dengan {ctx['pencarian']['lipatan']}-fold CV pada data latih saja; data uji tidak dipakai memilih."
        )
    else:
        baris.append("- Parameter bawaan, tanpa penyetelan.")

    lo, hi = m["akurasi_selang_95"]
    baris += ["", "## 3. Hasil pada data uji", ""]
    baris += [
        f"- Akurasi: **{_persen(m['akurasi'])}** (selang 95% kira-kira {_persen(lo)} sampai {_persen(hi)}, dari {m['jumlah_uji']} baris uji)",
        f"- Akurasi top-{m['k_top']} (kelas benar ada di {m['k_top']} peringkat teratas): {_persen(m['akurasi_top_k'])}",
        f"- Pembanding: selalu menebak kelas mayoritas {_persen(m['baseline_kelas_mayoritas'])}; menebak acak {_persen(m['baseline_acak'])}",
        f"- Makro: precision {m['makro']['precision']:.3f}, recall {m['makro']['recall']:.3f}, F1 {m['makro']['f1']:.3f}",
        f"- Berbobot: precision {m['berbobot']['precision']:.3f}, recall {m['berbobot']['recall']:.3f}, F1 {m['berbobot']['f1']:.3f}",
        "",
        "| Kelas | Nama | Precision | Recall | F1 | Jumlah uji |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for r in m["per_kelas"]:
        baris.append(
            f"| {r['kelas']} | {nama_kelas.get(r['kelas'].upper(), '-')} | {r['precision']:.3f} | {r['recall']:.3f} | {r['f1']:.3f} | {r['support']} |"
        )

    baris += ["", "### Confusion matrix (baris = kelas sebenarnya, kolom = prediksi)", ""]
    baris.append("| | " + " | ".join(m["kelas"]) + " |")
    baris.append("|---|" + "---:|" * len(m["kelas"]))
    for nama, isi in zip(m["kelas"], m["confusion_matrix"]):
        baris.append(f"| **{nama}** | " + " | ".join(str(v) for v in isi) + " |")
    tertukar = pasangan_tertukar(m)
    if tertukar:
        baris += ["", "Pasangan yang paling sering tertukar (sebenarnya -> diprediksi):", ""]
        for jml, a, b in tertukar:
            baris.append(f"- {a} -> {b}: {jml} kali")

    baris += ["", "## 4. Validasi silang (gambaran kestabilan)", ""]
    baris += [
        f"- {cv['lipatan']}-fold berstrata pada seluruh data setelah dibersihkan, parameter yang sama:",
        f"  akurasi {_persen(cv['akurasi_rata2'])} +- {_persen(cv['akurasi_simpangan'])}, "
        f"F1 makro {cv['f1_makro_rata2']:.3f} +- {cv['f1_makro_simpangan']:.3f}",
        "- Ini gambaran kestabilan, bukan pengganti data uji. Jika parameter disetel, angka ini sedikit optimistis.",
        "",
        "## 5. Gejala paling berpengaruh",
        "",
        "| Gejala | Uraian | Kepentingan |",
        "|---|---|---:|",
    ]
    for kode, nilai in ctx["penting"][:10]:
        baris.append(f"| {kode} | {nama_gejala.get(kode, '-')} | {nilai:.3f} |")

    baris += ["", "## 6. Cara membaca hasil ini", ""]
    baris += [
        "- Keyakinan model adalah probabilitas dari `predict_proba`, bukan jaminan kebenaran.",
        f"- Dengan {m['jumlah_uji']} baris uji, selisih satu baris sekitar {_persen(1 / m['jumlah_uji'])}. Hindari melaporkan akurasi dengan presisi berlebih.",
        "- Kepentingan gejala menunjukkan apa yang dipelajari model dari data ini, bukan bukti sebab-akibat teknis.",
    ]
    if d.data_sintetis:
        baris += [
            "- Karena data sintetis, kelas yang sering tertukar mencerminkan tumpang tindih profil gejala buatan, bukan kebingungan diagnosis di lapangan.",
            "- Untuk klaim yang bisa dipertanggungjawabkan, uji model dengan kasus nyata yang labelnya divalidasi mekanik.",
        ]

    baris += ["", "## 7. Reproduksi", ""]
    v = ctx["versi"]
    baris += [
        f"- Python {v['python']}, scikit-learn {v['scikit-learn']}, numpy {v['numpy']}",
        "- Perintah: `python training\\train_model.py` dari folder `bengkelpintar_backend`.",
        f"- Dibuat: {ctx['dibuat']}",
        "",
    ]
    Path(path).write_text("\n".join(baris), encoding="utf-8")


def tulis_csv(path, judul, isi):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(judul)
        w.writerows(isi)


# ------------------------------------------------------------------------- utama
def jalankan(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Latih Random Forest untuk diagnosis kerusakan motor (B-10).")
    ap.add_argument("--dataset", default=str(AKAR / "dataset" / "dataset_v3_motor_injeksi.csv"))
    ap.add_argument("--daftar-gejala", default=None, help="CSV kode,uraian (opsional, untuk nama gejala)")
    ap.add_argument("--daftar-kelas", default=None, help="CSV kode,nama (opsional, untuk nama kerusakan)")
    ap.add_argument("--kolom-label", default=None)
    ap.add_argument("--keluaran", default=str(AKAR / "models_pengembangan"), help="folder rf_model.pkl dan model_meta.json")
    ap.add_argument("--hasil", default=str(AKAR / "training" / "hasil"), help="folder laporan evaluasi")
    ap.add_argument("--porsi-uji", type=float, default=0.2)
    ap.add_argument("--seed", type=int, default=RANDOM_STATE)
    ap.add_argument("--cari-parameter", action="store_true", help="setel parameter dengan CV pada data latih")
    ap.add_argument("--izinkan-sintetis", action="store_true", help="izinkan menyimpan model data sintetis ke folder 'models'")
    a = ap.parse_args(argv)

    folder_dataset = Path(a.dataset).resolve().parent
    daftar_gejala = Path(a.daftar_gejala) if a.daftar_gejala else folder_dataset / "daftar_gejala_v3.csv"
    daftar_kelas = Path(a.daftar_kelas) if a.daftar_kelas else folder_dataset / "daftar_kelas_v3.csv"

    try:
        data = baca_dataset(a.dataset, a.kolom_label)
        keluaran = Path(a.keluaran).resolve()
        if data.data_sintetis and keluaran.name.lower() == "models" and not a.izinkan_sintetis:
            raise DataTidakValid(
                "Dataset bertanda SINTETIS tidak boleh disimpan ke folder 'models' (folder yang dibaca API). "
                "Pakai folder lain, misalnya models_pengembangan, atau tambahkan --izinkan-sintetis bila Anda "
                "paham risikonya."
            )
        bersih, info_bersih = hapus_duplikat(data)
        latih_idx, uji_idx = bagi_data(bersih.y, a.porsi_uji, a.seed)
    except DataTidakValid as e:
        print(f"GAGAL: {e}", file=sys.stderr)
        return 2

    X_latih, y_latih = bersih.X[latih_idx], bersih.y[latih_idx]
    X_uji, y_uji = bersih.X[uji_idx], bersih.y[uji_idx]
    model, params, pencarian = latih(X_latih, y_latih, a.seed, a.cari_parameter)
    metrik = evaluasi(model, X_uji, y_uji, y_latih)
    silang = validasi_silang(bersih.X, bersih.y, params, a.seed)

    nama_gejala, nama_kelas = baca_daftar(daftar_gejala), baca_daftar(daftar_kelas)
    penting = sorted(zip(bersih.kode_gejala, model.feature_importances_.tolist()), key=lambda x: -x[1])
    peringatan = list(data.peringatan)
    kecil = {str(k): n for k, n in sorted(Counter(bersih.y).items()) if n < 30}
    if kecil:
        peringatan.append(f"Kelas dengan kurang dari 30 sampel: {kecil}. Hasil per kelas tidak stabil.")
    if data.data_sintetis:
        peringatan.insert(0, BANNER_SINTETIS)

    versi = {"python": platform.python_version(), "scikit-learn": sklearn.__version__, "numpy": np.__version__}
    dibuat = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = {
        "versi_meta": 1,
        "dibuat": dibuat,
        "kode_gejala": bersih.kode_gejala,
        "kode_kelas": [str(k) for k in model.classes_],
        "nama_gejala": {k: nama_gejala[k] for k in bersih.kode_gejala if k in nama_gejala},
        "nama_kelas": {str(k): nama_kelas[str(k).upper()] for k in model.classes_ if str(k).upper() in nama_kelas},
        "random_state": a.seed,
        "parameter": params,
        "jumlah_latih": int(len(y_latih)),
        "jumlah_uji": int(len(y_uji)),
        "versi_library": versi,
        "dataset": {
            "berkas": Path(a.dataset).name,
            "sha256": sha256_berkas(a.dataset),
            "baris_dibaca": data.baris_awal,
            "baris_setelah_bersih": bersih.jumlah,
            "sumber_data": dict(data.sumber_data),
            "status_verifikasi": dict(data.status_verifikasi),
            "data_sintetis": data.data_sintetis,
        },
        "metrik_uji": {
            "akurasi": metrik["akurasi"],
            "akurasi_top_k": metrik["akurasi_top_k"],
            "f1_makro": metrik["makro"]["f1"],
        },
        "peringatan": peringatan,
    }

    keluaran.mkdir(parents=True, exist_ok=True)
    hasil = Path(a.hasil)
    hasil.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, keluaran / "rf_model.pkl", compress=3)
    (keluaran / "model_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    # laporan memakai sebaran data yang sudah dibersihkan, tetapi mencatat jumlah baris awal
    data_laporan = Dataset(**{**data.__dict__, "X": bersih.X, "y": bersih.y, "id_kasus": bersih.id_kasus})
    ctx = {
        "data": data_laporan,
        "bersih": info_bersih,
        "metrik": metrik,
        "silang": silang,
        "nama_kelas": nama_kelas,
        "nama_gejala": nama_gejala,
        "peringatan": [p for p in peringatan if p != BANNER_SINTETIS],
        "dataset": {"berkas": Path(a.dataset).name, "sha256": meta["dataset"]["sha256"]},
        "jumlah_latih": int(len(y_latih)),
        "seed": a.seed,
        "parameter": params,
        "pencarian": pencarian,
        "penting": penting,
        "versi": versi,
        "dibuat": dibuat,
    }
    tulis_laporan(hasil / "laporan_evaluasi.md", ctx)
    (hasil / "metrik.json").write_text(
        json.dumps({"metrik_uji": metrik, "validasi_silang": silang, "pencarian_parameter": pencarian}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tulis_csv(hasil / "confusion_matrix.csv", ["sebenarnya\\prediksi"] + metrik["kelas"], [[k] + r for k, r in zip(metrik["kelas"], metrik["confusion_matrix"])])
    sebaran = Counter(bersih.y)
    tulis_csv(hasil / "distribusi_kelas.csv", ["kelas", "nama", "jumlah"], [[k, nama_kelas.get(k.upper(), ""), sebaran[k]] for k in sorted(sebaran)])
    tulis_csv(hasil / "pentingnya_gejala.csv", ["gejala", "uraian", "kepentingan"], [[k, nama_gejala.get(k, ""), f"{v:.6f}"] for k, v in penting])

    print(f"Selesai. Model: {keluaran / 'rf_model.pkl'}")
    print(f"Laporan: {hasil / 'laporan_evaluasi.md'}")
    if data.data_sintetis:
        print("PERINGATAN: data sintetis. Jangan laporkan angka ini sebagai performa pada motor sungguhan.")
    print(f"Akurasi uji {metrik['akurasi']:.3f} (n={metrik['jumlah_uji']}); top-{metrik['k_top']} {metrik['akurasi_top_k']:.3f}; F1 makro {metrik['makro']['f1']:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(jalankan())
