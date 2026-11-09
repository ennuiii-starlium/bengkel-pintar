from typing import Protocol

from app.services.aturan_tiruan import AturanTiruan


class Classifier(Protocol):
    """Antarmuka yang dipakai layanan diagnosis. Model Random Forest asli (B-11) cukup
    menyediakan tiga hal ini, dengan urutan gejala dan kelas yang sama seperti saat pelatihan."""

    kode_gejala: tuple[str, ...]
    kode_kerusakan: tuple[str, ...]

    def predict_proba(self, vektor: list[int]) -> list[float]: ...


_pengklasifikasi: Classifier | None = None


def ambil_pengklasifikasi() -> Classifier:
    """Dipasang sebagai dependency FastAPI, sehingga mudah diganti (B-11) atau ditimpa di tes."""
    global _pengklasifikasi
    if _pengklasifikasi is None:
        _pengklasifikasi = AturanTiruan()
    return _pengklasifikasi
