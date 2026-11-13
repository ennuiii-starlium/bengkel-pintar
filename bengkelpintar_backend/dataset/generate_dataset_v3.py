#!/usr/bin/env python3
"""
Generator dataset v3 - motor_injeksi (SINTETIS, bukan data bengkel).

Cara kerja:
1. Baris asli (W001-W360) dipertahankan apa adanya, hanya jenis_motor -> 'motor_injeksi'.
2. Profil peluang gejala per kelas = frekuensi empiris 360 baris asli (dismoothing),
   + penyesuaian kecil yang punya dasar sumber (lihat ADJUST).
3. Baris baru = sampel Bernoulli per gejala dari profil itu, ditambah "silang-gejala"
   (overlap) pada sebagian baris sesuai kebingungan diagnosis yang DITULIS di sumber.
4. Semua vektor gejala baru unik terhadap seluruh dataset.

Seed tetap -> hasil dapat direproduksi.
"""
import numpy as np, pandas as pd, sys

SEED = 20261030
PER_CLASS_TARGET = 120          # 9 kelas x 120 = 1080 baris
P_CROSSTALK = 0.15              # ASUMSI, bukan hasil pengukuran
NOISE_FLOOR = 0.035             # peluang gejala non-khas (ASUMSI, dari kisaran data asli)
SIGNATURE_MIN = 0.15            # gejala dgn frekuensi asli >= ini dianggap khas kelas

IN = "/mnt/user-data/uploads/"
OUT = "/mnt/user-data/outputs/"

# ---- penyesuaian profil yang punya dasar sumber (kode sumber ada di daftar_sumber_v3.csv)
ADJUST = {
    # S36,S37: akselerasi lemot/berat disebut sebagai gejala utama per CVT lemah (asli: 0.30)
    ("K4", "G04"): 0.55,
    # S26,S27: busi lemah -> sulit hidup saat mesin dingin/pagi hari (asli: 0.05)
    ("K1", "G28"): 0.30,
}

# ---- kebingungan diagnosis yang dinyatakan sumber (kelas asal -> kelas yang mirip)
CONFUSABLE = {
    "K1": ["K7", "K8", "K9"],   # S08 (busi sekarat dikira hilang kompresi), S20, S23
    "K8": ["K1", "K9", "K6"],   # S20 (fuel pump dikira aki/busi/injektor/TB)
    "K9": ["K1", "K8"],         # S23 (TB dikira busi/injektor/ISC)
    "K7": ["K1", "K8"],
    "K2": ["K3", "K4"],         # gejala CVT saling tumpang tindih
    "K3": ["K2", "K4"],
    "K4": ["K3", "K2"],
    "K5": ["K6"],               # starter vs aki
    "K6": ["K5", "K8"],         # S39 (aki lemah dibiarkan -> fuel pump)
}

# ---- sumber baru S26.. (semua URL muncul di hasil pencarian pada 2026-10-30)
NEW_SOURCES = [
 # (kelas_terkait, penerbit, judul, tanggal_terbit_yg_terlihat, url)
 ("K1","detikOto","Kapan Waktu yang Tepat Ganti Busi Motor?","", "https://oto.detik.com/tips-and-tricks-motor/d-8249623/kapan-waktu-yang-tepat-ganti-busi-motor"),
 ("K1","GridOto","Tips Perbaikan Motor Bekas, Begini Ciri-ciri Busi Motor Minta Diganti","2022-04-01","https://www.gridoto.com/read/223210693/tips-perbaikan-motor-bekas-begini-ciri-ciri-busi-motor-minta-diganti"),
 ("K1","Carmudi","Busi Motor Matic: Fungsi, Ciri Kerusakan, dan Waktu Ganti yang Tepat","","https://www.carmudi.co.id/journal/busi-motor-matic-fungsi-ciri-kerusakan-dan-waktu-ganti-yang-tepat/"),
 ("K1","GridOto","Sebelum Lakukan Perjalanan Jauh, Begini Ciri Busi Motor Mau Mati","2022-04-28","https://www.gridoto.com/read/223256636/sebelum-lakukan-perjalanan-jauh-begini-ciri-busi-motor-mau-mati"),
 ("K2","GridOto","Ini Ciri V-belt Motor Matic Yang Harus Diganti, Awas Putus di Jalan","2021-09-13","https://www.gridoto.com/read/222887329/ini-ciri-v-belt-motor-matic-yang-harus-diganti-awas-putus-di-jalan?page=all"),
 ("K2","GridOto","Jangan Dipakai Perjalanan Jauh, Ini Ciri V-Belt Motor Matic Aus","2022-04-13","https://www.gridoto.com/amp/223231670/jangan-dipakai-perjalanan-jauh-ini-ciri-v-belt-motor-matic-aus?page=all"),
 ("K2","Otomotifnet","Masih Sedikit yang Tahu, Ini Tanda-tanda V-Belt Motor Matik Mau Putus","2024-04-28","https://otomotifnet.gridoto.com/read/234074668/masih-sedikit-yang-tahu-ini-tanda-tanda-v-belt-motor-matik-mau-putus?page=all"),
 ("K3","GridOto","Jangan Diabaikan, Ini Tanda Roller di CVT Motor Matic Mulai Aus","2021-05-20","https://www.gridoto.com/read/222700636/jangan-diabaikan-ini-tanda-roller-di-cvt-motor-matic-mulai-aus"),
 ("K3","GridOto","Inilah Beberapa Dampak Membiarkan Roller Motor Matic Peyang","2025-05-11","https://www.gridoto.com/read/224249825/inilah-beberapa-dampak-membiarkan-roller-motor-matic-peyang?page=all"),
 ("K3","GridOto","Ternyata Ini Penyebab Tarikan Mesin Motor Matic Jadi Lemot dan Berat","2021-06-29","https://www.gridoto.com/read/222763700/ternyata-ini-penyebab-tarikan-mesin-motor-matic-jadi-lemot-dan-berat?page=all"),
 ("K4","GridOto","Sering Dirasakan, Ini Ciri-ciri Per CVT Motor Matic Minta Diganti","2025-07-02","https://www.gridoto.com/read/224268487/sering-dirasakan-ini-ciri-ciri-per-cvt-motor-matic-minta-diganti?page=all"),
 ("K4","GridOto","Ternyata Ini Sebabnya Akselerasi Motor Matic Lama-lama Makin Lemot","2025-08-18","https://www.gridoto.com/read/224286413/ternyata-ini-sebabnya-akselerasi-motor-matic-lama-lama-makin-lemot?page=all"),
 ("K6","JawaPos","Motor Susah Distarter? Jangan Panik, Cek 7 Bagian Ini Sebelum Bawa ke Bengkel","2026-09-18","https://www.jawapos.com/oto-dan-tekno/2609180309/motor-susah-distarter-jangan-panik-cek-7-bagian-ini-sebelum-bawa-ke-bengkel"),
 ("K6","GridOto","Awas! Ini Dampak Negatif Membiarkan Aki Lemah di Motor Injeksi","2021-09-16","https://www.gridoto.com/amp/222893413/awas-ini-dampak-negatif-membiarkan-aki-lemah-di-motor-injeksi?page=all"),
 ("K7","GridOto","Awas! Begini Ciri Ring Piston Honda Vario 125 Old Mulai Lemah","2023-11-29","https://www.gridoto.com/amp/223953380/awas-begini-ciri-ring-piston-honda-vario-125-old-mulai-lemah?page=all"),
 ("K7","GridOto","Banyak yang Gak Sadar, Ini Penyebab Utama Mesin Motor Hilang Kompresi","","https://www.gridoto.com/read/223247053/banyak-yang-gak-sadar-ini-penyebab-utama-mesin-motor-hilang-kompresi?page=all"),
 ("K7","Antara","Knalpot motor mengeluarkan asap putih? Ini penyebabnya","","https://otomotif.antaranews.com/berita/5711171/knalpot-motor-mengeluarkan-asap-putih-ini-penyebabnya"),
 ("K7","GridOto","Tips Beli Motor Bekas, Begini Ciri-ciri Ring Piston Mulai Lemah","2021-12-04","https://www.gridoto.com/read/223025953/tips-beli-motor-bekas-begini-ciri-ciri-ring-piston-mulai-lemah?page=all"),
 ("K8","GridOto","Jarang Disadari Pemilik, Ini Ciri Fuel Pump Motor Injeksi Mulai Lemah","2022-05-11","https://www.gridoto.com/read/223275681/jarang-disadari-pemilik-ini-ciri-fuel-pump-motor-injeksi-mulai-lemah?page=all"),
 ("K8","GridOto","Bisa Bikin Motor Mogok, Ini Ciri Fuel Pump Motor Injeksi Minta Diganti","2023-05-04","https://www.gridoto.com/read/223774762/bisa-bikin-motor-mogok-ini-ciri-fuel-pump-motor-injeksi-minta-diganti"),
 ("K8","Autofun","3 Tanda Fuel Pump Motor Lemah, Dari Brebet Sampai Mogok","","https://www.autofun.co.id/berita-motor/3-tanda-fuel-pump-motor-lemah-dari-brebet-sampai-mogok-79604"),
 ("K8","JawaPos","Waspadai 6 Tanda Fuel Pump Motor Anda Mulai Rusak","","https://www.jawapos.com/oto-dan-tekno/2510290301/waspadai-6-tanda-fuel-pump-motor-anda-mulai-rusak"),
 ("K9","GridOto","Throttle Body Motor Injeksi Dipenuhi Kotoran? Ini Beberapa Gejalanya","2020-06-29","https://www.gridoto.com/read/222218452/throttle-body-motor-injeksi-dipenuhi-kotoran-ini-beberapa-gejalanya?page=all"),
 ("K9","GridOto","Ini Gejala Yang Muncul Saat Throttle Body Di Motor Bekas Sudah kotor","2026-02-16","https://www.gridoto.com/read/224353683/ini-gejala-yang-muncul-saat-throttle-body-di-motor-bekas-sudah-kotor"),
 ("K9","Antara","9 penyebab motor injeksi mati mendadak saat berhenti","2026-10-24","https://otomotif.antaranews.com/berita/5808827/9-penyebab-motor-injeksi-mati-mendadak-saat-berhenti"),
 ("K9","Carmudi","Throttle Body Motor, Jantung Pernapasan yang Bisa Mengancam Performa","","https://www.carmudi.co.id/journal/throttle-body-motor-jantung-pernapasan-yang-bisa-mengancam-performa/amp/"),
]
# tautan gejala <- sumber baru (hanya yang isinya benar-benar terlihat di hasil pencarian).
# Nilai = urutan 1-based di NEW_SOURCES (no.1 = S26, no.26 = S51)
SYMPTOM_LINKS = {
 "G01":[1,2,3,4,20], "G03":[23], "G04":[1,2,7,10,11,12,15,20,23,24,26],
 "G05":[1,3,4,21,25,26], "G06":[1,3,7,24,26], "G07":[4,23,24,25,26],
 "G08":[22], "G09":[7,9], "G10":[8], "G12":[6,9], "G15":[13], "G16":[13],
 "G21":[17,18], "G22":[15,16,17,18], "G28":[1,2],
}

# titik-titik sumber asli S01-S25: (judul, penerbit, tanggal, status_akses)
OLD_META = {
 "S01":("Cara Mengetahui V-Belt Motor Matic Aus Sebelum Putus Di Jalan","GridOto","2022-05-06",1),
 "S02":("Perlu Tahu, Ini Ciri-Ciri V-Belt Motor Matic Mau Putus, Wajib Diganti","Otomotifnet","2024-04-27",1),
 "S03":("(judul belum diverifikasi)","detikOto","",0),
 "S04":("Tips Servis CVT Motor Matic, Segini Usia Pemakaian Roller di Motor","GridOto","2022-10-21",1),
 "S05":("Pengertian CVT, Fungsi, dan Ciri-Ciri Kerusakannya pada Motor Matic","detikOto","2023-11-28",1),
 "S06":("(judul belum diverifikasi)","dayaauto.co.id","",0),
 "S07":("Kenali Gejala dan Ciri Per CVT Motor Matic Rusak, Biar Gak Merembet Kemana-Mana!","Autofun","",1),
 "S08":("Ciri Busi Motor Akan Mati, Sering Muncul Tapi Diabaikan Bikers","GridOto","2025-05-05",1),
 "S09":("Gejala Ini Bakal Muncul Kalau Busi Motor Minta Diganti","GridOto","2018-10-25",1),
 "S10":("Ketahui 5 Ciri-Ciri Busi Motor Harus Diganti!","Moladin","",1),
 "S11":("(judul belum diverifikasi)","Batam Pos","",0),
 "S12":("Kenapa motor susah distarter? Ini penyebab yang sering terjadi","Antara","",1),
 "S13":("Inilah 8 penyebab motor tidak mau distarter","Antara","",1),
 "S14":("Ini 8 Penyebab Motor Sulit Distarter","kumparanOTO","",1),
 "S15":("5 Penyebab Motor Injeksi Susah Dihidupkan dan Solusinya","Moladin","",1),
 "S16":("Kenali 9 Ciri-ciri Motor Turun Mesin dan Penyebabnya","Moladin","",1),
 "S17":("Jelang Mudik Lebaran, Ini Ciri Ring Piston Motor Minta Diganti","GridOto","2025-03-18",1),
 "S18":("Volume Oli Mesin Motor Berkurang Banyak? Ini Beberapa Penyebabnya","GridOto","",1),
 "S19":("Tes Kompresi Mesin, Apaan Sih?","detikOto","2011-06-07",1),
 "S20":("Ciri-Ciri Fuel Pump Motor Mulai Rusak, Jangan Tunggu Sampai Mogok Mendadak","Mobil123","",1),
 "S21":("Kenali Gejala Fuel Pump Motor Injeksi Sudah Mulai Lemah","Carmudi","",1),
 "S22":("Cara Mengetahui Bedanya Injektor Motor Kotor dengan Injektor Rusak","GridOto","2021-04-14",1),
 "S23":("Throttle Body Kotor Bikin Tarikan Motor Berat, Ini Penyebab, Gejala, dan Cara Mengatasinya","Autofun","",1),
 "S24":("(judul belum diverifikasi)","GridOto","",0),
 "S25":("7 Penyebab Motor Matic Tiba-tiba Mati di Jalan","JawaPos","",1),
}

CVT_SYMPTOMS = {"G09","G10","G11","G12","G13","G30","G31"}
CVT_CLASSES = {"K2","K3","K4"}


def main():
    rng = np.random.default_rng(SEED)
    d = pd.read_csv(IN + "dataset_v2_matic_injeksi.csv")
    kelas = pd.read_csv(IN + "daftar_kelas_v2.csv")
    gejala = pd.read_csv(IN + "daftar_gejala_v2.csv")
    G = [c for c in d.columns if c.startswith("G")]
    classes = sorted(d["kelas"].unique())

    # ---------- tabel sumber
    old_url = {}
    for df in (kelas, gejala):
        for r in df.itertuples():
            for c, u in zip(r.kode_sumber.split(";"), r.url_sumber.split(";")):
                old_url[c.strip()] = u.strip()
    rows = []
    for c in sorted(old_url):
        t, p, tgl, ok = OLD_META[c]
        rows.append([c, "asli_v2", p, t, tgl, old_url[c],
                     "ditemukan_di_hasil_pencarian_2026-10-30" if ok else "BELUM_TERVERIFIKASI_perlu_cek_manual"])
    new_code = {}
    for i, (kls, p, t, tgl, u) in enumerate(NEW_SOURCES, start=1):
        code = f"S{25+i:02d}"
        new_code[i] = code
        rows.append([code, "tambahan_v3", p, t, tgl, u, "ditemukan_di_hasil_pencarian_2026-10-30"])
    src = pd.DataFrame(rows, columns=["kode_sumber","asal","penerbit","judul","tanggal_terbit_terlihat","url","status_akses"])
    src.to_csv(OUT + "daftar_sumber_v3.csv", index=False)
    url_of = dict(zip(src.kode_sumber, src.url))

    # ---------- kelas v3
    add_by_class = {}
    for i, (kls, *_rest) in enumerate(NEW_SOURCES, start=1):
        add_by_class.setdefault(kls, []).append(new_code[i])
    k3 = kelas.copy()
    ks, ku = [], []
    for r in k3.itertuples():
        codes = r.kode_sumber.split(";") + add_by_class.get(r.kode_kelas, [])
        ks.append(";".join(codes)); ku.append("; ".join(url_of[c] for c in codes))
    k3["kode_sumber"], k3["url_sumber"] = ks, ku
    k3["cakupan"] = k3.kode_kelas.map(lambda k: "hanya matic (CVT)" if k in CVT_CLASSES else "semua motor injeksi")
    k3.to_csv(OUT + "daftar_kelas_v3.csv", index=False)

    # ---------- gejala v3
    g3 = gejala.copy()
    gs, gu = [], []
    for r in g3.itertuples():
        codes = r.kode_sumber.split(";") + [new_code[i] for i in SYMPTOM_LINKS.get(r.kode_gejala, [])]
        codes = list(dict.fromkeys(codes))
        gs.append(";".join(codes)); gu.append("; ".join(url_of[c] for c in codes))
    g3["kode_sumber"], g3["url_sumber"] = gs, gu
    g3["cakupan"] = g3.kode_gejala.map(lambda x: "hanya matic (CVT)" if x in CVT_SYMPTOMS else "semua motor injeksi")
    g3.to_csv(OUT + "daftar_gejala_v3.csv", index=False)

    # ---------- profil peluang
    emp = d.groupby("kelas")[G].mean()
    prof = emp.copy()
    for c in classes:
        for g in G:
            e = emp.loc[c, g]
            prof.loc[c, g] = e if e >= SIGNATURE_MIN else 0.5 * e + 0.5 * NOISE_FLOOR
    for (c, g), v in ADJUST.items():
        prof.loc[c, g] = v

    # ---------- generator
    d = d.copy(); d["jenis_motor"] = "motor_injeksi"
    seen = set(d[G].astype(int).astype(str).agg("".join, axis=1))
    new_rows, next_id = [], len(d) + 1
    for c in classes:
        n_have = int((d["kelas"] == c).sum())
        need = PER_CLASS_TARGET - n_have
        made, tries = 0, 0
        p = prof.loc[c].values
        while made < need:
            tries += 1
            if tries > 200000: raise RuntimeError("gagal membuat baris unik untuk " + c)
            v = (rng.random(len(G)) < p).astype(int)
            tag = ""
            if rng.random() < P_CROSSTALK:
                other = rng.choice(CONFUSABLE[c])
                po = prof.loc[other].values.copy()
                po[v == 1] = 0
                sig = po * (po >= SIGNATURE_MIN)
                if sig.sum() > 0:
                    j = rng.choice(len(G), p=sig / sig.sum()); v[j] = 1; tag = f";overlap={other}"
            while v.sum() < 2:
                q = p.copy(); q[v == 1] = 0
                v[rng.choice(len(G), p=q / q.sum())] = 1
            key = "".join(map(str, v))
            if key in seen: continue
            seen.add(key); made += 1
            rec = {"id_kasus": f"W{next_id:03d}", "jenis_motor": "motor_injeksi"}
            rec.update({g: int(x) for g, x in zip(G, v)})
            rec.update({"kelas": c, "sumber_data": "WEB_SINTETIS", "status_verifikasi": "belum_diverifikasi",
                        "id_mekanik": np.nan, "tanggal_verifikasi": np.nan, "catatan": "ekspansi_v3" + tag})
            new_rows.append(rec); next_id += 1
    out = pd.concat([d, pd.DataFrame(new_rows)], ignore_index=True)[d.columns]
    out.to_csv(OUT + "dataset_v3_motor_injeksi.csv", index=False)
    print("selesai:", out.shape, out["kelas"].value_counts().to_dict())


if __name__ == "__main__":
    main()
