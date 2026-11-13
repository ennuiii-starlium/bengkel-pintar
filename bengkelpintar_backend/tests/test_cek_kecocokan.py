import json

import pytest

from training import cek_kecocokan as c

META = {
    "kode_gejala": ["G01", "G02"],
    "kode_kelas": ["K1", "K2"],
    "nama_gejala": {"G01": "Mesin susah dihidupkan", "G02": "Mesin mati mendadak"},
    "nama_kelas": {"K1": "Busi kotor", "K2": "Aki lemah"},
}
GEJALA_DB = [{"kode": "G01", "nama": "Mesin susah dihidupkan"}, {"kode": "G02", "nama": "Mesin mati mendadak"}]
KERUSAKAN_DB = [{"kode": "K1", "nama": "Busi kotor"}, {"kode": "K2", "nama": "Aki lemah"}]


def status(hasil, jenis):
    return {(r[1] or r[3]): r[6] for r in hasil["baris"] if r[0] == jenis}


def test_normalisasi_kode():
    assert c.normal("K1") == c.normal("K01") == c.normal("k001") == "K1"
    assert c.normal("G10") == "G10" and c.normal("ABC") == "ABC"


def test_daftar_sama_persis_dinyatakan_cocok():
    h = c.bandingkan(META, GEJALA_DB, KERUSAKAN_DB)
    assert h["cocok"] is True
    assert set(status(h, "gejala").values()) == {"MIRIP"} == set(status(h, "kerusakan").values())


def test_format_kode_berbeda_dilaporkan_dan_tidak_dianggap_cocok():
    h = c.bandingkan(META, GEJALA_DB, [{"kode": "K01", "nama": "Busi kotor"}, {"kode": "K02", "nama": "Aki lemah"}])
    assert h["cocok"] is False
    assert set(status(h, "kerusakan").values()) == {"MIRIP+FORMAT_KODE_BEDA"}


def test_kode_sama_arti_berbeda_ditandai_berbeda():
    db = [{"kode": "G01", "nama": "Mesin susah dihidupkan"}, {"kode": "G02", "nama": "Lampu depan meredup"}]
    h = c.bandingkan(META, db, KERUSAKAN_DB)
    assert h["cocok"] is False and status(h, "gejala") == {"G01": "MIRIP", "G02": "BERBEDA"}


def test_nama_yang_memuat_dianggap_mirip():
    db = [{"kode": "G01", "nama": "Mesin sulit dihidupkan"}, {"kode": "G02", "nama": "Mesin mati mendadak saat berjalan"}]
    assert set(status(c.bandingkan(META, db, KERUSAKAN_DB), "gejala").values()) == {"MIRIP"}


def test_hanya_di_model_dan_hanya_di_database():
    meta = {**META, "kode_gejala": ["G01", "G02", "G05"], "nama_gejala": {**META["nama_gejala"], "G05": "Tarikan berat"}}
    db = GEJALA_DB + [{"kode": "G09", "nama": "Boros bensin"}]
    h = c.bandingkan(meta, db, KERUSAKAN_DB)
    assert h["cocok"] is False
    assert status(h, "gejala") == {"G01": "MIRIP", "G02": "MIRIP", "G05": "HANYA_DI_MODEL", "G09": "HANYA_DI_DATABASE"}


def test_tanpa_nama_di_model_tidak_bisa_dianggap_mirip():
    meta = {**META, "nama_gejala": {}}
    assert set(status(c.bandingkan(meta, GEJALA_DB, KERUSAKAN_DB), "gejala").values()) == {"BERBEDA"}


def siapkan(tmp_path, gejala=GEJALA_DB, kerusakan=KERUSAKAN_DB):
    (tmp_path / "meta.json").write_text(json.dumps(META), encoding="utf-8")
    (tmp_path / "g.json").write_text(json.dumps(gejala), encoding="utf-8")
    (tmp_path / "k.json").write_text(json.dumps(kerusakan), encoding="utf-8")
    return ["--meta", str(tmp_path / "meta.json"), "--gejala-json", str(tmp_path / "g.json"), "--kerusakan-json", str(tmp_path / "k.json"), "--hasil", str(tmp_path / "h")]


def test_cli_kode_keluar_dan_berkas_hasil(tmp_path, capsys):
    assert c.jalankan(siapkan(tmp_path)) == 0
    assert "HASIL: COCOK" in capsys.readouterr().out
    assert c.jalankan(siapkan(tmp_path, gejala=[{"kode": "G01", "nama": "Lampu"}] + GEJALA_DB[1:])) == 1
    teks = (tmp_path / "h" / "kecocokan_database.md").read_text(encoding="utf-8")
    assert "TIDAK COCOK" in teks and "tidak boleh dipasang ke API" in teks
    assert (tmp_path / "h" / "kecocokan_database.csv").is_file()


def test_cli_berkas_rusak_kode_keluar_2(tmp_path, capsys):
    argumen = siapkan(tmp_path, gejala={"bukan": "daftar"})
    assert c.jalankan(argumen) == 2 and "GAGAL" in capsys.readouterr().err
    (tmp_path / "k.json").write_text("{rusak", encoding="utf-8")
    assert c.jalankan(argumen) == 2
    assert c.jalankan(["--meta", str(tmp_path / "tidak_ada.json"), "--gejala-json", "x", "--kerusakan-json", "y"]) == 2
