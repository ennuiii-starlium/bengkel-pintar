import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

import joblib
import numpy as np
import pytest
import sklearn

from training import train_model as t

BARIS_DATASET_ASLI = Path(t.AKAR) / "dataset" / "dataset_v3_motor_injeksi.csv"


def buat_csv(path, per_kelas=40, sumber="WEB_SINTETIS", seed=0, kolom_label="kelas", tanpa_sumber=False):
    """3 kelas dengan pola gejala yang jelas: A -> g1,g2; B -> g3,g4; C -> g5,g6, ditambah sedikit derau."""
    rng = np.random.default_rng(seed)
    pola = {"K1": [0, 1], "K2": [2, 3], "K3": [4, 5]}
    judul = ["id_kasus"] + [f"G0{i}" for i in range(1, 7)] + [kolom_label]
    if not tanpa_sumber:
        judul += ["sumber_data", "status_verifikasi"]
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(judul)
        n = 0
        for kelas, kolom in pola.items():
            for _ in range(per_kelas):
                v = [int(rng.random() < 0.3) for _ in range(6)]
                for k in kolom:
                    v[k] = int(rng.random() < 0.85)
                v[int(rng.integers(0, 6))] = 1
                n += 1
                baris = [f"W{n:03d}"] + v + [kelas]
                if not tanpa_sumber:
                    baris += [sumber, "belum_diverifikasi" if "SINTETIS" in sumber else "diverifikasi"]
                w.writerow(baris)
    return path


def tulis(path, baris, judul=("id_kasus", "G01", "G02", "kelas")):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(judul)
        w.writerows(baris)
    return path


def latih_di(tmp_path, *argumen, **kw):
    ds = buat_csv(tmp_path / "d.csv", **kw)
    keluaran, hasil = tmp_path / "keluar", tmp_path / "hasil"
    kode = t.jalankan(["--dataset", str(ds), "--keluaran", str(keluaran), "--hasil", str(hasil), *argumen])
    return kode, ds, keluaran, hasil


# ------------------------------------------------------------- membaca data
def test_baca_dataset_valid(tmp_path):
    d = t.baca_dataset(buat_csv(tmp_path / "d.csv"))
    assert d.X.shape == (120, 6) and d.kode_gejala == [f"G0{i}" for i in range(1, 7)]
    assert set(d.y) == {"K1", "K2", "K3"} and d.kolom_label == "kelas"
    assert d.sumber_data == {"WEB_SINTETIS": 120} and d.data_sintetis is True
    assert set(np.unique(d.X)) == {0, 1}


def test_status_asal_data(tmp_path):
    assert t.baca_dataset(buat_csv(tmp_path / "a.csv", sumber="BENGKEL_NYATA")).data_sintetis is False
    assert t.baca_dataset(buat_csv(tmp_path / "b.csv", tanpa_sumber=True)).data_sintetis is None


def test_kolom_label_bernama_kerusakan_dan_huruf_kecil_dinormalkan(tmp_path):
    p = tulis(tmp_path / "d.csv", [["1", 1, 0, "K1"], ["2", 0, 1, "K2"], ["3", 1, 1, "K1"]], ("id", "g01", "g02", "Kerusakan"))
    d = t.baca_dataset(p)
    assert d.kode_gejala == ["G01", "G02"] and d.kolom_label == "Kerusakan" and d.id_kasus == ["1", "2", "3"]


def test_berkas_dengan_bom_excel_terbaca(tmp_path):
    p = tmp_path / "d.csv"
    p.write_bytes(b"\xef\xbb\xbfG01,G02,kelas\n1,0,K1\n0,1,K2\n")
    assert t.baca_dataset(p).kode_gejala == ["G01", "G02"]


@pytest.mark.parametrize(
    "baris, pesan",
    [
        ([["1", 2, 0, "K1"], ["2", 0, 1, "K2"]], "'2'"),
        ([["1", "ya", 0, "K1"], ["2", 0, 1, "K2"]], "'ya'"),
        ([["1", "", 0, "K1"], ["2", 0, 1, "K2"]], "nilai ''"),
        ([["1", 1, 0, ""], ["2", 0, 1, "K2"]], "label kosong"),
        ([["1", 1, 0, "K1"], ["2", 0, 1, "K1"]], "minimal 2 kelas"),
    ],
)
def test_dataset_tidak_valid_ditolak_dengan_pesan_jelas(tmp_path, baris, pesan):
    with pytest.raises(t.DataTidakValid) as e:
        t.baca_dataset(tulis(tmp_path / "d.csv", baris))
    assert pesan in str(e.value)


def test_masalah_dilaporkan_beserta_nomor_baris_dan_jumlahnya(tmp_path):
    baris = [[str(i), 2, 0, "K1"] for i in range(8)] + [["x", 0, 1, "K2"]]
    with pytest.raises(t.DataTidakValid) as e:
        t.baca_dataset(tulis(tmp_path / "d.csv", baris))
    assert "8 masalah" in str(e.value) and "baris 2" in str(e.value) and "dan 3 masalah lain" in str(e.value)


def test_struktur_salah_ditolak(tmp_path):
    with pytest.raises(t.DataTidakValid, match="tidak ditemukan"):
        t.baca_dataset(tmp_path / "tidak_ada.csv")
    with pytest.raises(t.DataTidakValid, match="Kolom label"):
        t.baca_dataset(tulis(tmp_path / "a.csv", [[1, 0, "K1"]], ("G01", "G02", "jenis")))
    with pytest.raises(t.DataTidakValid, match="ganda"):
        t.baca_dataset(tulis(tmp_path / "b.csv", [[1, 0, "K1"]], ("G01", "g01", "kelas")))
    with pytest.raises(t.DataTidakValid, match="minimal 2 kolom gejala"):
        t.baca_dataset(tulis(tmp_path / "c.csv", [[1, "K1"]], ("G01", "kelas")))
    with pytest.raises(t.DataTidakValid, match="kolom kurang"):
        t.baca_dataset(tulis(tmp_path / "d.csv", [[1, 0], [1, 0, "K1"]], ("G01", "G02", "kelas")))
    (tmp_path / "e.csv").write_text("")
    with pytest.raises(t.DataTidakValid, match="kosong"):
        t.baca_dataset(tmp_path / "e.csv")


def test_baris_tanpa_gejala_dibuang_dengan_peringatan(tmp_path):
    p = tulis(tmp_path / "d.csv", [["a", 0, 0, "K1"], ["b", 1, 0, "K1"], ["c", 0, 1, "K2"]])
    d = t.baca_dataset(p)
    assert d.jumlah == 2 and any("tanpa satu pun gejala" in w and "a" in w for w in d.peringatan)


# ------------------------------------------------- pembersihan dan pembagian
def test_duplikat_sama_label_dibuang_tetapi_beda_label_dipertahankan(tmp_path):
    p = tulis(tmp_path / "d.csv", [["1", 1, 0, "K1"], ["2", 1, 0, "K1"], ["3", 1, 0, "K2"], ["4", 0, 1, "K2"]])
    bersih, info = t.hapus_duplikat(t.baca_dataset(p))
    assert bersih.jumlah == 3 and info == {"duplikat_dibuang": 1, "vektor_lintas_kelas": 1}
    assert bersih.id_kasus == ["1", "3", "4"]


def test_pembagian_berstrata_terpisah_dan_deterministik():
    y = np.array(["A"] * 50 + ["B"] * 30 + ["C"] * 20)
    latih, uji = t.bagi_data(y, 0.2, 42)
    assert len(set(latih) & set(uji)) == 0 and len(latih) + len(uji) == 100
    assert Counter(y[uji]) == {"A": 10, "B": 6, "C": 4}
    assert all(np.array_equal(a, b) for a, b in zip((latih, uji), t.bagi_data(y, 0.2, 42)))
    assert not np.array_equal(uji, t.bagi_data(y, 0.2, 7)[1])


def test_kelas_dengan_satu_sampel_tidak_bisa_dibagi():
    with pytest.raises(t.DataTidakValid, match="berstrata"):
        t.bagi_data(np.array(["A"] * 10 + ["B"]), 0.2, 42)


def test_tidak_ada_baris_identik_di_latih_dan_uji(tmp_path):
    rng = np.random.default_rng(1)
    baris = []
    for i in range(300):  # banyak duplikat sengaja: hanya 4 pola per kelas
        kelas = "K1" if i % 2 else "K2"
        pola = int(rng.integers(0, 4))
        v = [1, 0, 0, 1] if kelas == "K1" else [0, 1, 1, 0]
        v[pola % 4] = 1
        baris.append([f"W{i}", *v, kelas])
    p = tulis(tmp_path / "d.csv", baris, ("id_kasus", "G01", "G02", "G03", "G04", "kelas"))
    bersih, _ = t.hapus_duplikat(t.baca_dataset(p))
    latih, uji = t.bagi_data(bersih.y, 0.2, 42)
    pasang = lambda idx: {(bersih.X[i].tobytes(), str(bersih.y[i])) for i in idx}
    assert pasang(latih).isdisjoint(pasang(uji))


# ------------------------------------------------------------------ evaluasi
def test_evaluasi_konsisten(tmp_path):
    d = t.baca_dataset(buat_csv(tmp_path / "d.csv", per_kelas=60))
    latih, uji = t.bagi_data(d.y, 0.25, 1)
    model, _, _ = t.latih(d.X[latih], d.y[latih], 1)
    m = t.evaluasi(model, d.X[uji], d.y[uji], d.y[latih])
    cm = np.array(m["confusion_matrix"])
    assert cm.sum() == m["jumlah_uji"] == len(uji)
    assert m["akurasi"] == pytest.approx(np.trace(cm) / cm.sum())
    assert m["akurasi_top_k"] == 1.0 and m["k_top"] == 3
    assert m["kelas"] == [str(k) for k in model.classes_]
    assert sum(r["support"] for r in m["per_kelas"]) == m["jumlah_uji"]
    lo, hi = m["akurasi_selang_95"]
    assert 0 <= lo <= m["akurasi"] <= hi <= 1
    assert m["baseline_acak"] == pytest.approx(1 / 3)


def test_selang_wilson():
    assert t.wilson(0.5, 100) == pytest.approx((0.404, 0.596), abs=0.002)
    assert t.wilson(1.0, 50)[1] == 1.0 and t.wilson(0.0, 0) == (0.0, 0.0)


# --------------------------------------------------------- alur lengkap (jalankan)
def test_alur_lengkap_menghasilkan_artefak_yang_konsisten(tmp_path):
    kode, ds, keluaran, hasil = latih_di(tmp_path)
    assert kode == 0
    model = joblib.load(keluaran / "rf_model.pkl")
    meta = json.loads((keluaran / "model_meta.json").read_text(encoding="utf-8"))
    assert meta["kode_gejala"] == [f"G0{i}" for i in range(1, 7)]
    assert meta["kode_kelas"] == [str(k) for k in model.classes_] == ["K1", "K2", "K3"]
    assert model.n_features_in_ == len(meta["kode_gejala"])
    assert meta["versi_library"]["scikit-learn"] == sklearn.__version__ and meta["versi_library"]["numpy"] == np.__version__
    assert meta["dataset"]["sha256"] == hashlib.sha256(ds.read_bytes()).hexdigest()
    assert meta["dataset"]["data_sintetis"] is True and meta["jumlah_latih"] + meta["jumlah_uji"] == meta["dataset"]["baris_setelah_bersih"]
    assert meta["peringatan"][0].startswith("PERINGATAN: DATA SINTETIS")
    for nama in ("laporan_evaluasi.md", "metrik.json", "confusion_matrix.csv", "distribusi_kelas.csv", "pentingnya_gejala.csv"):
        assert (hasil / nama).is_file(), nama
    metrik = json.loads((hasil / "metrik.json").read_text(encoding="utf-8"))
    assert sum(map(sum, metrik["metrik_uji"]["confusion_matrix"])) == meta["jumlah_uji"]
    assert meta["metrik_uji"]["akurasi"] == metrik["metrik_uji"]["akurasi"]


def test_urutan_kolom_proba_sama_dengan_meta_kode_kelas(tmp_path):
    _, _, keluaran, _ = latih_di(tmp_path)
    model = joblib.load(keluaran / "rf_model.pkl")
    meta = json.loads((keluaran / "model_meta.json").read_text(encoding="utf-8"))
    pola = {"K1": [1, 1, 0, 0, 0, 0], "K2": [0, 0, 1, 1, 0, 0], "K3": [0, 0, 0, 0, 1, 1]}
    for kelas, vektor in pola.items():
        proba = model.predict_proba([vektor])[0]
        assert meta["kode_kelas"][int(np.argmax(proba))] == kelas


def test_laporan_memuat_peringatan_hanya_untuk_data_sintetis(tmp_path):
    (tmp_path / "s").mkdir()
    _, _, _, hasil = latih_di(tmp_path / "s")
    teks = (hasil / "laporan_evaluasi.md").read_text(encoding="utf-8")
    assert "DATA SINTETIS" in teks and "JANGAN dilaporkan" in teks and "belum divalidasi mekanik pada 120 dari 120" in teks
    (tmp_path / "n").mkdir()
    _, _, keluaran, hasil_nyata = latih_di(tmp_path / "n", sumber="BENGKEL_NYATA")
    teks = (hasil_nyata / "laporan_evaluasi.md").read_text(encoding="utf-8")
    assert "DATA SINTETIS" not in teks
    meta = json.loads((keluaran / "model_meta.json").read_text(encoding="utf-8"))
    assert meta["dataset"]["data_sintetis"] is False
    assert not any("SINTETIS" in p for p in meta["peringatan"])
    assert not any("np.str_" in p for p in meta["peringatan"])


def test_hasil_identik_untuk_seed_yang_sama(tmp_path):
    (tmp_path / "a").mkdir(), (tmp_path / "b").mkdir()
    _, _, _, h1 = latih_di(tmp_path / "a")
    _, _, _, h2 = latih_di(tmp_path / "b")
    a = json.loads((h1 / "metrik.json").read_text(encoding="utf-8"))
    b = json.loads((h2 / "metrik.json").read_text(encoding="utf-8"))
    assert a == b


def test_model_hanya_dilatih_dengan_data_latih(tmp_path, monkeypatch):
    from sklearn.ensemble import RandomForestClassifier

    panggilan = []
    asli = RandomForestClassifier.fit

    def pantau(self, X, y, *a, **k):
        panggilan.append(len(X))
        return asli(self, X, y, *a, **k)

    monkeypatch.setattr(RandomForestClassifier, "fit", pantau)
    _, _, keluaran, _ = latih_di(tmp_path)
    meta = json.loads((keluaran / "model_meta.json").read_text(encoding="utf-8"))
    assert panggilan[0] == meta["jumlah_latih"] < meta["dataset"]["baris_setelah_bersih"]


def test_penjaga_menolak_data_sintetis_di_folder_models(tmp_path, capsys):
    ds = buat_csv(tmp_path / "d.csv")
    folder = tmp_path / "models"
    kode = t.jalankan(["--dataset", str(ds), "--keluaran", str(folder), "--hasil", str(tmp_path / "h")])
    assert kode == 2 and not folder.exists()
    assert "SINTETIS" in capsys.readouterr().err
    kode = t.jalankan(["--dataset", str(ds), "--keluaran", str(folder), "--hasil", str(tmp_path / "h"), "--izinkan-sintetis"])
    assert kode == 0 and (folder / "rf_model.pkl").is_file()


def test_data_nyata_boleh_disimpan_ke_folder_models(tmp_path):
    ds = buat_csv(tmp_path / "d.csv", sumber="BENGKEL_NYATA")
    assert t.jalankan(["--dataset", str(ds), "--keluaran", str(tmp_path / "models"), "--hasil", str(tmp_path / "h")]) == 0


def test_dataset_rusak_menghasilkan_kode_keluar_2_tanpa_artefak(tmp_path, capsys):
    p = tulis(tmp_path / "d.csv", [["1", 5, 0, "K1"], ["2", 0, 1, "K2"]])
    kode = t.jalankan(["--dataset", str(p), "--keluaran", str(tmp_path / "k"), "--hasil", str(tmp_path / "h")])
    assert kode == 2 and "GAGAL" in capsys.readouterr().err
    assert not (tmp_path / "k").exists()


def test_cari_parameter_hanya_memakai_data_latih(tmp_path, monkeypatch):
    from sklearn.model_selection import GridSearchCV

    monkeypatch.setattr(t, "GRID_PARAMETER", {"n_estimators": [20, 30], "max_depth": [None, 3]})
    dilihat = []
    asli = GridSearchCV.fit

    def pantau(self, X, y, *a, **k):
        dilihat.append(len(X))
        return asli(self, X, y, *a, **k)

    monkeypatch.setattr(GridSearchCV, "fit", pantau)
    kode, _, keluaran, hasil = latih_di(tmp_path, "--cari-parameter")
    assert kode == 0
    meta = json.loads((keluaran / "model_meta.json").read_text(encoding="utf-8"))
    assert dilihat == [meta["jumlah_latih"]]
    assert meta["parameter"]["n_estimators"] in (20, 30) and meta["parameter"]["max_depth"] in (None, 3)
    metrik = json.loads((hasil / "metrik.json").read_text(encoding="utf-8"))
    assert 1 <= len(metrik["pencarian_parameter"]["lima_terbaik"]) <= 4
    assert "data uji tidak dipakai memilih" in (hasil / "laporan_evaluasi.md").read_text(encoding="utf-8")


def test_nama_gejala_dan_kelas_dari_daftar_masuk_ke_meta(tmp_path):
    ds = buat_csv(tmp_path / "d.csv")
    (tmp_path / "daftar_gejala_v3.csv").write_text("kode,uraian\nG01,Mesin susah hidup\nG02,Mati mendadak\n", encoding="utf-8")
    (tmp_path / "daftar_kelas_v3.csv").write_text("kode,nama\nK1,Busi\nK2,Aki\n", encoding="utf-8")
    assert t.jalankan(["--dataset", str(ds), "--keluaran", str(tmp_path / "k"), "--hasil", str(tmp_path / "h")]) == 0
    meta = json.loads((tmp_path / "k" / "model_meta.json").read_text(encoding="utf-8"))
    assert meta["nama_gejala"] == {"G01": "Mesin susah hidup", "G02": "Mati mendadak"}
    assert meta["nama_kelas"] == {"K1": "Busi", "K2": "Aki"}


@pytest.mark.skipif(not BARIS_DATASET_ASLI.is_file(), reason="dataset v3 tidak ada di folder dataset")
def test_dataset_v3_yang_disertakan_lolos_validasi():
    d = t.baca_dataset(BARIS_DATASET_ASLI)
    assert (d.baris_awal, len(d.kode_gejala), len(set(d.y))) == (1080, 31, 9)
    assert d.data_sintetis is True and d.status_verifikasi == {"belum_diverifikasi": 1080}
    bersih, info = t.hapus_duplikat(d)
    assert bersih.jumlah == 1070 and info["vektor_lintas_kelas"] == 3


def test_peringatan_kelas_kecil_terbaca_manusia(tmp_path):
    ds = buat_csv(tmp_path / "d.csv", per_kelas=20, sumber="BENGKEL_NYATA")
    assert t.jalankan(["--dataset", str(ds), "--keluaran", str(tmp_path / "k"), "--hasil", str(tmp_path / "h")]) == 0
    meta = json.loads((tmp_path / "k" / "model_meta.json").read_text(encoding="utf-8"))
    kecil = [p for p in meta["peringatan"] if "kurang dari 30 sampel" in p]
    assert len(kecil) == 1 and "np.str_" not in kecil[0] and "'K1'" in kecil[0]
    assert "kurang dari 30 sampel" in (tmp_path / "h" / "laporan_evaluasi.md").read_text(encoding="utf-8")


def test_alur_utama_membuang_duplikat_sebelum_membagi(tmp_path):
    judul = ("id_kasus", "G01", "G02", "G03", "G04", "G05", "G06", "kelas")
    baris = []
    for kelas, awal in (("K1", [1, 0]), ("K2", [0, 1])):
        for n in range(12):  # 12 pola unik per kelas, tiap pola muncul 3 kali
            pola = awal + [int(b) for b in format(n, "04b")]
            for ulang in range(3):
                baris.append([f"{kelas}-{n}-{ulang}", *pola, kelas])
    p = tulis(tmp_path / "d.csv", baris, judul)
    assert t.jalankan(["--dataset", str(p), "--keluaran", str(tmp_path / "k"), "--hasil", str(tmp_path / "h")]) == 0
    meta = json.loads((tmp_path / "k" / "model_meta.json").read_text(encoding="utf-8"))
    assert meta["dataset"]["baris_dibaca"] == 72
    assert meta["dataset"]["baris_setelah_bersih"] == 24
    assert "48 dibuang" in (tmp_path / "h" / "laporan_evaluasi.md").read_text(encoding="utf-8")
