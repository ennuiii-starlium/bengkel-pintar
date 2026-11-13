# Laporan Evaluasi Model Random Forest

> **PERINGATAN: DATA SINTETIS. Dataset ini dibuat dari artikel web dan sampel acak, bukan dari kasus bengkel sungguhan, dan labelnya belum divalidasi mekanik. Angka di bawah hanya mengukur seberapa baik model menebak ulang data buatan itu. JANGAN dilaporkan sebagai kemampuan mendiagnosis motor sungguhan.**

> Label belum divalidasi mekanik pada 1080 dari 1080 baris.

## 1. Data

- Berkas: `dataset_v3_motor_injeksi.csv` (SHA-256 `4e66ce9fe8038596...`)
- Baris dibaca: 1080; setelah membuang duplikat gejala+label: 1070 (10 dibuang)
- Vektor gejala yang sama tetapi berlabel berbeda: 3 (dipertahankan)
- Jumlah gejala (fitur): 31; jumlah kelas: 9
- `sumber_data`: {'WEB_SINTETIS': 1080}
- `status_verifikasi`: {'belum_diverifikasi': 1080}

### Distribusi kelas

| Kelas | Nama | Jumlah | Persen |
|---|---|---:|---:|
| K1 | Busi lemah/kotor | 120 | 11.2% |
| K2 | V-belt aus/mulur | 119 | 11.1% |
| K3 | Roller CVT aus/peyang | 117 | 10.9% |
| K4 | Per CVT lemah (sumber terbatas) | 118 | 11.0% |
| K5 | Dinamo starter/bendik bermasalah | 118 | 11.0% |
| K6 | Aki lemah | 119 | 11.1% |
| K7 | Kompresi bocor (ring piston/klep/seal klep) | 119 | 11.1% |
| K8 | Pompa bensin (fuel pump) lemah | 120 | 11.2% |
| K9 | Injektor/throttle body kotor | 120 | 11.2% |

Rasio kelas terbanyak terhadap tersedikit: 1.03.

## 2. Pengaturan

- Pembagian: 856 latih / 214 uji (berstrata, random_state=42).
- Parameter: `{"n_estimators": 300, "max_depth": null, "min_samples_leaf": 1, "max_features": "sqrt", "class_weight": null}`
- Parameter bawaan, tanpa penyetelan.

## 3. Hasil pada data uji

- Akurasi: **81.8%** (selang 95% kira-kira 76.1% sampai 86.4%, dari 214 baris uji)
- Akurasi top-3 (kelas benar ada di 3 peringkat teratas): 98.1%
- Pembanding: selalu menebak kelas mayoritas 11.2%; menebak acak 11.1%
- Makro: precision 0.816, recall 0.817, F1 0.814
- Berbobot: precision 0.816, recall 0.818, F1 0.814

| Kelas | Nama | Precision | Recall | F1 | Jumlah uji |
|---|---|---:|---:|---:|---:|
| K1 | Busi lemah/kotor | 1.000 | 0.875 | 0.933 | 24 |
| K2 | V-belt aus/mulur | 0.880 | 0.917 | 0.898 | 24 |
| K3 | Roller CVT aus/peyang | 0.917 | 0.957 | 0.936 | 23 |
| K4 | Per CVT lemah (sumber terbatas) | 0.696 | 0.667 | 0.681 | 24 |
| K5 | Dinamo starter/bendik bermasalah | 0.619 | 0.565 | 0.591 | 23 |
| K6 | Aki lemah | 0.700 | 0.583 | 0.636 | 24 |
| K7 | Kompresi bocor (ring piston/klep/seal klep) | 0.958 | 0.958 | 0.958 | 24 |
| K8 | Pompa bensin (fuel pump) lemah | 0.778 | 0.875 | 0.824 | 24 |
| K9 | Injektor/throttle body kotor | 0.793 | 0.958 | 0.868 | 24 |

### Confusion matrix (baris = kelas sebenarnya, kolom = prediksi)

| | K1 | K2 | K3 | K4 | K5 | K6 | K7 | K8 | K9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **K1** | 21 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| **K2** | 0 | 22 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| **K3** | 0 | 0 | 22 | 0 | 1 | 0 | 0 | 0 | 0 |
| **K4** | 0 | 2 | 1 | 16 | 0 | 0 | 0 | 4 | 1 |
| **K5** | 0 | 0 | 0 | 2 | 13 | 6 | 1 | 1 | 0 |
| **K6** | 0 | 0 | 0 | 1 | 7 | 14 | 0 | 1 | 1 |
| **K7** | 0 | 0 | 0 | 0 | 0 | 0 | 23 | 0 | 1 |
| **K8** | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 21 | 1 |
| **K9** | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 23 |

Pasangan yang paling sering tertukar (sebenarnya -> diprediksi):

- K6 -> K5: 7 kali
- K5 -> K6: 6 kali
- K4 -> K8: 4 kali
- K1 -> K9: 2 kali
- K4 -> K2: 2 kali

## 4. Validasi silang (gambaran kestabilan)

- 5-fold berstrata pada seluruh data setelah dibersihkan, parameter yang sama:
  akurasi 80.2% +- 2.0%, F1 makro 0.800 +- 0.020
- Ini gambaran kestabilan, bukan pengganti data uji. Jika parameter disetel, angka ini sedikit optimistis.

## 5. Gejala paling berpengaruh

| Gejala | Uraian | Kepentingan |
|---|---|---:|
| G19 | Elektroda busi hitam/kotor/berkerak (hasil pemeriksaan) | 0.069 |
| G24 | Tekanan kompresi rendah (hasil pengukuran) | 0.056 |
| G11 | Bunyi berdecit/dengung dari area CVT | 0.052 |
| G31 | Roller peyang/aus (hasil pemeriksaan fisik) | 0.051 |
| G15 | Starter terasa berat/lemah/panjang | 0.044 |
| G05 | Tarikan brebet/tersendat saat digas | 0.044 |
| G17 | Lampu meredup atau klakson melemah saat starter ditekan | 0.040 |
| G26 | Respons gas lambat/terlambat | 0.038 |
| G30 | V-belt retak/mulur/pecah (hasil pemeriksaan fisik) | 0.037 |
| G04 | Tarikan terasa berat/lemot | 0.037 |

## 6. Cara membaca hasil ini

- Keyakinan model adalah probabilitas dari `predict_proba`, bukan jaminan kebenaran.
- Dengan 214 baris uji, selisih satu baris sekitar 0.5%. Hindari melaporkan akurasi dengan presisi berlebih.
- Kepentingan gejala menunjukkan apa yang dipelajari model dari data ini, bukan bukti sebab-akibat teknis.
- Karena data sintetis, kelas yang sering tertukar mencerminkan tumpang tindih profil gejala buatan, bukan kebingungan diagnosis di lapangan.
- Untuk klaim yang bisa dipertanggungjawabkan, uji model dengan kasus nyata yang labelnya divalidasi mekanik.

## 7. Reproduksi

- Python 3.12.3, scikit-learn 1.9.1, numpy 2.5.4
- Perintah: `python training\train_model.py` dari folder `bengkelpintar_backend`.
- Dibuat: 2026-11-10 09:20 UTC
