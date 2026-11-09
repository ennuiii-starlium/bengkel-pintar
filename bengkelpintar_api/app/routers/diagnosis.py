from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import Pengguna, RiwayatDiagnosis
from app.schemas import (
    DiagnosisRequest,
    HasilDiagnosisOut,
    RiwayatDiagnosisOut,
    StatistikDiagnosisItemOut,
    StatistikDiagnosisOut,
)
from app.services import diagnosis as layanan
from app.services.classifier import Classifier, ambil_pengklasifikasi
from app.util import IdPath, ke_wib

router = APIRouter(tags=["Diagnosis"])


def _keluar(riwayat: RiwayatDiagnosis, nama_pengguna: str) -> RiwayatDiagnosisOut:
    return RiwayatDiagnosisOut(
        id=riwayat.id,
        pengguna_id=riwayat.pengguna_id,
        pengguna_nama=nama_pengguna,
        gejala=riwayat.gejala,
        hasil=riwayat.hasil,
        keyakinan=riwayat.keyakinan,
        waktu=ke_wib(riwayat.waktu),
    )


@router.post("/diagnosis/predict", response_model=HasilDiagnosisOut)
def prediksi(
    data: DiagnosisRequest,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
    pengklasifikasi: Classifier = Depends(ambil_pengklasifikasi),
):
    return layanan.jalankan(db, pengguna, data.gejala_ids, pengklasifikasi)


@router.get("/diagnosis/riwayat", response_model=list[RiwayatDiagnosisOut])
def daftar_riwayat(
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    kueri = (
        select(RiwayatDiagnosis, Pengguna.nama)
        .join(Pengguna, Pengguna.id == RiwayatDiagnosis.pengguna_id)
        .order_by(RiwayatDiagnosis.waktu.desc(), RiwayatDiagnosis.id.desc())
    )
    if pengguna.peran != "admin":
        kueri = kueri.where(RiwayatDiagnosis.pengguna_id == pengguna.id)
    return [_keluar(r, nama) for r, nama in db.execute(kueri).all()]


@router.get("/diagnosis/riwayat/{riwayat_id}", response_model=RiwayatDiagnosisOut)
def detail_riwayat(
    riwayat_id: IdPath,
    pengguna: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    baris = db.execute(
        select(RiwayatDiagnosis, Pengguna.nama)
        .join(Pengguna, Pengguna.id == RiwayatDiagnosis.pengguna_id)
        .where(RiwayatDiagnosis.id == riwayat_id)
    ).first()
    if baris is None or (pengguna.peran != "admin" and baris[0].pengguna_id != pengguna.id):
        raise HTTPException(status_code=404, detail="Riwayat diagnosis tidak ditemukan.")
    return _keluar(*baris)


@router.get("/diagnosis/statistik", response_model=StatistikDiagnosisOut)
def statistik_diagnosis(
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    nama = RiwayatDiagnosis.hasil["kerusakan_utama"]["nama"].astext
    jumlah = func.count()
    baris = db.execute(
        select(nama, jumlah).where(nama.is_not(None)).group_by(nama).order_by(jumlah.desc(), nama.asc())
    ).all()
    total = sum(j for _, j in baris)
    return StatistikDiagnosisOut(
        total=total,
        items=[StatistikDiagnosisItemOut(nama=n, jumlah=j, persentase=j / total) for n, j in baris],
    )
