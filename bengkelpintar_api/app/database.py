from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, pool_pre_ping=True) if DATABASE_URL else None
SessionLocal = sessionmaker(bind=engine, autoflush=False) if engine else None


def get_db():
    if SessionLocal is None:
        raise RuntimeError("DATABASE_URL belum diisi di .env")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def pastikan_skema(mesin) -> None:
    """Penyesuaian skema yang tidak dilakukan create_all pada tabel yang sudah ada."""
    with mesin.begin() as conn:
        conn.execute(text("ALTER TABLE item_transaksi ADD COLUMN IF NOT EXISTS nama VARCHAR(120)"))
        conn.execute(
            text(
                "UPDATE item_transaksi i SET nama = p.nama FROM produk p "
                "WHERE i.nama IS NULL AND i.tipe = 'produk' AND i.produk_id = p.id"
            )
        )
        conn.execute(
            text(
                "UPDATE item_transaksi i SET nama = j.nama FROM jasa j "
                "WHERE i.nama IS NULL AND i.tipe = 'jasa' AND i.jasa_id = j.id"
            )
        )
        conn.execute(text("ALTER TABLE transaksi ADD COLUMN IF NOT EXISTS waktu_final TIMESTAMPTZ"))
        conn.execute(
            text(
                "UPDATE transaksi SET waktu_final = waktu "
                "WHERE status = 'final' AND waktu_final IS NULL"
            )
        )
