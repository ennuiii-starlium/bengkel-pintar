import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import config
from app.database import get_db
from app.models_db import Pengguna

ALGORITMA = "HS256"
BATAS_BYTE_PASSWORD = 72
PANJANG_MINIMAL_SECRET = 32

_skema_bearer = HTTPBearer(auto_error=False)
_hash_tiruan: str | None = None


def hash_password(password: str) -> str:
    if len(password.encode("utf-8")) > BATAS_BYTE_PASSWORD:
        raise ValueError("Password terlalu panjang.")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def hash_tiruan() -> str:
    """Hash untuk dibandingkan saat username tidak ada, supaya waktu respons sama."""
    global _hash_tiruan
    if _hash_tiruan is None:
        _hash_tiruan = hash_password(secrets.token_urlsafe(16))
    return _hash_tiruan


def _sidik_password(password_hash: str) -> str:
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def _secret_jwt() -> str:
    if len(config.JWT_SECRET) < PANJANG_MINIMAL_SECRET:
        raise RuntimeError(
            f"JWT_SECRET di .env harus diisi minimal {PANJANG_MINIMAL_SECRET} karakter."
        )
    return config.JWT_SECRET


def buat_token(pengguna: Pengguna) -> str:
    sekarang = datetime.now(timezone.utc)
    isi = {
        "sub": str(pengguna.id),
        "iat": sekarang,
        "exp": sekarang + timedelta(minutes=config.JWT_EXPIRE_MINUTES),
        "pv": _sidik_password(pengguna.password_hash),
    }
    return jwt.encode(isi, _secret_jwt(), algorithm=ALGORITMA)


def _tolak_sesi() -> HTTPException:
    return HTTPException(
        status_code=401,
        detail="Sesi tidak valid atau sudah berakhir. Silakan masuk lagi.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def periksa_api_key(x_api_key: str | None = Header(default=None)) -> None:
    if not config.API_KEY:
        raise HTTPException(status_code=500, detail="Server belum dikonfigurasi.")
    if not x_api_key or not secrets.compare_digest(
        x_api_key.encode("utf-8"), config.API_KEY.encode("utf-8")
    ):
        raise HTTPException(status_code=401, detail="API key tidak valid.")


def pengguna_saat_ini(
    _: None = Depends(periksa_api_key),
    kredensial: HTTPAuthorizationCredentials | None = Depends(_skema_bearer),
    db: Session = Depends(get_db),
) -> Pengguna:
    if kredensial is None:
        raise _tolak_sesi()
    try:
        isi = jwt.decode(
            kredensial.credentials,
            _secret_jwt(),
            algorithms=[ALGORITMA],
            options={"require": ["exp", "iat", "sub", "pv"]},
        )
        id_pengguna = int(isi["sub"])
    except (jwt.InvalidTokenError, ValueError):
        raise _tolak_sesi()
    pengguna = db.get(Pengguna, id_pengguna)
    if (
        pengguna is None
        or not pengguna.aktif
        or not secrets.compare_digest(isi["pv"], _sidik_password(pengguna.password_hash))
    ):
        raise _tolak_sesi()
    return pengguna


def hanya_admin(pengguna: Pengguna = Depends(pengguna_saat_ini)) -> Pengguna:
    if pengguna.peran != "admin":
        raise HTTPException(
            status_code=403, detail="Hanya admin yang dapat mengakses fitur ini."
        )
    return pengguna
