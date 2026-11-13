# bengkelpintar_backend (sisi machine learning)

Folder ini hanya untuk melatih dan mengevaluasi model. **Bukan server.** Server satu-satunya adalah `bengkelpintar_api`.

## Status saat ini (baca dulu)
- Dataset yang ada, `dataset/dataset_v3_motor_injeksi.csv`, **sintetis**: seluruh 1.080 barisnya bertanda `WEB_SINTETIS` dan `belum_diverifikasi`, tanpa validasi mekanik. Lihat `dataset/README_v3.md`.
- Hasil pelatihan **hanya mengukur seberapa baik model menebak ulang data buatan**. Jangan dilaporkan sebagai kemampuan mendiagnosis motor sungguhan.
- Kode di dataset (`K1`..`K9`, `G01`..`G31`) **tidak cocok** dengan data master database (`K01`..`K10`, `G01`..`G18`), bahkan kode yang sama bisa berarti lain. Karena itu model ini **tidak dipasang ke API**. API tetap memakai fungsi skor tiruan (B-08).
- Model disimpan ke `models_pengembangan\`, bukan `models\`. Skrip menolak menyimpan data sintetis ke folder `models` kecuali dipaksa (`--izinkan-sintetis`).

## Menjalankan (PowerShell, dari folder ini)
```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python training\train_model.py
python -m pytest -q
```
`scikit-learn` dan `numpy` di `requirements.txt` harus sama persis dengan `bengkelpintar_api\requirements.txt`, karena berkas `.pkl` sensitif terhadap versi.

Keluaran: `models_pengembangan\rf_model.pkl` dan `model_meta.json`; laporan di `training\hasil\` (`laporan_evaluasi.md`, `metrik.json`, `confusion_matrix.csv`, `distribusi_kelas.csv`, `pentingnya_gejala.csv`).

Opsi: `--cari-parameter` (setel parameter dengan CV hanya pada data latih), `--porsi-uji 0.2`, `--seed 42`, `--dataset <berkas>`, `--keluaran <folder>`.

## Memeriksa kecocokan dengan database
Simpan daftar gejala dan kerusakan dari API (server harus berjalan), lalu bandingkan:
```
$h = @{ "X-API-Key" = "<API_KEY>"; "Content-Type" = "application/json" }
$t = (Invoke-RestMethod -Method Post http://localhost:8000/auth/login -Headers $h -Body '{"username":"admin","password":"<PASSWORD>"}').access_token
$h["Authorization"] = "Bearer $t"
Invoke-RestMethod http://localhost:8000/gejala    -Headers $h | ConvertTo-Json -Depth 5 | Set-Content gejala_db.json    -Encoding utf8
Invoke-RestMethod http://localhost:8000/kerusakan -Headers $h | ConvertTo-Json -Depth 5 | Set-Content kerusakan_db.json -Encoding utf8
python training\cek_kecocokan.py --meta models_pengembangan\model_meta.json --gejala-json gejala_db.json --kerusakan-json kerusakan_db.json
```
Hasil di `training\hasil\kecocokan_database.md`. Kode keluar 0 berarti cocok. **Model hanya boleh dipasang ke API (B-11) bila hasilnya COCOK dan datanya sudah tervalidasi.** Hapus `gejala_db.json` dan `kerusakan_db.json` setelah dipakai.

## Memakai dataset lain
Satu baris per kasus; kolom gejala `G01`, `G02`, ... berisi `0` atau `1`; satu kolom label bernama `kerusakan` atau `kelas`. Kolom opsional: `id_kasus`, `sumber_data`, `status_verifikasi`. Daftar nama gejala dan kerusakan (`daftar_gejala_v3.csv`, `daftar_kelas_v3.csv`: kode, nama) dibaca dari folder yang sama dengan dataset bila ada. Skrip menolak data yang rusak dengan pesan yang menyebut nomor barisnya.
