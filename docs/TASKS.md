# TASKS.md: BengkelPintar

Daftar tugas proyek dalam **dua bagian**: Bagian A untuk frontend (Flutter, kode `T-`) dan Bagian B untuk backend (server, database, model, dan sambungan ke API, kode `B-`).
Acuan: `docs/PRD.md` (kebutuhan, 34 halaman, kontrak API), `AGENTS.md` (aturan kerja dan batas folder), `docs/HALAMAN.md` (urutan halaman, jenis header, navigasi), dan `docs/DESIGN.md` (UI/UX, sketsa, data baku).

## Cara Memakai File Ini

- Kerjakan **satu tugas per langkah**, sesuai urutan nomor. Jangan melompat atau menggabung banyak tugas.
- Perintah contoh untuk agent: *"Kerjakan T-03"* atau *"Kerjakan B-02"*.
- Setelah selesai: jalankan pemeriksaan (`flutter analyze`, `flutter test`, atau `pytest`), centang kotak tugas, dan laporkan file yang dibuat atau diubah.
- Tugas hanya dianggap selesai jika **kriteria selesai** terpenuhi.
- Jika sebuah tugas bertentangan dengan `docs/PRD.md`, hentikan dan tanyakan.
- **Batas folder:** tugas `T-` hanya mengubah `bengkelpintar\`. Tugas `B-` mengikuti tabel batas folder di `AGENTS.md` bagian 3.
- **Frontend tidak pernah menunggu backend.** Semua tugas `T-` memakai data mock. Hanya tugas `B-13` sampai `B-16` yang menyambungkan Flutter ke server, dan itu bagian backend.
- Tugas yang membuat layar: ikuti `docs/DESIGN.md` (pola layar dan sketsa), lalu centang halaman terkait di `docs/HALAMAN.md` **setelah pengguna menyetujui tampilannya**.
- Mock memakai **data baku `docs/DESIGN.md` bagian 16** dan teks baku bagian 17.
- **Gerbang persetujuan antar-tugas dihapus** sesuai instruksi pengguna. Halaman
  di `docs/HALAMAN.md` tetap tidak dicentang sampai pengguna menyetujui
  tampilannya.

**Peran:** `M` = mekanik, `A` = admin.

## Ringkasan Progres

| Bagian | Tugas | Selesai |
|---|---|---|
| A. Frontend | T-01 sampai T-30 | 29 / 30 |
| B. Backend | B-01 sampai B-16 | 0 / 16 |

Tugas terakhir selesai: T-28/T-30

---

# BAGIAN A: FRONTEND (folder `bengkelpintar\`)

Semua tugas di bagian ini memakai data mock dan **tidak bergantung pada backend**.

## Ringkasan Blok

| Blok | Tugas | Isi |
|---|---|---|
| 1. Fondasi | T-01 sampai T-05 | Setup, tema, navigasi, mock, konfigurasi |
| 2. Autentikasi | T-06 sampai T-08 | Splash, pengaturan server, login, beranda |
| 3. Diagnosis | T-09 sampai T-12 | Gejala, hasil, riwayat |
| 4. POS | T-13 sampai T-18 | Transaksi, nota, katalog |
| 5. Admin | T-19 sampai T-22 | Data master, pengguna, laporan |
| 6. Tambahan | T-26 sampai T-30 | Pengaturan bengkel, password, server tidak terjangkau, daftar gejala dan kerusakan, kategori produk |
| 7. Penutup | T-23 sampai T-25 | Profil, pengujian, serah terima |

---

## Blok 1: Fondasi

### [x] T-01: Setup proyek Flutter
**Isi:**
- Buat proyek Flutter `bengkelpintar` di `C:\bengkel\` (jika belum ada).
- Tambah paket: `provider`, `shared_preferences`, `intl`, `pdf`, `printing` (atau `share_plus`) untuk bagikan nota, dan `fl_chart` untuk grafik (berjalan tanpa internet), serta `material_symbols_icons` untuk ikon (outline membulat, dibundel, tanpa internet; lihat `docs/DESIGN.md` bagian 4.4).
- Buat struktur folder: `lib/core/{theme,widgets,utils}`, `lib/data`, `lib/services`, `lib/features/{auth,diagnosis,pos,laporan}`, `assets/{mock,fonts,images}`.
- Bundel **Plus Jakarta Sans** (400, 500, 600, 700) sebagai font global dan Poppins (400, 500, 600, 700) untuk layar yang memakainya. Daftarkan di `pubspec.yaml`. Jangan memakai `google_fonts` yang mengunduh saat runtime.
- Daftarkan `assets/mock/` dan `assets/images/` di `pubspec.yaml`.
- Android: aktifkan `usesCleartextTraffic` di `AndroidManifest.xml` untuk **build demo** (server lokal memakai HTTP), dan aktifkan mode edge-to-edge.
- Konfigurasi alamat server lewat `--dart-define=API_BASE_URL=...` (demo: IP laptop, produksi: `https://api.<domain>`). Alamat dibaca di satu tempat di `lib/core`.

**Kriteria selesai:** `flutter pub get` dan `flutter analyze` bersih, aplikasi bisa dijalankan, font Plus Jakarta Sans tampil, dan font Poppins tersedia untuk layar pengecualian.

### [x] T-02: Tema dan komponen dasar
**Isi:** ikuti `docs/DESIGN.md` bagian 2 sampai 5 dan 11.
- **Token tema** di `lib/core/theme`: `app_colors.dart`, `app_icons.dart` (pemetaan fungsi ke ikon, `docs/DESIGN.md` bagian 18), `app_text.dart`, `app_spacing.dart` (jarak dan radius), `app_system_ui.dart` (bilah status transparan, ikon terang), `app_theme.dart` (Material 3).
- **Komponen** di `lib/core/widgets`: `AppButton` (primary, secondary, tonal, small, danger), `CircleIconButton`, `AppSearchBar`, `AppChip`, `AppTag`, `AppCheckbox`, `AppSwitch`, `AppDropdown`, `UrgensiBadge`, `StatusBadge`, `PerkiraanLabel`, `ListCard`, `ProductCard`, `StatHeaderCard`, `BlueHeader` (jenis H1 sampai H4 dan `HeaderDecoration`), `FloatingNavBar` (tombol Diagnosis menonjol di tengah), `FloatingActionBar`, `QtyStepper`, `CheckListItem`, `DataRowItem`, `DashedDivider`, `EmptyState`, `ErrorState`, `LoadingSkeleton`.
- **Helper** di `lib/core/utils`: format rupiah (`Rp30.000`) dan format tanggal Indonesia (`24 Okt 2026, 10:15`).
- Komponen grafik (`BarChartCard`, `DonutChartCard`) dan `ReceiptView` dibuat saat dibutuhkan di T-21, T-22, dan T-15.

**Kriteria selesai:** semua komponen bisa dilihat di satu layar uji sementara, tanpa strip putih di atas, dan tidak ada warna atau ukuran yang ditulis langsung di luar token, dan semua nama ikon di `DESIGN.md` bagian 18 sudah diperiksa ada di paket (laporkan yang tidak ada). Layar tidak memanggil `Icons.xxx` atau `Symbols.xxx` langsung.

Gerbang persetujuan antar-tugas dihapus sesuai instruksi pengguna. Pemeriksaan visual tetap wajib dicatat.

### [x] T-03: Navigasi dan pembatasan peran
**Isi:**
- Routing antar layar (nama rute terpusat di `lib/core`).
- Mekanisme penjaga rute: layar khusus admin tidak bisa dibuka oleh mekanik.
- Menu beranda menyesuaikan peran.

**Kriteria selesai:** login sebagai `M` tidak bisa membuka rute khusus `A`, dan mencoba membukanya menampilkan layar Akses Ditolak (halaman 26).

### [x] T-04: Model data dan data mock
**Isi:**
- Buat model Dart di `lib/data/models` yang **bentuknya sama persis** dengan kontrak API di `docs/PRD.md` bagian 9: `User`, `Gejala`, `Kerusakan`, `HasilDiagnosis`, `RiwayatDiagnosis`, `Produk`, `Jasa`, `Transaksi`, `ItemTransaksi`. Model `Kategori` dan `PengaturanBengkel` ditambahkan di T-30 dan T-26.
- Buat file JSON mock di `assets/mock/` memakai **data baku `docs/DESIGN.md` bagian 16**: pengguna (3: Andi Pratama admin, Budi Santoso dan Rina Wulandari mekanik), pelanggan (4), gejala (18), kerusakan (10), kategori produk (6), produk (12), jasa (9), transaksi (4), riwayat diagnosis contoh, dan data bengkel (Bengkel Maju Jaya).
- Diagnosis mock: kombinasi gejala tertentu menghasilkan hasil tertentu (aturan sederhana), **bukan acak**, supaya bisa diuji berulang. Contoh dari PRD (mesin susah dihidupkan + tarikan berat + knalpot asap putih = Busi kotor / aus, 78%).
- Setiap model punya `fromJson` dan `toJson`.

**Kriteria selesai:** semua file mock terbaca tanpa error dan nama field sama dengan kontrak API.

### [x] T-05: Lapisan service (antarmuka dan implementasi mock)
**Isi:**
- Di `lib/services`, buat **antarmuka abstrak** per area: `AuthService`, `DiagnosisService`, `ProdukService`, `JasaService`, `TransaksiService`, `LaporanService`, `PenggunaService`, `KerusakanService`.
- Buat implementasi **mock** untuk tiap antarmuka (membaca JSON dari T-04, data bisa diubah di memori selama aplikasi berjalan).
- Tambahkan jeda buatan singkat (sekitar 300-600 ms) agar status "memuat" teruji.
- Daftarkan service lewat Provider di `main.dart` sehingga implementasi bisa diganti tanpa mengubah layar.
- Semua layar **hanya** memakai antarmuka, tidak pernah mock langsung.

**Kriteria selesai:** mengganti implementasi mock dengan kelas lain cukup mengubah satu tempat di `main.dart`.

---

## Blok 2: Autentikasi dan Beranda

### [x] T-06: Splash dan Pengaturan Server (layar 1 dan 2)
**Isi:**
- Splash: logo dan nama BengkelPintar, cek apakah sudah ada sesi login.
- Splash langsung menuju Login (atau Beranda bila sudah login). **Tidak ada layar alamat server di alur harian.**
- Pengaturan Server (hanya admin, dibuka dari Profil): **satu kolom URL penuh** (contoh `http://192.168.1.10:8000`), tombol "Tes Koneksi" (memanggil `GET /health`, di fase 1 hasilnya mock), dan "Kembalikan ke bawaan". Alamat yang diubah disimpan di `shared_preferences` dan menimpa nilai `API_BASE_URL`.

**Kriteria selesai:** aplikasi langsung memakai alamat bawaan tanpa input pengguna, dan alamat yang diubah admin tetap ada setelah aplikasi dibuka ulang.

### [x] T-07: Login dan sesi (layar 3)
**Isi:**
- Form username dan password, validasi tidak boleh kosong, status memuat, pesan error bahasa Indonesia.
- Login lewat `AuthService`. Simpan token mock dan data pengguna di state (Provider) dan `shared_preferences`.
- Logout menghapus sesi dan kembali ke login.
- Layar Login **tidak memiliki** tautan ke Pengaturan Server.

**Kriteria selesai:** login admin dan mekanik berhasil, kredensial salah menampilkan pesan, sesi bertahan setelah restart.

### [x] T-08: Beranda (layar 4)
**Isi:** ikuti `docs/DESIGN.md` bagian 6.2 (header H1).
- Header biru: avatar, nama pengguna, peran, ikon bel berlencana dan profil, empat angka statistik (admin: Diagnosis, Draft, Final, Stok Menipis; mekanik: Diagnosis, Draft Saya, Final, Riwayat), tombol panah untuk melipat statistik.
- Pencarian, banner "Diagnosis Cepat", dan deret menu cepat sesuai peran (admin: Diagnosis, Transaksi, Produk, Jasa, Laporan, Pengguna, Data Master; mekanik: Diagnosis, Riwayat, Draft).
- Bagian "Diagnosis Terbaru" (admin: semua pengguna, mekanik: miliknya sendiri).
- **Navigasi bawah mengambang** (`FloatingNavBar`) sesuai peran: Admin (Beranda, Transaksi, Diagnosis, Katalog, Profil), Mekanik (Beranda, Riwayat, Diagnosis, Draft, Profil).

**Kriteria selesai:** menu, angka, dan navigasi berbeda untuk `M` dan `A`, setiap menu membuka layar tujuan (boleh placeholder dahulu).

**Gerbang persetujuan:** setelah tugas ini selesai, agent **berhenti** dan menunggu pengguna memeriksa tampilan di emulator atau HP. Jangan lanjut ke tugas berikutnya sebelum disetujui.

---

## Blok 3: Diagnosis

### [x] T-09: Form Gejala (layar 5)
**Isi:**
- Daftar gejala sebagai checklist dengan kolom pencarian dan pengelompokan (bila data gejala punya kategori).
- Chip kategori gejala (Semua, Mesin, Kelistrikan, Rem, Transmisi).
- Penghitung gejala terpilih dan bar bawah tetap dengan tombol "Diagnosis" (nonaktif jika belum ada yang dipilih).
- Tombol "Reset pilihan".

**Kriteria selesai:** memilih gejala dan menekan Diagnosis mengirim daftar `gejala_ids` ke `DiagnosisService`.

### [x] T-10: Hasil Diagnosis (layar 6)
**Isi:** tampilkan semua field kontrak, dengan urutan:
- Kerusakan utama dan **tingkat keyakinan** (persentase, dengan cincin progres).
- **Kemungkinan lain** beserta persentase.
- **Urgensi** (label berwarna) dan keterangannya.
- **Solusi** dan **estimasi waktu**.
- **Komponen terkait** dan **jasa terkait** beserta harga.
- **Estimasi biaya** dengan label **"perkiraan"** yang jelas terlihat.
- Catatan kecil bahwa hasil adalah alat bantu, bukan kepastian.
- Tombol "Buat Draft Transaksi" dan "Diagnosis Ulang".

**Kriteria selesai:** contoh dari `docs/PRD.md` bagian 6.2 tampil lengkap dan sama isinya.

**Gerbang persetujuan:** setelah tugas ini selesai, agent **berhenti** dan menunggu pengguna memeriksa tampilan di emulator atau HP. Jangan lanjut ke tugas berikutnya sebelum disetujui.

### [x] T-11: Riwayat Diagnosis (layar 7)
**Isi:**
- Daftar riwayat (tanggal, kerusakan utama, keyakinan), terbaru di atas.
- Detail riwayat membuka tampilan yang sama dengan hasil diagnosis (pakai ulang komponen dari T-10).
- `M` hanya melihat riwayat miliknya. `A` melihat semua dan ada nama pembuat.

**Kriteria selesai:** aturan visibilitas per peran berfungsi.

### [x] T-12: Hubungan diagnosis ke transaksi
**Isi:**
- Tombol "Buat Draft Transaksi" di hasil diagnosis membuat draft dengan komponen dan jasa terkait sudah terisi, lalu membuka layar draft.
- Draft menyimpan referensi ke riwayat diagnosis.

**Kriteria selesai:** dari hasil diagnosis, satu ketukan menghasilkan draft yang isinya sesuai komponen dan jasa terkait.

---

## Blok 4: POS

### [x] T-13: Draft Transaksi / Keranjang (layar 8) `M` `A`
**Isi:**
- Daftar item (produk dan jasa) dengan jumlah, harga satuan, subtotal.
- Tambah item dari katalog (pemilih produk dan jasa dengan pencarian), ubah jumlah, hapus item.
- Input nama pelanggan dan plat nomor.
- Total otomatis. Peringatan jika jumlah melebihi stok tersedia.
- Tombol "Simpan Draft".

**Kriteria selesai:** draft bisa dibuat manual maupun dari diagnosis, total benar.

### [x] T-14: Daftar Transaksi (layar 9) `M` `A`
**Isi:**
- **Admin:** daftar semua transaksi dengan filter status (draft / final) dan pencarian (nama pelanggan atau plat). Ketuk transaksi membuka detail (halaman 18).
- **Mekanik:** judul "Draft Saya", hanya draft miliknya, tanpa tab Final dan tanpa tombol Finalisasi. Ketuk membuka Draft Transaksi (layar 8) untuk diubah.

**Kriteria selesai:** filter dan pencarian bekerja, dan mekanik tidak pernah melihat draft atau transaksi milik orang lain.

### [x] T-15: Finalisasi dan Nota (layar 10) `A`
**Isi:**
- Layar finalisasi: ringkasan item, total, metode pembayaran sederhana (tunai/transfer) dan jumlah dibayar, kembalian.
- Saat finalisasi (mock): status jadi final, **stok produk berkurang**, dan penolakan jika stok tidak cukup.
- Tampilan nota (nama bengkel, nomor, tanggal, pelanggan, item, total).
- Tombol bagikan nota sebagai **PDF**.

**Kriteria selesai:** setelah finalisasi stok berkurang dan nota bisa dibagikan sebagai PDF. Draft yang sudah final tidak bisa diubah.

### [x] T-16: Katalog Produk (layar 11) `A`
**Isi:** daftar, pencarian, tambah, ubah, nonaktifkan produk (nama, kategori, harga, stok). Penanda stok menipis. Validasi harga dan stok tidak negatif.

**Kriteria selesai:** operasi tambah, ubah, nonaktifkan bekerja pada data mock dan terlihat di pemilih produk pada T-13.

### [x] T-17: Katalog Jasa (layar 12) `A`
**Isi:** daftar, tambah, ubah, nonaktifkan jasa (nama, harga), dengan validasi.

**Kriteria selesai:** sama seperti T-16 untuk jasa.

### [x] T-18: Penyesuaian stok manual `A`
**Isi:** dari layar produk, admin dapat menambah atau mengurangi stok dengan alasan (contoh: barang masuk, rusak). Tercatat sebagai mutasi stok dan terlihat di detail produk.

**Kriteria selesai:** stok berubah dan riwayat mutasi tampil.

---

## Blok 5: Admin

### [x] T-19: Data Gejala dan Kerusakan (layar 13) `A`
**Isi:**
- Kelola gejala (tambah, ubah, nonaktifkan).
- Kelola kerusakan: nama, urgensi, solusi, estimasi waktu, dan **penautan komponen dan jasa terkait** (pemilih dari katalog).
- Tampilkan **peringatan** bahwa mengubah daftar gejala atau kelas kerusakan memerlukan pelatihan ulang model.

**Catatan:** layar ini berfungsi sebagai menu yang membuka Daftar Gejala dan Daftar Kerusakan (dibuat di T-29).

**Kriteria selesai:** perubahan penautan komponen terlihat pada hasil diagnosis mock.

### [x] T-20: Kelola Pengguna (layar 14) `A`
**Isi:** daftar pengguna, tambah, ubah, nonaktifkan, atur peran (admin / mekanik). Pengguna nonaktif tidak bisa login. Admin tidak bisa menonaktifkan dirinya sendiri.

**Kriteria selesai:** pengguna baru bisa login dan pengguna nonaktif ditolak.

### [x] T-21: Laporan Penjualan (layar 15) `A`
**Isi:**
- Pilih periode (hari ini, 7 hari, bulan ini, rentang kustom).
- Grafik batang penjualan per hari dan kartu angka besar, mengikuti `docs/DESIGN.md` bagian 20.
- Tampilkan total penjualan, jumlah transaksi, daftar transaksi final, dan produk atau jasa terlaris.
- Hanya transaksi berstatus final yang dihitung.

**Kriteria selesai:** angka laporan cocok dengan data transaksi final di mock.

### [x] T-22: Statistik diagnosis (opsional)
**Isi:** ringkasan kerusakan yang paling sering terdiagnosis dengan grafik donat dan daftar peringkat (`docs/DESIGN.md` bagian 20.2).

**Kriteria selesai:** tampil di beranda admin atau layar laporan. **Lewati jika waktu terbatas.**

---

## Blok 6: Tambahan

Kerjakan blok ini **sebelum T-25**. T-26 dan T-30 sebaiknya sebelum T-15 dan T-16 jika memungkinkan. Jika sudah terlanjur, perbarui nota dan form produk setelahnya.

### [x] T-26: Pengaturan Bengkel (halaman 32) `A`
**Isi:**
- Form nama bengkel, alamat, dan nomor telepon.
- Tambahkan model dan data mock `PengaturanBengkel`, serta service-nya (antarmuka dan implementasi mock).
- Data ini dipakai sebagai kop pada nota (T-15).

**Kriteria selesai:** perubahan nama dan alamat bengkel langsung terlihat pada tampilan dan PDF nota.

### [x] T-27: Ganti Password dan Reset Password (halaman 30 dan 31)
**Isi:**
- **Ganti Password** (M, A), dibuka dari Profil: password lama, password baru, konfirmasi. Validasi minimal 6 karakter, konfirmasi harus sama, password lama harus benar (mock).
- **Reset Password Pengguna** (A): dari Form Pengguna, admin mengatur password baru untuk pengguna lain, dengan dialog konfirmasi.
- Tambahkan metode di `AuthService` dan `PenggunaService`.

**Kriteria selesai:** setelah ganti atau reset, login dengan password lama ditolak dan password baru diterima.

### [x] T-28: Server Tidak Terjangkau (halaman 33)
**Isi:**
- Tampilan khusus saat aplikasi tidak bisa menghubungi server, dengan teks yang jelas (laptop mati, beda Wi-Fi, atau alamat salah).
- Tombol "Coba Lagi". Pintasan ke Pengaturan Server hanya untuk admin, mekanik melihat teks "Hubungi admin".
- Buat jenis error jaringan yang seragam di `lib/services`, sehingga semua layar menampilkan tampilan yang sama.
- Tambahkan **sakelar simulasi gagal** pada service mock (misalnya konfigurasi di `lib/core`), agar tampilan ini bisa diuji di fase 1.

**Kriteria selesai:** dengan simulasi gagal aktif, setiap layar yang memuat data menampilkan tampilan ini, dan "Coba Lagi" memuat ulang data setelah simulasi dimatikan.

### [x] T-29: Daftar Gejala dan Daftar Kerusakan (halaman 28 dan 29) `A`
**Isi:**
- **Daftar Gejala:** daftar, pencarian, status aktif atau nonaktif, tombol tambah dan ubah (membuka form halaman 23).
- **Daftar Kerusakan:** daftar dengan urgensi dan jumlah komponen terkait, tombol tambah dan ubah (membuka form halaman 24).
- Halaman 13 (T-19) menjadi menu yang membuka dua daftar ini.
- Tampilkan peringatan: mengubah gejala atau kelas kerusakan memerlukan pelatihan ulang model.

**Kriteria selesai:** dari menu halaman 13, kedua daftar terbuka dan perubahan di form tercermin di daftar.

### [x] T-30: Kelola Kategori Produk (halaman 34) `A`
**Isi:**
- Daftar, tambah, ubah, dan nonaktifkan kategori (contoh: Busi, Oli, Ban, Aki, Kelistrikan).
- Tambahkan model dan data mock `Kategori`, serta service-nya.
- Form produk (T-16) memilih kategori dari daftar ini, bukan mengetik bebas.
- Kategori yang masih dipakai produk tidak boleh dihapus, hanya dinonaktifkan.

**Kriteria selesai:** kategori baru langsung muncul sebagai pilihan di form produk, dan filter kategori di katalog bekerja.

---

## Blok 7: Penutup

### [x] T-23: Profil dan logout (layar 16)
**Isi:** info akun, peran, tombol logout dengan konfirmasi, versi aplikasi. Menu "Alamat Server" dan "Pengaturan Bengkel" hanya tampil untuk admin (membuka halaman 2 dan 32).

**Kriteria selesai:** logout membersihkan sesi.

### [ ] T-24: Pengujian dan pemeriksaan alur
**Isi:**
- Tes unit sederhana: format rupiah, perhitungan total transaksi, pemotongan stok, aturan diagnosis mock, penjaga rute per peran.
- Uji manual alur utama dan catat hasilnya:
  1. Mekanik login, pilih gejala, lihat hasil, buat draft.
  2. Admin login, finalisasi, nota, stok berkurang.
  3. Admin melihat laporan.
- Pastikan setiap layar menangani kondisi memuat, kosong, dan error.
- Pemeriksaan tampilan: tidak ada strip putih di atas, bilah status transparan, status selalu disertai teks.
- Uji **lebar layar 320, 360, dan 412** dan **ukuran teks sistem 130%**: tidak ada overflow, teks tidak terpotong, tombol utama tidak tertutup keyboard.

**Kriteria selesai:** `flutter test` dan `flutter analyze` bersih, dan alur utama berjalan penuh.

Catatan hasil parsial: pemeriksaan otomatis telah dijalankan. Uji manual/perangkat
fisik belum dapat dilakukan karena tidak ada emulator atau perangkat Android
pada sesi ini; tugas tetap belum dicentang.

### [x] T-25: Rapikan dan serah terima ke Fase 2
**Isi:**
- Hapus kode mati dan layar uji sementara.
- Petakan tiap endpoint di `docs/PRD.md` bagian 9 ke layanan mock yang menggantikannya sebagai daftar serah terima untuk tugas `B-13` sampai `B-16`.
- Pastikan semua halaman di `docs/HALAMAN.md` yang termasuk fase 1 sudah dicentang.
- Perbarui `AGENTS.md` bagian 9 bila fase berubah.

**Kriteria selesai:** tidak ada layar yang memanggil mock secara langsung, dan setiap endpoint di kontrak punya padanan di layer service.

Catatan: halaman pada `docs/HALAMAN.md` sengaja tidak dicentang karena
persetujuan visual tetap menjadi hak pengguna. Status tugas tidak mengubah
persetujuan halaman.

---

## T-31: Kasir dan perubahan navigasi
**Status:** belum dicentang

- Tambah tab Kasir untuk admin dan mekanik.
- Pindahkan Katalog menjadi layar admin tanpa navigasi bawah.
- Simpan keranjang di Provider dan gunakan QtyStepper dengan batas stok.
- Perbarui alur Transaksi Baru, Draft Saya, dan hasil diagnosis agar membuka Kasir.
- Pastikan layout, dokumentasi, analyze, dan test tetap bersih.

---

# BAGIAN B: BACKEND (folder `bengkelpintar_api\` dan `bengkelpintar_backend\`)

Tugas `B-01` sampai `B-12` tidak menyentuh folder Flutter. Tugas `B-13` sampai `B-16` menyambungkan Flutter ke server dan **hanya boleh mengubah `bengkelpintar\lib\services\` dan satu baris di `main.dart`**, bukan layar.

## Ringkasan Blok

| Blok | Tugas | Isi |
|---|---|---|
| 8. Server dan data | B-01 sampai B-07 | Setup, PostgreSQL, login, data master, stok, transaksi, laporan |
| 9. Diagnosis dan kualitas | B-08, B-09 | Diagnosis tiruan, riwayat, tes |
| 10. Model | B-10, B-11 | Dataset, pelatihan, pemasangan model |
| 11. Operasional | B-12 | Backup dan pindah ke VPS |
| 12. Sambungan Flutter | B-13 sampai B-16 | Klien HTTP, ganti mock, error jaringan, uji di HP |

## Blok 8: Server dan Data

### [✔️] B-01: Setup server API
**Isi:**
- Folder `bengkelpintar_api\`, lingkungan `.venv`, `requirements.txt` (FastAPI, uvicorn, SQLAlchemy, driver PostgreSQL, pydantic, JWT, hashing password, pytest, httpx). Catat versi `scikit-learn` dan `numpy` yang akan dipakai (harus sama dengan `bengkelpintar_backend`).
- Struktur `app\` (`main.py`, `schemas.py`, `database.py`, `models_db.py`, `auth.py`).
- `.env` dan `.env.example` (`DATABASE_URL`, `JWT_SECRET`, `API_KEY`, `MODEL_DIR`). `.env` tidak masuk git.
- `GET /health` (tanpa login) mengembalikan `{ "status": "ok", "versi": "1.0" }`.

**Kriteria selesai:** server berjalan dengan `--host 0.0.0.0 --port 8000`, `/docs` terbuka, dan `/health` bisa dibuka dari browser HP di jaringan yang sama.

### [✔️] B-02: PostgreSQL, tabel, dan data awal
**Isi:**
- Pasang PostgreSQL di laptop, buat database dan pengguna khusus aplikasi. Port database tidak dibuka ke jaringan.
- Tabel di `models_db.py` sesuai `docs/PRD.md` bagian 10 (tanpa Alembic, dibuat lewat kode).
- Skrip data awal (seed) memakai **data baku `docs/DESIGN.md` bagian 16**: bengkel, 3 pengguna, 6 kategori, 12 produk, 9 jasa, 18 gejala, 10 kerusakan beserta penautan komponen dan jasa, 4 transaksi.

**Kriteria selesai:** tabel terbentuk, seed berjalan ulang tanpa duplikasi, dan total transaksi contoh benar (TRX-0105 Rp45.000, TRX-0104 Rp135.000, TRX-0103 Rp300.000, TRX-0102 Rp295.000).

### [✔️] B-03: Autentikasi dan peran
**Isi:**
- `POST /auth/login`, `GET /auth/me`, token JWT dengan masa berlaku, password di-hash.
- Pemeriksaan peran (admin, mekanik) dan pemeriksaan header `X-API-Key` pada semua endpoint kecuali `/auth/login` dan `/health`.
- `POST /auth/ganti-password` dan `POST /pengguna/{id}/reset-password` (admin).

**Kriteria selesai:** tes membuktikan mekanik mendapat 403 pada endpoint admin, request tanpa token mendapat 401, dan password lama ditolak setelah diganti.

### [✔️] B-04: Data master
**Isi:** endpoint daftar, tambah, ubah, dan nonaktifkan untuk kategori, produk, jasa, gejala, kerusakan (termasuk penautan komponen dan jasa terkait), pengguna, dan `GET/PUT /pengaturan-bengkel`, sesuai `docs/PRD.md` bagian 9. Data nonaktif tidak dihapus. Kategori yang masih dipakai produk tidak boleh dihapus.

**Kriteria selesai:** semua endpoint master sesuai kontrak, dan peran dibatasi di server.

### [ ] B-05: Stok
**Isi:** `POST /produk/{id}/stok` (penyesuaian manual dengan alasan), `GET /produk/{id}/mutasi`, stok tidak boleh negatif, penanda stok menipis (`stok_minimum`).

**Kriteria selesai:** penyesuaian tercatat sebagai mutasi dan stok baru benar (contoh: Busi NGK Standar 4 ditambah 10 menjadi 14).

### [ ] B-06: Transaksi
**Isi:**
- Buat dan ubah draft (`POST /transaksi`, `PUT /transaksi/{id}`), daftar dan detail. Mekanik hanya melihat dan mengubah draft miliknya. Nomor transaksi berurutan (`TRX-0105`).
- `POST /transaksi/{id}/finalisasi` (admin) **atomik dalam satu database transaction**: cek stok, ubah status, kurangi stok, catat mutasi, simpan metode bayar dan jumlah dibayar, hitung kembalian. Gagal satu berarti batal semua.
- Transaksi final tidak bisa diubah. `GET /transaksi/{id}/nota`.

**Kriteria selesai:** tes membuktikan finalisasi dengan stok kurang ditolak dan stok tidak berubah, dan finalisasi berhasil mengurangi stok tepat sesuai jumlah item.

### [ ] B-07: Laporan dan statistik
**Isi:** `GET /laporan/penjualan` per periode (hari ini, 7 hari, bulan ini, rentang kustom) hanya dari transaksi final, termasuk total, jumlah, rata-rata, penjualan per hari, dan produk atau jasa terlaris. `GET /diagnosis/statistik` (opsional).

**Kriteria selesai:** angka laporan cocok dengan data transaksi final di database.

## Blok 9: Diagnosis dan Kualitas

### [ ] B-08: Diagnosis tiruan dan riwayat
**Isi:**
- `POST /diagnosis/predict` memakai **aturan tiruan deterministik** (sama dengan mock Flutter di T-04) di balik antarmuka `Classifier`, supaya B-11 hanya mengganti isinya.
- Hasil digabung dengan data referensi: urgensi, solusi, estimasi waktu, komponen dan jasa terkait, dan **estimasi biaya dihitung dari harga di database dengan label "Perkiraan"**.
- Riwayat disimpan. `GET /diagnosis/riwayat` dan `/diagnosis/riwayat/{id}` (mekanik hanya miliknya).

**Kriteria selesai:** contoh dari `docs/PRD.md` bagian 9.3 menghasilkan respons dengan bentuk persis sama.

### [ ] B-09: Penanganan error dan tes
**Isi:** format error JSON yang seragam, validasi input, CORS, dan tes `pytest` untuk alur utama (login, diagnosis, draft, finalisasi, laporan). Periksa bahwa bentuk setiap respons cocok dengan `docs/PRD.md` bagian 9.

**Kriteria selesai:** `pytest` bersih dan alur utama lolos dari awal sampai akhir.

## Blok 10: Model

### [ ] B-10: Dataset dan pelatihan (`bengkelpintar_backend\`)
**Isi:**
- Lingkungan `.venv` dan `requirements.txt` dengan versi `scikit-learn` dan `numpy` **sama** dengan server.
- `dataset\dataset_motor.csv` (kolom gejala 0/1 dan label kerusakan) dari data nyata (wawancara mekanik, catatan servis, atau buku servis). **Jangan mengarang data.**
- `training\train_model.py`: pisah data latih dan uji (misalnya 80:20), latih Random Forest, hitung akurasi, precision, recall, F1, dan confusion matrix.
- Simpan `models\rf_model.pkl` dan `models\model_meta.json` (daftar kode gejala, daftar kode kelas, urutan fitur). Simpan laporan ke `training\hasil\`.

**Kriteria selesai:** hasil evaluasi berasal dari pelatihan nyata, dan daftar kode di `model_meta.json` cocok dengan kode gejala dan kerusakan di database.

### [ ] B-11: Pasang model ke API
**Isi:** implementasi `Classifier` memakai `rf_model.pkl` dan `model_meta.json` dari `MODEL_DIR`, dimuat **sekali** saat server menyala. Ubah gejala terpilih menjadi vektor 0/1 sesuai urutan di `model_meta.json`. Beri peringatan saat start jika `model_meta.json` tidak cocok dengan gejala di database.

**Kriteria selesai:** diagnosis memakai model asli, tingkat keyakinan berasal dari `predict_proba`, dan tes memastikan urutan fitur benar.

## Blok 11: Operasional

### [ ] B-12: Backup dan pindah ke VPS
**Isi:** skrip backup `pg_dump` dan langkah memulihkan, serta panduan singkat pindah ke VPS di `bengkelpintar_api\README.md` sesuai `docs/PRD.md` bagian 8.6 (HTTPS, `.env` produksi, port database tertutup, CORS dibatasi, batas percobaan login, build Flutter dengan `API_BASE_URL` baru).

**Kriteria selesai:** backup berhasil dipulihkan ke database kosong, dan panduan bisa diikuti dari awal sampai akhir.

## Blok 12: Sambungan Flutter ke API

**Prasyarat blok ini:** `T-05` dan `T-25` selesai, serta endpoint terkait di Bagian B sudah jadi. Tugas hanya mengubah `bengkelpintar\lib\services\` dan satu baris pendaftaran di `main.dart`.

### [ ] B-13: Klien HTTP di Flutter
**Isi:** klien dasar di `lib/services` yang membaca `API_BASE_URL` (dan alamat yang ditimpa admin), mengirim header `Authorization` dan `X-API-Key`, memakai batas waktu, dan memetakan kegagalan menjadi jenis error jaringan yang seragam. Prasyarat: B-01 dan B-03.

**Kriteria selesai:** klien bisa memanggil `/health` dan `/auth/login` dari HP ke server di laptop.

### [ ] B-14: Ganti service mock satu per satu
**Isi:** buat implementasi HTTP untuk tiap antarmuka service (Auth, Diagnosis, Produk, Jasa, Kategori, Gejala dan Kerusakan, Transaksi, Laporan, Pengguna, Pengaturan Bengkel), **satu service per langkah**, lalu daftarkan di `main.dart`. Antarmuka tidak berubah. Ganti tiap service hanya setelah endpoint terkait selesai sesuai kontrak di `docs/PRD.md` bagian 9.

**Kriteria selesai:** semua layar berjalan dengan server asli tanpa mengubah `lib/features`.

### [ ] B-15: Penanganan error jaringan
**Isi:** server tidak terjangkau menampilkan layar Server Tidak Terjangkau (halaman 33), token kedaluwarsa kembali ke Login, dan 403 menampilkan Akses Ditolak (halaman 26), memakai pesan baku `docs/DESIGN.md` bagian 17.5. Navigasi dipicu lewat handler yang didaftarkan di `main.dart`, bukan dengan mengubah layar.

**Kriteria selesai:** mematikan server atau menghapus token memunculkan tampilan yang benar di setiap layar berdata.

### [ ] B-16: Uji alur utama di HP dengan server asli
**Isi:** uji di dua HP pada jaringan yang sama: mekanik login, diagnosis, membuat draft. Admin membuka transaksi, finalisasi, melihat nota, lalu laporan. Catat hasil uji dan temuan di bawah tugas ini.

**Kriteria selesai:** alur penuh berjalan di dua HP dan data keduanya sama.

---

## Urutan dan Ketergantungan

```
BAGIAN A (frontend, tidak menunggu siapa pun)
T-01 -> T-02 [gerbang] -> T-03
          \
           T-04 -> T-05 -> T-06 -> T-07 -> T-08 [gerbang]
                                              |
   Diagnosis (T-09 -> T-10 [gerbang] -> T-11 -> T-12)
   POS (T-13 -> T-14 -> T-15), Katalog (T-16, T-17, T-18)
   Admin (T-19, T-20, T-21, T-22)
   Tambahan (T-26, T-27, T-28, T-29, T-30)
   Penutup (T-23 -> T-24 -> T-25)

BAGIAN B (backend, berjalan terpisah)
B-01 -> B-02 -> B-03 -> B-04 -> B-05 -> B-06 -> B-07
                                  \-> B-08 -> B-09
Dataset (dikumpulkan sejak awal) -> B-10 -> B-11 -> B-12

SAMBUNGAN (butuh T-05, T-25, dan endpoint terkait)
B-13 -> B-14 -> B-15 -> B-16
```

Catatan:
- T-13 membutuhkan katalog (T-16, T-17) untuk pemilih item. Jika perlu, kerjakan T-16 dan T-17 sebelum T-13.
- T-30 (kategori) sebaiknya sebelum T-16, dan T-26 (pengaturan bengkel) sebelum T-15.
- T-28 membutuhkan sakelar simulasi gagal di service mock (T-05).
- B-14 dikerjakan per service, dimulai setelah endpoint terkait selesai. Tidak perlu menunggu seluruh Bagian B.
- Dataset sebaiknya mulai dikumpulkan sejak sekarang, karena B-10 bergantung padanya.

## Di Luar Tugas Saat Ini

- Mode offline-first, pembayaran digital, printer Bluetooth, iOS.
- Penyetelan lanjutan model dan fitur di luar `docs/PRD.md`.
