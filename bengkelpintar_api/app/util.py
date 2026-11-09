from datetime import datetime, timedelta, timezone

from typing import Annotated

from fastapi import HTTPException, Path
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def pola_cari(kata: str) -> str:
    aman = kata.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{aman}%"


def nama_sudah_ada(db: Session, model, kolom, nilai: str, kecuali_id: int | None = None) -> bool:
    kueri = select(model.id).where(func.lower(kolom) == nilai.lower())
    if kecuali_id is not None:
        kueri = kueri.where(model.id != kecuali_id)
    return db.scalar(kueri.limit(1)) is not None


def ambil_atau_404(db: Session, model, id_: int, pesan: str):
    objek = db.get(model, id_)
    if objek is None:
        raise HTTPException(status_code=404, detail=pesan)
    return objek


def simpan(db: Session, pesan_konflik: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=pesan_konflik)


WIB = timezone(timedelta(hours=7))


def ke_wib(waktu: datetime) -> datetime:
    """Waktu server (zona apa pun) menjadi waktu WIB tanpa zona, tanpa mikrodetik."""
    if waktu.tzinfo is None:
        waktu = waktu.replace(tzinfo=timezone.utc)
    return waktu.astimezone(WIB).replace(tzinfo=None, microsecond=0)


IdPath = Annotated[int, Path(ge=1, le=2_147_483_647)]
