"""Format error seragam: setiap respons error berbentuk {"detail": "<pesan Indonesia>"}.

Khusus error validasi (422) ada tambahan "errors": [{"field": ..., "pesan": ...}].
Nilai masukan pengguna tidak pernah dikembalikan (bisa berisi password).
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, OperationalError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("bengkelpintar.error")

PESAN_BAWAAN = {
    404: "Endpoint tidak ditemukan.",
    405: "Metode HTTP tidak diizinkan untuk endpoint ini.",
}


def _pesan_validasi(err: dict) -> str:
    tipe = err.get("type", "")
    ctx = err.get("ctx") or {}
    if tipe == "missing":
        return "wajib diisi."
    if tipe == "string_too_short":
        return "tidak boleh kosong." if ctx.get("min_length") == 1 else f"minimal {ctx.get('min_length')} karakter."
    if tipe == "string_too_long":
        return f"maksimal {ctx.get('max_length')} karakter."
    if tipe == "string_pattern_mismatch":
        return "formatnya tidak sesuai."
    if tipe in ("int_type", "int_parsing", "int_from_float"):
        return "harus berupa bilangan bulat."
    if tipe in ("float_type", "float_parsing"):
        return "harus berupa angka."
    if tipe in ("bool_type", "bool_parsing"):
        return "harus berupa true atau false."
    if tipe == "string_type":
        return "harus berupa teks."
    if tipe == "greater_than_equal":
        return f"tidak boleh kurang dari {ctx.get('ge')}."
    if tipe == "greater_than":
        return f"harus lebih dari {ctx.get('gt')}."
    if tipe == "less_than_equal":
        return f"tidak boleh lebih dari {ctx.get('le')}."
    if tipe == "less_than":
        return f"harus kurang dari {ctx.get('lt')}."
    if tipe == "literal_error":
        return f"harus salah satu dari: {str(ctx.get('expected')).replace(' or ', ' atau ')}."
    if tipe == "too_short":
        return f"minimal {ctx.get('min_length')} item."
    if tipe == "too_long":
        return f"maksimal {ctx.get('max_length')} item."
    if tipe == "list_type":
        return "harus berupa daftar."
    if tipe in ("dict_type", "model_type", "model_attributes_type"):
        return "bentuk datanya tidak sesuai."
    if tipe.startswith("date"):
        return "formatnya harus YYYY-MM-DD."
    if tipe == "json_invalid":
        return "isi permintaan bukan JSON yang valid."
    if tipe == "value_error":
        galat = str(ctx.get("error", "")).strip()
        return galat if galat else "tidak valid."
    return "tidak valid."


def _nama_kolom(lokasi: tuple) -> str:
    bagian = [b for b in lokasi[1:] if not (isinstance(b, int) and lokasi[0] == "body" and b == 1 and len(lokasi) == 2)]
    teks = ""
    for b in bagian:
        teks += f"[{b}]" if isinstance(b, int) else (f".{b}" if teks else str(b))
    return teks


def ringkas_validasi(galat: list[dict]) -> tuple[str, list[dict]]:
    daftar = []
    for e in galat:
        kolom = _nama_kolom(tuple(e.get("loc", ())))
        daftar.append({"field": kolom, "pesan": _pesan_validasi(e)})
    pertama = daftar[0]
    kalimat = f"{pertama['field']} {pertama['pesan']}" if pertama["field"] else pertama["pesan"][0].upper() + pertama["pesan"][1:]
    if len(daftar) > 1:
        kalimat += f" (dan {len(daftar) - 1} kesalahan lain)"
    return kalimat, daftar


def pasang_penanganan_error(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validasi(_: Request, exc: RequestValidationError):
        detail, daftar = ringkas_validasi(exc.errors())
        return JSONResponse(status_code=422, content={"detail": detail, "errors": daftar})

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        detail = exc.detail if isinstance(exc.detail, str) else "Permintaan tidak dapat diproses."
        if exc.status_code in PESAN_BAWAAN and detail in ("Not Found", "Method Not Allowed"):
            detail = PESAN_BAWAAN[exc.status_code]
        return JSONResponse(status_code=exc.status_code, content={"detail": detail}, headers=exc.headers)

    @app.exception_handler(DataError)
    async def _data(_: Request, exc: DataError):
        log.warning("Nilai ditolak database: %s", type(exc.orig).__name__)
        return JSONResponse(status_code=400, content={"detail": "Nilai pada data tidak valid atau di luar batas."})

    @app.exception_handler(OperationalError)
    @app.exception_handler(PoolTimeoutError)
    async def _basis_data(_: Request, exc: Exception):
        log.error("Database tidak dapat dihubungi: %s", type(exc).__name__)
        return JSONResponse(
            status_code=503,
            content={"detail": "Database tidak dapat dihubungi. Coba lagi sebentar."},
        )

    @app.exception_handler(Exception)
    async def _tak_terduga(_: Request, exc: Exception):
        log.exception("Kesalahan tak terduga", exc_info=exc)
        return JSONResponse(status_code=500, content={"detail": "Terjadi kesalahan pada server."})
