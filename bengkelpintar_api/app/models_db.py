from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PengaturanBengkel(Base):
    __tablename__ = "pengaturan_bengkel"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120))
    alamat: Mapped[str] = mapped_column(String(255))
    telepon: Mapped[str] = mapped_column(String(30))


class Pengguna(Base):
    __tablename__ = "pengguna"
    __table_args__ = (
        CheckConstraint("peran IN ('admin', 'mekanik')", name="ck_pengguna_peran"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120))
    username: Mapped[str] = mapped_column(String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    peran: Mapped[str] = mapped_column(String(10))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Kategori(Base):
    __tablename__ = "kategori"

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(80), unique=True)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Produk(Base):
    __tablename__ = "produk"
    __table_args__ = (
        CheckConstraint("harga >= 0", name="ck_produk_harga"),
        CheckConstraint("stok >= 0", name="ck_produk_stok"),
        CheckConstraint("stok_minimum >= 0", name="ck_produk_stok_minimum"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120))
    kategori_id: Mapped[int] = mapped_column(ForeignKey("kategori.id"), index=True)
    harga: Mapped[int] = mapped_column(Integer)
    stok: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    stok_minimum: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    kategori: Mapped[Kategori] = relationship()


class Jasa(Base):
    __tablename__ = "jasa"
    __table_args__ = (CheckConstraint("harga >= 0", name="ck_jasa_harga"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    nama: Mapped[str] = mapped_column(String(120))
    harga: Mapped[int] = mapped_column(Integer)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class Gejala(Base):
    __tablename__ = "gejala"

    id: Mapped[int] = mapped_column(primary_key=True)
    kode: Mapped[str] = mapped_column(String(10), unique=True)
    nama: Mapped[str] = mapped_column(String(120))
    kategori: Mapped[str] = mapped_column(String(50))
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")


class KerusakanProduk(Base):
    __tablename__ = "kerusakan_produk"

    kerusakan_id: Mapped[int] = mapped_column(
        ForeignKey("kerusakan.id"), primary_key=True
    )
    produk_id: Mapped[int] = mapped_column(ForeignKey("produk.id"), primary_key=True)


class KerusakanJasa(Base):
    __tablename__ = "kerusakan_jasa"

    kerusakan_id: Mapped[int] = mapped_column(
        ForeignKey("kerusakan.id"), primary_key=True
    )
    jasa_id: Mapped[int] = mapped_column(ForeignKey("jasa.id"), primary_key=True)


class Kerusakan(Base):
    __tablename__ = "kerusakan"
    __table_args__ = (
        CheckConstraint(
            "urgensi IN ('rendah', 'sedang', 'tinggi')", name="ck_kerusakan_urgensi"
        ),
        CheckConstraint(
            "estimasi_waktu_menit >= 0", name="ck_kerusakan_estimasi_waktu"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    kode: Mapped[str] = mapped_column(String(10), unique=True)
    nama: Mapped[str] = mapped_column(String(120))
    urgensi: Mapped[str] = mapped_column(String(10))
    solusi: Mapped[str] = mapped_column(Text)
    estimasi_waktu_menit: Mapped[int] = mapped_column(Integer)
    aktif: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")

    komponen: Mapped[list[Produk]] = relationship(secondary="kerusakan_produk")
    jasa: Mapped[list[Jasa]] = relationship(secondary="kerusakan_jasa")


class RiwayatDiagnosis(Base):
    __tablename__ = "riwayat_diagnosis"

    id: Mapped[int] = mapped_column(primary_key=True)
    pengguna_id: Mapped[int] = mapped_column(ForeignKey("pengguna.id"), index=True)
    gejala: Mapped[list] = mapped_column(JSONB)
    hasil: Mapped[dict] = mapped_column(JSONB)
    keyakinan: Mapped[float]
    waktu: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaksi(Base):
    __tablename__ = "transaksi"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'final')", name="ck_transaksi_status"),
        CheckConstraint(
            "metode_bayar IS NULL OR metode_bayar IN ('tunai', 'transfer')",
            name="ck_transaksi_metode_bayar",
        ),
        CheckConstraint("total >= 0", name="ck_transaksi_total"),
        CheckConstraint(
            "status = 'draft' OR (metode_bayar IS NOT NULL "
            "AND jumlah_dibayar IS NOT NULL AND difinalkan_oleh IS NOT NULL "
            "AND jumlah_dibayar >= total)",
            name="ck_transaksi_final_lengkap",
        ),
        Index("ix_transaksi_status_waktu", "status", "waktu"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    nomor: Mapped[str] = mapped_column(String(20), unique=True)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    nama_pelanggan: Mapped[Optional[str]] = mapped_column(String(120))
    plat_nomor: Mapped[Optional[str]] = mapped_column(String(20))
    total: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    metode_bayar: Mapped[Optional[str]] = mapped_column(String(10))
    jumlah_dibayar: Mapped[Optional[int]] = mapped_column(Integer)
    dibuat_oleh: Mapped[int] = mapped_column(ForeignKey("pengguna.id"), index=True)
    difinalkan_oleh: Mapped[Optional[int]] = mapped_column(ForeignKey("pengguna.id"))
    riwayat_diagnosis_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("riwayat_diagnosis.id")
    )
    waktu: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    waktu_final: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    pembuat: Mapped[Pengguna] = relationship(foreign_keys=[dibuat_oleh])
    penyelesai: Mapped[Optional[Pengguna]] = relationship(foreign_keys=[difinalkan_oleh])
    items: Mapped[list["ItemTransaksi"]] = relationship(
        back_populates="transaksi",
        order_by="ItemTransaksi.id",
        cascade="all, delete-orphan",
    )


class ItemTransaksi(Base):
    __tablename__ = "item_transaksi"
    __table_args__ = (
        CheckConstraint("tipe IN ('produk', 'jasa')", name="ck_item_tipe"),
        CheckConstraint(
            "(tipe = 'produk' AND produk_id IS NOT NULL AND jasa_id IS NULL) OR "
            "(tipe = 'jasa' AND jasa_id IS NOT NULL AND produk_id IS NULL)",
            name="ck_item_sumber",
        ),
        CheckConstraint("jumlah > 0", name="ck_item_jumlah"),
        CheckConstraint("harga_satuan >= 0", name="ck_item_harga_satuan"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    transaksi_id: Mapped[int] = mapped_column(
        ForeignKey("transaksi.id"), index=True
    )
    tipe: Mapped[str] = mapped_column(String(10))
    produk_id: Mapped[Optional[int]] = mapped_column(ForeignKey("produk.id"))
    jasa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("jasa.id"))
    nama: Mapped[Optional[str]] = mapped_column(String(120))
    jumlah: Mapped[int] = mapped_column(Integer)
    harga_satuan: Mapped[int] = mapped_column(Integer)

    transaksi: Mapped[Transaksi] = relationship(back_populates="items")
    produk: Mapped[Optional[Produk]] = relationship()
    jasa: Mapped[Optional[Jasa]] = relationship()


class MutasiStok(Base):
    __tablename__ = "mutasi_stok"
    __table_args__ = (
        CheckConstraint("jumlah <> 0", name="ck_mutasi_jumlah"),
        Index("ix_mutasi_stok_produk_waktu", "produk_id", "waktu"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    produk_id: Mapped[int] = mapped_column(ForeignKey("produk.id"))
    jumlah: Mapped[int] = mapped_column(Integer)
    alasan: Mapped[str] = mapped_column(String(255))
    pengguna_id: Mapped[int] = mapped_column(ForeignKey("pengguna.id"))
    transaksi_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transaksi.id"))
    waktu: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
