import json
import os
import re
from decimal import Decimal
import psycopg2

JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "arsip_penerima.json")
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

PETA_KABUPATEN = {
    "KOTA SABANG",
    "KOTA BANDA ACEH",
    "KAB. ACEH BESAR",
    "KAB. ACEH BARAT",
    "KAB. ACEH SELATAN",
    "KAB. ACEH JAYA",
    "KAB. ABDYA",
    "KAB. SIMEULUE",
    "KAB. NAGAN RAYA",
    "KAB. ACEH SINGKIL",
    "KAB. ACEH TIMUR",
    "KAB. ACEH UTARA",
    "KAB. PIDIE",
    "KAB. ACEH TAMIANG",
    "KAB. BIREUEN",
    "KOTA LANGSA",
    "KOTA LHOKSEUMAWE",
    "KAB. PIDIE JAYA",
}
DAFTAR_KOTA = {"SABANG", "BANDA ACEH", "LHOKSEUMAWE", "LANGSA"}


def normalisasi_kabupaten(nama_kab):
    teks = re.sub(r"\s+", " ", str(nama_kab or "").strip().upper())
    if not teks:
        return "TIDAK TERISI"
    if teks in PETA_KABUPATEN:
        return teks
    inti = re.sub(r"^(KAB\.?|KABUPATEN|KOTA)\s+", "", teks).strip()
    if inti == "ACEH BARAT DAYA":
        inti = "ABDYA"
    kandidat = f"KOTA {inti}" if inti in DAFTAR_KOTA else f"KAB. {inti}"
    return kandidat if kandidat in PETA_KABUPATEN else teks


def normalisasi_strata(strata_teks):
    s = str(strata_teks or "").strip().upper()
    if s in ("PT", "PERGURUAN TINGGI", "KULIAH", "UNIVERSITAS", "S1", "D3"):
        return "PERGURUAN TINGGI"
    if s in ("SD", "MI"):
        return "SD"
    if s in ("SMP", "MTS"):
        return "SMP"
    if s in ("SMA", "SMK", "MA"):
        return "SMA"
    return s


def bersihkan_angka(nilai):
    if nilai is None:
        return 0
    if isinstance(nilai, Decimal):
        return int(nilai)
    if isinstance(nilai, (int, float)):
        return int(nilai)
    teks = (
        str(nilai)
        .replace("Rp", "")
        .replace("rp", "")
        .replace(".", "")
        .replace(",", "")
        .strip()
    )
    if teks.isdigit():
        return int(teks)
    try:
        return int(float(teks))
    except ValueError:
        return 0


def main():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL belum diatur. Isi environment variable DATABASE_URL terlebih dahulu.")

    with open(JSON_PATH, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError("Format arsip_penerima.json harus berupa list JSON [...]")

    sql = """
        INSERT INTO tabel_penerima (
            tahun,
            semester,
            kabupaten_kota,
            lhok,
            nama_penerima,
            alamat,
            strata_pendidikan,
            nomor_rekening,
            jumlah_dana,
            status_data
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'ARSIP')
    """

    connect_kwargs = {}
    if "sslmode=" not in DATABASE_URL:
        connect_kwargs["sslmode"] = "require"

    masuk = 0
    terlewat = 0

    with psycopg2.connect(DATABASE_URL, **connect_kwargs) as conn:
        with conn.cursor() as cur:
            for row in data:
                if not isinstance(row, dict):
                    terlewat += 1
                    continue

                nama = re.sub(r"\s+", " ", str(row.get("NAMA") or "").strip().upper())
                if not nama:
                    terlewat += 1
                    continue

                tahun = str(row.get("TAHUN") or "").strip()
                semester = str(row.get("SEMESTER") or "").strip()
                kabupaten = normalisasi_kabupaten(row.get("KABUPATEN") or "")
                lhok = str(row.get("LHOK") or "").strip().upper()
                alamat = str(row.get("ALAMAT") or "").strip().upper()
                strata = normalisasi_strata(row.get("STRATA") or "")
                rekening = str(row.get("NOMOR REKENIG") or "").strip()
                dana = bersihkan_angka(row.get("JUMLAH DANA") or 0)

                cur.execute(
                    sql,
                    (tahun, semester, kabupaten, lhok, nama, alamat, strata, rekening, dana),
                )
                masuk += 1
        conn.commit()

    print(f"Selesai: {masuk} data arsip masuk ke Neon (status_data='ARSIP'), {terlewat} terlewat.")


if __name__ == "__main__":
    main()