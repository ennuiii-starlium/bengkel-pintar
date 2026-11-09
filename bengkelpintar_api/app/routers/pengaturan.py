from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app import auth
from app.database import get_db
from app.models_db import PengaturanBengkel, Pengguna
from app.schemas import PengaturanBengkelBody, PengaturanBengkelOut

router = APIRouter(tags=["Pengaturan bengkel"])


@router.get("/pengaturan-bengkel", response_model=PengaturanBengkelOut)
def lihat_pengaturan(
    _: Pengguna = Depends(auth.pengguna_saat_ini),
    db: Session = Depends(get_db),
):
    pengaturan = db.get(PengaturanBengkel, 1)
    if pengaturan is None:
        raise HTTPException(status_code=404, detail="Pengaturan bengkel belum diisi.")
    return pengaturan


@router.put("/pengaturan-bengkel", response_model=PengaturanBengkelOut)
def ubah_pengaturan(
    data: PengaturanBengkelBody,
    _: Pengguna = Depends(auth.hanya_admin),
    db: Session = Depends(get_db),
):
    pengaturan = db.get(PengaturanBengkel, 1)
    if pengaturan is None:
        pengaturan = PengaturanBengkel(id=1, nama=data.nama, alamat=data.alamat, telepon=data.telepon)
        db.add(pengaturan)
    else:
        pengaturan.nama = data.nama
        pengaturan.alamat = data.alamat
        pengaturan.telepon = data.telepon
    db.commit()
    return pengaturan
