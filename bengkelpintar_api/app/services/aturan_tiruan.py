"""Pengklasifikasi TIRUAN untuk pengembangan, sampai model Random Forest asli tersedia (B-10, B-11).

PENTING:
- Bobot di bawah disusun manual dari nama gejala dan kerusakan. Ini BUKAN data penelitian,
  BUKAN hasil pelatihan, dan belum divalidasi mekanik.
- Keluaran tidak boleh dikutip sebagai akurasi, evaluasi, atau hasil model di skripsi.
- Antarmukanya sengaja sama dengan model asli (daftar gejala, daftar kelas, predict_proba),
  sehingga B-11 cukup mengganti isinya.

Perilaku yang ditiru dari Random Forest: banyak "pohon" yang masing-masing hanya melihat
sebagian gejala, tiap pohon memberi distribusi kelas, lalu distribusi dirata-rata sehingga
keluaran berupa probabilitas yang jumlahnya 1. Tidak ada angka acak: hasilnya selalu sama
untuk masukan yang sama.
"""

import hashlib
import math

KODE_GEJALA = tuple(f"G{n:02d}" for n in range(1, 19))
KODE_KERUSAKAN = tuple(f"K{n:02d}" for n in range(1, 11))

# kerusakan -> {gejala: kekuatan hubungan 0..1}
BOBOT: dict[str, dict[str, float]] = {
    "K01": {"G01": 0.9, "G03": 0.7, "G04": 0.5, "G09": 0.6, "G18": 0.7, "G02": 0.3, "G05": 0.3},
    "K02": {"G01": 0.6, "G03": 0.6, "G05": 0.9, "G09": 0.8, "G18": 0.9, "G02": 0.5, "G04": 0.3},
    "K03": {"G01": 0.5, "G07": 1.0, "G08": 1.0, "G16": 1.0},
    "K04": {"G10": 1.0},
    "K05": {"G12": 1.0, "G03": 0.4, "G09": 0.2},
    "K06": {"G11": 1.0, "G13": 0.6, "G03": 0.3},
    "K07": {"G03": 0.6, "G05": 0.7, "G09": 0.7, "G18": 0.4, "G06": 0.2},
    "K08": {"G17": 1.0, "G15": 0.9, "G06": 0.8, "G14": 0.8, "G04": 0.4},
    "K09": {"G02": 0.9, "G01": 0.6, "G18": 0.6},
    "K10": {"G01": 0.7, "G02": 0.6, "G03": 0.5, "G18": 0.5},
}


def _termasuk(pohon: int, kode: str, fraksi: float) -> bool:
    """Penentuan subset gejala per pohon, tetap dan tidak bergantung versi Python."""
    byte = hashlib.sha256(f"{pohon}:{kode}".encode()).digest()[0]
    return byte / 255 < fraksi


class AturanTiruan:
    kode_gejala = KODE_GEJALA
    kode_kerusakan = KODE_KERUSAKAN

    def __init__(self, jumlah_pohon: int = 40, fraksi_gejala: float = 0.7, suhu: float = 0.3, penalti: float = 0.15):
        self.suhu = suhu
        self.penalti = penalti
        self._subset = [
            {k for k in self.kode_gejala if _termasuk(p, k, fraksi_gejala)} for p in range(jumlah_pohon)
        ]

    def predict_proba(self, vektor: list[int]) -> list[float]:
        if len(vektor) != len(self.kode_gejala):
            raise ValueError("Panjang vektor gejala tidak sama dengan daftar gejala model.")
        ada = {k for k, v in zip(self.kode_gejala, vektor) if v}
        total = [0.0] * len(self.kode_kerusakan)
        for subset in self._subset:
            terlihat = ada & subset
            skor = []
            for kelas in self.kode_kerusakan:
                bobot = BOBOT[kelas]
                skor.append(sum(bobot.get(g, -self.penalti) for g in terlihat))
            puncak = max(skor)
            eksp = [math.exp((s - puncak) / self.suhu) for s in skor]
            jumlah = sum(eksp)
            for i, e in enumerate(eksp):
                total[i] += e / jumlah
        return [t / len(self._subset) for t in total]
