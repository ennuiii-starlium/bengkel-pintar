from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

BATAS_BYTE_PASSWORD = 72
BATAS_ID = 2_147_483_647
BATAS_STOK = 1_000_000


def _tanpa_nul(nilai):
    if isinstance(nilai, str) and "\x00" in nilai:
        raise ValueError("tidak boleh mengandung karakter NUL.")
    return nilai


def _periksa_panjang_byte(nilai: str) -> str:
    if len(nilai.encode("utf-8")) > BATAS_BYTE_PASSWORD:
        raise ValueError(f"terlalu panjang (maksimal {BATAS_BYTE_PASSWORD} byte).")
    return nilai


class HealthResponse(BaseModel):
    status: str
    versi: str


class PesanResponse(BaseModel):
    pesan: str


class LoginRequest(BaseModel):
    username: Annotated[str, Field(min_length=1, max_length=50), AfterValidator(_tanpa_nul)]
    password: str = Field(min_length=1, max_length=128)


class PenggunaRingkas(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama: str
    peran: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: PenggunaRingkas


class PenggunaDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama: str
    peran: str
    username: str
    aktif: bool


class GantiPasswordRequest(BaseModel):
    password_lama: str = Field(min_length=1, max_length=128)
    password_baru: str = Field(min_length=6)

    _batas_baru = field_validator("password_baru")(_periksa_panjang_byte)


class ResetPasswordRequest(BaseModel):
    password_baru: str = Field(min_length=6)

    _batas_baru = field_validator("password_baru")(_periksa_panjang_byte)


# ---------------------------------------------------------------- data master
from typing import Annotated, Literal  # noqa: E402

from pydantic import BeforeValidator, StrictInt, StringConstraints  # noqa: E402


def _teks(maks: int):
    return Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=maks),
        AfterValidator(_tanpa_nul),
    ]


Harga = Annotated[StrictInt, Field(ge=0, le=100_000_000)]
Stok = Annotated[StrictInt, Field(ge=0, le=BATAS_STOK)]
IdInt = Annotated[StrictInt, Field(ge=1, le=BATAS_ID)]
Urgensi = Literal["rendah", "sedang", "tinggi"]
Peran = Literal["admin", "mekanik"]
KodeMaster = Annotated[
    str,
    StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Za-z][A-Za-z0-9]{0,9}$"),
]
def _rapikan_username(nilai):
    return nilai.strip().lower() if isinstance(nilai, str) else nilai


Username = Annotated[
    str,
    BeforeValidator(_rapikan_username),
    StringConstraints(pattern=r"^[a-z0-9._]{3,50}$"),
]


class KategoriBuat(BaseModel):
    nama: _teks(80)
    aktif: bool = True


class KategoriUbah(BaseModel):
    nama: _teks(80)
    aktif: bool


class KategoriOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama: str
    aktif: bool


class ProdukBuat(BaseModel):
    nama: _teks(120)
    kategori_id: IdInt
    harga: Harga
    stok: Stok = 0
    stok_minimum: Stok = 0
    aktif: bool = True


class ProdukUbah(BaseModel):
    """Stok tidak bisa diubah lewat PUT: perubahan stok hanya lewat mutasi stok."""

    nama: _teks(120)
    kategori_id: IdInt
    harga: Harga
    stok_minimum: Stok
    aktif: bool


class ProdukOut(BaseModel):
    id: int
    nama: str
    kategori_id: int
    kategori_nama: str
    harga: int
    stok: int
    stok_minimum: int
    aktif: bool


class JasaBuat(BaseModel):
    nama: _teks(120)
    harga: Harga
    aktif: bool = True


class JasaUbah(BaseModel):
    nama: _teks(120)
    harga: Harga
    aktif: bool


class JasaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama: str
    harga: int
    aktif: bool


class GejalaBuat(BaseModel):
    kode: KodeMaster
    nama: _teks(120)
    kategori: _teks(50)
    aktif: bool = True


class GejalaUbah(BaseModel):
    kode: KodeMaster | None = None
    nama: _teks(120)
    kategori: _teks(50)
    aktif: bool


class GejalaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kode: str
    nama: str
    kategori: str
    aktif: bool


class KomponenRef(BaseModel):
    produk_id: IdInt


class JasaRef(BaseModel):
    jasa_id: IdInt


class KerusakanBuat(BaseModel):
    kode: KodeMaster
    nama: _teks(120)
    urgensi: Urgensi
    solusi: _teks(2000)
    estimasi_waktu_menit: Annotated[StrictInt, Field(ge=0, le=1440)]
    aktif: bool = True
    komponen_terkait: list[KomponenRef] = []
    jasa_terkait: list[JasaRef] = []


class KerusakanUbah(BaseModel):
    kode: KodeMaster | None = None
    nama: _teks(120)
    urgensi: Urgensi
    solusi: _teks(2000)
    estimasi_waktu_menit: Annotated[StrictInt, Field(ge=0, le=1440)]
    aktif: bool
    komponen_terkait: list[KomponenRef]
    jasa_terkait: list[JasaRef]


class KomponenTerkaitOut(BaseModel):
    produk_id: int
    nama: str
    harga: int


class JasaTerkaitOut(BaseModel):
    jasa_id: int
    nama: str
    harga: int


class KerusakanOut(BaseModel):
    id: int
    kode: str
    nama: str
    urgensi: str
    solusi: str
    estimasi_waktu_menit: int
    aktif: bool
    komponen_terkait: list[KomponenTerkaitOut]
    jasa_terkait: list[JasaTerkaitOut]


class PenggunaBuat(BaseModel):
    nama: _teks(120)
    username: Username
    peran: Peran
    password: str = Field(min_length=6)
    aktif: bool = True

    _batas_password = field_validator("password")(_periksa_panjang_byte)


class PenggunaUbah(BaseModel):
    nama: _teks(120)
    username: Username
    peran: Peran
    aktif: bool


class PengaturanBengkelBody(BaseModel):
    nama: _teks(120)
    alamat: _teks(255)
    telepon: _teks(30)


class PengaturanBengkelOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nama: str
    alamat: str
    telepon: str


# ----------------------------------------------------------------------- stok
from datetime import datetime  # noqa: E402

JumlahPenyesuaian = Annotated[StrictInt, Field(ge=-1_000_000, le=1_000_000)]


class PenyesuaianStokRequest(BaseModel):
    jumlah: JumlahPenyesuaian
    alasan: _teks(255)

    @field_validator("jumlah")
    @classmethod
    def _bukan_nol(cls, nilai: int) -> int:
        if nilai == 0:
            raise ValueError("tidak boleh nol.")
        return nilai


class StokBaruResponse(BaseModel):
    stok_baru: int


class MutasiStokOut(BaseModel):
    id: int
    produk_id: int
    jumlah: int
    alasan: str
    waktu: datetime
    dibuat_oleh: str


# ------------------------------------------------------------------ transaksi
Teks120 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120), AfterValidator(_tanpa_nul)]
Teks20 = Annotated[str, StringConstraints(strip_whitespace=True, max_length=20), AfterValidator(_tanpa_nul)]


class ItemTransaksiRequest(BaseModel):
    tipe: Literal["produk", "jasa"]
    id: IdInt
    jumlah: Annotated[StrictInt, Field(ge=1, le=10_000)]


class TransaksiBuat(BaseModel):
    riwayat_diagnosis_id: IdInt | None = None
    nama_pelanggan: Teks120
    plat_nomor: Teks20
    items: Annotated[list[ItemTransaksiRequest], Field(min_length=1, max_length=100)]


class TransaksiUbah(BaseModel):
    nama_pelanggan: Teks120
    plat_nomor: Teks20
    items: Annotated[list[ItemTransaksiRequest], Field(min_length=1, max_length=100)]


class FinalisasiRequest(BaseModel):
    metode_bayar: Literal["tunai", "transfer"]
    jumlah_dibayar: Annotated[StrictInt, Field(ge=0, le=2_000_000_000)]


class ItemTransaksiOut(BaseModel):
    id: int
    tipe: str
    produk_id: int | None
    jasa_id: int | None
    nama: str
    jumlah: int
    harga_satuan: int
    subtotal: int


class TransaksiOut(BaseModel):
    id: int
    nomor: str
    status: str
    nama_pelanggan: str
    plat_nomor: str
    total: int
    metode_bayar: str | None
    jumlah_dibayar: int | None
    kembalian: int | None
    dibuat_oleh: str
    dibuat_oleh_id: int
    difinalkan_oleh: str | None
    riwayat_diagnosis_id: int | None
    waktu: datetime
    items: list[ItemTransaksiOut]


# -------------------------------------------------------------------- laporan
class PenjualanPerHariOut(BaseModel):
    tanggal: str
    total: int
    jumlah: int


class TerlarisOut(BaseModel):
    tipe: str
    id: int
    nama: str
    jumlah: int
    total: int


class LaporanPenjualanOut(BaseModel):
    periode_mulai: str
    periode_selesai: str
    total_penjualan: int
    jumlah_transaksi: int
    rata_rata: int
    penjualan_per_hari: list[PenjualanPerHariOut]
    terlaris: list[TerlarisOut]


class StatistikDiagnosisItemOut(BaseModel):
    nama: str
    jumlah: int
    persentase: float


class StatistikDiagnosisOut(BaseModel):
    total: int
    items: list[StatistikDiagnosisItemOut]


# ------------------------------------------------------------------ diagnosis
class DiagnosisRequest(BaseModel):
    gejala_ids: Annotated[list[IdInt], Field(min_length=1, max_length=50)]


class KerusakanPrediksiOut(BaseModel):
    id: int
    nama: str
    keyakinan: float


class EstimasiBiayaOut(BaseModel):
    min: int
    max: int
    keterangan: str


class HasilDiagnosisOut(BaseModel):
    riwayat_id: int
    kerusakan_utama: KerusakanPrediksiOut
    kemungkinan_lain: list[KerusakanPrediksiOut]
    urgensi: str
    urgensi_keterangan: str
    solusi: str
    estimasi_waktu_menit: int
    komponen_terkait: list[KomponenTerkaitOut]
    jasa_terkait: list[JasaTerkaitOut]
    estimasi_biaya: EstimasiBiayaOut
    waktu: datetime


class RiwayatDiagnosisOut(BaseModel):
    id: int
    pengguna_id: int
    pengguna_nama: str
    gejala: list[GejalaOut]
    hasil: HasilDiagnosisOut
    keyakinan: float
    waktu: datetime
