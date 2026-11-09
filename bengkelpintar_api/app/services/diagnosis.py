import logging

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models_db import Gejala, Kerusakan, Pengguna, RiwayatDiagnosis
from app.schemas import (
    EstimasiBiayaOut,
    GejalaOut,
    HasilDiagnosisOut,
    JasaTerkaitOut,
    KerusakanPrediksiOut,
    KomponenTerkaitOut,
)
from app.services.classifier import Classifier
from app.util import ke_wib

log = logging.getLogger("bengkelpintar.diagnosis")

JUMLAH_KEMUNGKINAN_LAIN = 2
KETERANGAN_URGENSI = {
    "rendah": "Aman dipakai, cek saat servis rutin",
    "sedang": "Masih bisa dipakai, segera cek",
    "tinggi": "Segera perbaiki, jangan dipakai",
}


def hitung_estimasi_biaya(komponen: list[KomponenTerkaitOut], jasa: list[JasaTerkaitOut]) -> EstimasiBiayaOut:
    total_jasa = sum(j.harga for j in jasa)
    harga = [k.harga for k in komponen]
    return EstimasiBiayaOut(
        min=total_jasa + (min(harga) if harga else 0),
        max=total_jasa + sum(harga),
        keterangan="Perkiraan",
    )


def _muat_gejala(db: Session, ids: list[int]) -> list[Gejala]:
    unik = sorted(set(ids))
    ditemukan = {g.id: g for g in db.scalars(select(Gejala).where(Gejala.id.in_(unik)))}
    hilang = [i for i in unik if i not in ditemukan]
    if hilang:
        raise HTTPException(status_code=400, detail=f"Gejala dengan id {', '.join(map(str, hilang))} tidak ditemukan.")
    for g in ditemukan.values():
        if not g.aktif:
            raise HTTPException(status_code=400, detail=f"Gejala '{g.nama}' sudah nonaktif.")
    return [ditemukan[i] for i in unik]


def jalankan(db: Session, pengguna: Pengguna, gejala_ids: list[int], pengklasifikasi: Classifier) -> HasilDiagnosisOut:
    gejala = _muat_gejala(db, gejala_ids)

    dikenal = set(pengklasifikasi.kode_gejala)
    tidak_dikenal = [g.kode for g in gejala if g.kode not in dikenal]
    if tidak_dikenal:
        log.warning("Gejala %s tidak dikenal model; diabaikan. Latih ulang model bila gejala berubah.", tidak_dikenal)
    terpilih = {g.kode for g in gejala}
    vektor = [1 if kode in terpilih else 0 for kode in pengklasifikasi.kode_gejala]
    if not any(vektor):
        raise HTTPException(status_code=400, detail="Gejala yang dipilih belum dikenali model diagnosis.")

    peluang = dict(zip(pengklasifikasi.kode_kerusakan, pengklasifikasi.predict_proba(vektor)))
    urutan = {kode: i for i, kode in enumerate(pengklasifikasi.kode_kerusakan)}
    referensi = {
        k.kode: k
        for k in db.scalars(
            select(Kerusakan)
            .where(Kerusakan.kode.in_(peluang), Kerusakan.aktif.is_(True))
            .options(selectinload(Kerusakan.komponen), selectinload(Kerusakan.jasa))
        )
    }
    hilang = [kode for kode in peluang if kode not in referensi]
    if hilang:
        log.warning("Kelas model %s tidak ada atau nonaktif di database; dikeluarkan.", hilang)
    if not referensi:
        raise HTTPException(status_code=503, detail="Diagnosis belum siap: data kerusakan tidak tersedia.")
    jumlah = sum(peluang[kode] for kode in referensi)
    kandidat = sorted(
        ((kode, peluang[kode] / jumlah) for kode in referensi),
        key=lambda x: (-x[1], urutan[x[0]]),
    )

    def prediksi(kode: str, nilai: float) -> KerusakanPrediksiOut:
        return KerusakanPrediksiOut(id=referensi[kode].id, nama=referensi[kode].nama, keyakinan=round(nilai, 2))

    utama_kode, utama_nilai = kandidat[0]
    lain = [
        prediksi(kode, nilai)
        for kode, nilai in kandidat[1 : 1 + JUMLAH_KEMUNGKINAN_LAIN]
        if round(nilai, 2) >= 0.01
    ]
    ref = referensi[utama_kode]
    komponen = [
        KomponenTerkaitOut(produk_id=p.id, nama=p.nama, harga=p.harga)
        for p in sorted(ref.komponen, key=lambda x: x.id)
        if p.aktif
    ]
    jasa = [
        JasaTerkaitOut(jasa_id=j.id, nama=j.nama, harga=j.harga)
        for j in sorted(ref.jasa, key=lambda x: x.id)
        if j.aktif
    ]

    riwayat = RiwayatDiagnosis(
        pengguna_id=pengguna.id,
        gejala=[GejalaOut.model_validate(g, from_attributes=True).model_dump() for g in gejala],
        hasil={},
        keyakinan=round(utama_nilai, 2),
    )
    db.add(riwayat)
    db.flush()
    db.refresh(riwayat)
    hasil = HasilDiagnosisOut(
        riwayat_id=riwayat.id,
        kerusakan_utama=prediksi(utama_kode, utama_nilai),
        kemungkinan_lain=lain,
        urgensi=ref.urgensi,
        urgensi_keterangan=KETERANGAN_URGENSI.get(ref.urgensi, ""),
        solusi=ref.solusi,
        estimasi_waktu_menit=ref.estimasi_waktu_menit,
        komponen_terkait=komponen,
        jasa_terkait=jasa,
        estimasi_biaya=hitung_estimasi_biaya(komponen, jasa),
        waktu=ke_wib(riwayat.waktu),
    )
    riwayat.hasil = hasil.model_dump(mode="json")
    db.commit()
    return hasil
