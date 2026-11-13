# Dataset v3 – motor_injeksi (1.080 baris, SINTETIS)

## Isi paket
| File | Keterangan |
|---|---|
| `dataset_v3_motor_injeksi.csv` | 1.080 baris × 39 kolom (skema sama dengan v2). 120 baris/kelas. |
| `daftar_kelas_v3.csv`, `daftar_gejala_v3.csv` | Sama seperti v2 + sumber tambahan + kolom `cakupan`. |
| `daftar_sumber_v3.csv` | 51 sumber (S01–S25 asli, S26–S51 baru) + status akses. |
| `generate_dataset_v3.py` | Skrip pembuat (seed tetap, dapat dijalankan ulang / diubah ukurannya). |

## Perubahan
- `jenis_motor` semua baris = `motor_injeksi` (sebelumnya `matic_injeksi`).
- W001–W360 tidak diubah selain `jenis_motor`. W361–W1080 baru (`catatan` = `ekspansi_v3`; bila ada silang-gejala: `ekspansi_v3;overlap=Kx`).
- `sumber_data` tetap `WEB_SINTETIS`; `status_verifikasi` tetap `belum_diverifikasi`; kolom mekanik kosong.

## Cara baris baru dibuat
Tidak ada sumber web yang menerbitkan data kasus per-baris. Sumber hanya menjelaskan gejala per komponen dalam bentuk artikel. Maka baris baru adalah sampel acak dari profil peluang gejala per kelas:
1. Profil = frekuensi gejala di 360 baris asli (gejala non-khas dihaluskan ke ±0,035).
2. Dua penyesuaian berdasar sumber: K4–G04 0,30→0,55 (S36, S37); K1–G28 0,05→0,30 (S26, S27).
3. 15% baris diberi 1 gejala tambahan dari kelas yang menurut sumber sering tertukar (mis. S08, S20, S23).
4. Setiap vektor gejala baru unik terhadap seluruh dataset.

Angka 0,15 / 0,035 / 0,55 / 0,30 adalah **asumsi**, bukan hasil pengukuran.

## Keterbatasan penting
1. **Ini data sintetis.** Akurasi model di dalamnya hanya mengukur seberapa baik model menebak ulang profil di atas, bukan kemampuan mendiagnosis motor nyata. Pada uji cepat (RandomForest/LogReg, 5-fold) akurasi ≈ 0,81–0,86; jangan dilaporkan sebagai performa dunia nyata.
2. **K2, K3, K4 dan gejala G09–G13, G30, G31 hanya berlaku untuk matic (CVT).** Motor bebek/sport injeksi tidak punya CVT. Lihat kolom `cakupan`. Dengan label tunggal `motor_injeksi`, kelas-kelas ini tidak bisa dibedakan dari motor non-matic.
3. `jenis_motor` kini konstan, jadi tidak berguna sebagai fitur.
4. v2 asli sudah memuat 13 vektor duplikat (3 di antaranya lintas kelas); dibiarkan. Baris baru tidak menambah duplikat.
5. Kelas K5 vs K6 (starter vs aki), K2 vs K4, dan K4 vs K8 paling sering tertukar pada uji cepat.
6. 4 URL asli (S03, S06, S11, S24) belum bisa dikonfirmasi dalam pencarian 2026-10-30; cek manual sebelum dikutip. Status "ditemukan" artinya muncul di hasil pencarian, bukan dibaca penuh.
7. S19 (detikOto, 2011) membahas tes kompresi mesin secara umum, bukan khusus motor injeksi.
8. Baris diurutkan per kelas (seperti v2); lakukan stratified shuffle sebelum membagi train/test.
