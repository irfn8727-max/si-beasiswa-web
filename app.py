import csv
import io
import os
import re
from decimal import Decimal
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash, generate_password_hash
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "si-beasiswa-nelayan-aceh-secret-key")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(BASE_DIR, "static", "img")

# Konfigurasi PostgreSQL (db_beasiswa)
DB_HOST = os.environ.get("PGHOST", "192.168.100.10")
DB_PORT = int(os.environ.get("PGPORT", "5432"))
DB_NAME = os.environ.get("PGDATABASE", "db_beasiswa")
DB_USER = os.environ.get("PGUSER", "postgres")
DB_PASSWORD = os.environ.get("PGPASSWORD", "adminserver123")

# Ganti tulisan di bawah ini sesuai Nama Instansi / Yayasan Anda
NAMA_INSTANSI = "YAYASAN PANGKAI MEUREUNOE ANEUK NELAYAN"

# Kredensial login awal
ADMIN_USERNAME = os.environ.get("APP_ADMIN_USER", "admin")
ADMIN_PASSWORD_HASH = generate_password_hash(
    os.environ.get("APP_ADMIN_PASS", "AdminAceh2026!")
)

BENDAHARA_USERNAME = os.environ.get("APP_BENDAHARA_USER", "bendahara")
BENDAHARA_PASSWORD_HASH = generate_password_hash(
    os.environ.get("APP_BENDAHARA_PASS", "BendaharaAceh2026!")
)

DATABASE_URL = os.environ.get("DATABASE_URL")
DB_SSLMODE = os.environ.get("DB_SSLMODE")  # isi "require" di cloud jika diminta


def get_db_connection():
    kwargs = {}
    if DB_SSLMODE:
        kwargs["sslmode"] = DB_SSLMODE

    if DATABASE_URL:
        return psycopg2.connect(DATABASE_URL, **kwargs)

    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        **kwargs,
    )


def cari_file_logo():
    if not os.path.isdir(IMG_DIR):
        return None
    prioritas = ["logo.png", "logo.jpg", "logo.jpeg", "logo.webp"]
    for nama in prioritas:
        if os.path.isfile(os.path.join(IMG_DIR, nama)):
            return f"img/{nama}"
    for berkas in sorted(os.listdir(IMG_DIR)):
        if berkas.lower().endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
            return f"img/{berkas}"
    return None


@app.context_processor
def inject_identitas_instansi():
    return {
        "nama_instansi": NAMA_INSTANSI.strip(),
        "logo_instansi": cari_file_logo(),
    }


TARIF_JENJANG = [
    {"jenjang": "SD", "nominal": 360000},
    {"jenjang": "SMP", "nominal": 480000},
    {"jenjang": "SMA", "nominal": 600000},
    {"jenjang": "PERGURUAN TINGGI", "nominal": 900000},
]

# 18 Kabupaten/Kota beserta nama-nama Lhok sesuai daftar resmi sistem
PETA_KABUPATEN_LHOK = {
    "KOTA SABANG": [
        "LHOK BALOHAN",
        "LHOK IE MEULEE",
        "LHOK KEUNEUKAI",
        "LHOK JABOI",
        "LHOK ANOI ITAM",
        "LHOK BEURAWANG",
        "LHOK PASIRAN",
        "LHOK IBOIH",
        "LHOK PRIA LAOT",
        "LHOK PAYA",
        "LHOK UJONG KAREUNG",
    ],
    "KOTA BANDA ACEH": [
        "LHOK PASIE TIBANG / ALUE NAGA",
        "LHOK KUALA ACEH / LAMPULO",
        "LHOK KUALA CANGKOI / ULEE LHEUE",
    ],
    "KAB. ACEH BESAR": [
        "LHOK LEUNGAH",
        "LHOK LAMPANAH",
        "LHOK KRUENG RAYA",
        "LHOK PASIE LAMNGA",
        "LHOK KUALA GIGIENG / LAMBADA",
        "LHOK LAMTEUNGOH",
        "LHOK NGA",
        "LHOK LAMPUUK",
        "LHOK LEUPUNG",
        "LHOK SANEY",
        "LHOK GLEE BRUEK",
        "LHOK PULO BREUH UTARA/PULO ACEH",
        "LHOK LAMPUYANG PULO ACEH",
        "LHOK PULO NASI",
    ],
    "KAB. ACEH BARAT": [
        "LHOK JOHAN PAHLAWAN",
        "LHOK SAMATIGA",
        "LHOK ARONGAN LAMBALEK",
        "LHOK MEUREUBOE",
    ],
    "KAB. ACEH SELATAN": [
        "LHOK TAPAKTUAN I",
        "LHOK TAPAKTUAN II",
        "LHOK SAMADUA I",
        "LHOK SAMADUA II",
        "LHOK PAWOH SAWANG",
        "LHOK SAWANG BA'U",
        "LHOK LABUHAN TAROK",
        "LHOK KEUDE MEUKEK",
        "LHOK PASIE RAJA",
        "LHOK KLUET UTARA/KUALA BA'U",
        "LHOK SUAK BAKONG",
        "LHOK PASIE BAKONGAN",
        "LHOK BAKONGAN TIMUR",
        "LHOK KEUDE TRUMON",
        "LHOK BULOH SEUMA",
        "LHOK LABUHAN HAJI TIMUR",
        "LHOK LABUHAN HAJI SELATAN",
        "LHOK LABUHAN HAJI BARAT",
        "LHOK RANTAU BINUANG",
    ],
    "KAB. ACEH JAYA": [
        "LHOK BABAH NIPAH",
        "LHOK KRUET",
        "LHOK PATEK",
        "LHOK RIGAIH",
        "LHOK CALANG",
        "LHOK TEUNOM",
        "LHOK PANGA",
        "LHOK KUALA DAYA",
        "LHOK KUALA UNGA",
        "LHOK KELUANG",
        "LHOK LAMBEUSOI",
    ],
    "KAB. ABDYA": [
        "LHOK SUSOH",
        "LHOK TANGAN-TANGAN",
        "LHOK MANGGENG",
        "LHOK LEMBAH SABIL",
        "LHOK SUAK SETIA",
        "LHOK KUALA BATEE",
    ],
    "KAB. SIMEULUE": [
        "LHOK SIMEULUE TIMUR",
        "LHOK SIMEULUE TENGAH",
        "LHOK TEUPAH BARAT",
        "LHOK SALANG",
        "LHOK TEUPAH SELATAN",
        "LHOK TELUK DALAM",
        "LHOK SIMEULUE BARAT",
        "LHOK ALAFAN",
        "LHOK TEUPAH TENGAH",
        "LHOK SIMEULUE CUT",
    ],
    "KAB. NAGAN RAYA": [
        "LHOK KUALA TRIPA",
        "LHOK KUALA TRANG",
        "LHOK KUALA TADU",
        "LHOK KUALA TUHA",
        "LHOK KUALA SEUMAYAM",
        "LHOK PULO",
        "LHOK BABAH LHUENG",
    ],
    "KAB. ACEH SINGKIL": [
        "KOTA SINGKIL",
        "LHOK PULO SAROK",
        "LHOK KILANGAN",
        "LHOK TELUK AMBUN",
        "LHOK UJUNG SINGKIL",
        "LHOK KAYU MENANG",
        "LHOK KUALA BARU SUNGAI",
        "LHOK KUALA BARU LAUT",
        "LHOK SUKA JAYA",
        "LHOK GOSONG TELAGA TIMUR",
        "LHOK GOSONG TELAGA UTARA",
        "LHOK GOSONG TELAGA SELATAN",
        "LHOK PULAU BALAI",
        "LHOK PULAU BAGUK",
        "LHOK TELUK NIBUNG",
        "LHOK HALOBAN",
        "LHOK ASANTOLA",
        "LHOK UJUNG SIALIT",
        "LHOK PULAU BANYAK / SUKA MAKMUR",
        "LHOK SITI AMBIA",
    ],
    "KAB. ACEH TIMUR": [
        "LHOK KUALA BIREM BAYEUN",
        "LHOK KUALA BAYEUN / RANTAU SELAMAT",
        "LHOK KUALA PAREK / SUNGAI RAYA",
        "LHOK KUALA ALUE LHOK / PEUREULAK TIMUR",
        "LHOK KUALA LEUGE / PEUREULAK KOTA",
        "LHOK KUALA BUGAK",
        "LHOK PEUREULAK BARAT",
        "LHOK KUALA PEUDAWA",
        "LHOK IDI TIMUR",
        "LHOK KUALA IDI RAYEUK",
        "LHOK KUALA IDI CUT / DARUL AMAN",
        "LHOK KUALA BAGOK / NURUSSALAM",
        "LHOK KUALA GEULUMPANG / JULOK",
        "LHOK KUALA SIMPANG ULIM",
        "LHOK KUALA KRUENG THO / MADAT",
    ],
    "KAB. ACEH UTARA": [
        "KEC/LHOK MUARA BATU",
        "KEC/LHOK SYAMTALIRA BAYU",
        "KEC/LHOK SAMUDERA",
        "KEC/LHOK TANAH PASIR",
        "KEC/LHOK SEUNUDDON",
        "KEC/LHOK JAMBO AYE",
        "KEC/LHOK DEWANTARA",
        "KEC/LHOK LAPANG",
    ],
    "KAB. PIDIE": [
        "LHOK KUALA LHEUE / SIMPANG TIGA",
        "LHOK PASIE IE LEUBEU",
        "LHOK KUALA BEURABOE",
        "LHOK BLANG RAYA",
        "LHOK KUALA TARI / KEMBANG TANJONG",
        "LHOK TGK. DI LAWEUNG/MUARA TIGA",
        "LHOK KUALA PASIE BLANG ANOE / BATEE",
        "LHOK KUALA PEUKAN BARO / KOTA SIGLI",
        "LHOK GEUNTENG BARAT",
        "LHOK PASI BEURANDEH",
        "LHOK UJONG PIE",
    ],
    "KAB. ACEH TAMIANG": [
        "LHOK MANYAK PAYED",
        "LHOK BENDAHARA",
        "LHOK SERUWAY",
        "LHOK BANDA MULIA",
    ],
    "KAB. BIREUEN": [
        "LHOK KUALA SAMALANGA",
        "LHOK KUALA PANDRAH",
        "LHOK KUALA SIMPANG MAMPLAM",
        "LHOK KUALA JEUNIEB",
        "LHOK KUALA PLIMBANG",
        "LHOK KUALA PEUDADA",
        "LHOK KUALA JEUMPA",
        "LHOK KUALA RAJA",
        "LHOK KUALA JANGKA",
        "LHOK KUALA CEURAPEE",
        "LHOK KUALA GANDAPURA",
    ],
    "KOTA LANGSA": [
        "LHOK PUSONG / TEULAGA TUJOH",
        "LHOK SUNGAI LUENG / LANGSA TIMUR",
        "LHOK KUALA LANGSA / LANGSA KOTA",
        "LHOK BIREM / LANGSA BARAT",
    ],
    "KOTA LHOKSEUMAWE": [
        "LHOK UJONG BLANG",
        "LHOK PUSONG",
        "LHOK BLANG MANGAT/MEURAKSA",
        "LHOK BANDA SAKTI",
        "LHOK RANCONG",
    ],
    "KAB. PIDIE JAYA": [
        "LHOK KUALA KIRAN",
        "LHOK PASIE ARON",
        "LHOK ULIM",
        "LHOK MEUREUDU",
        "LHOK LANCANG PARU",
        "LHOK PANTE RAJA",
        "LHOK MEURAH DUA",
        "LHOK TRIENG GADENG",
        "LHOK KUALA BEURACAN",
    ],
}

DAFTAR_KOTA = {"SABANG", "BANDA ACEH", "LHOKSEUMAWE", "LANGSA"}


def normalisasi_kabupaten(nama_kab):
    teks = re.sub(r"\s+", " ", str(nama_kab or "").strip().upper())
    if not teks:
        return ""
    if teks in PETA_KABUPATEN_LHOK:
        return teks

    inti = re.sub(r"^(KAB\.?|KABUPATEN|KOTA)\s+", "", teks).strip()
    if inti == "ACEH BARAT DAYA":
        inti = "ABDYA"

    if inti in DAFTAR_KOTA:
        kandidat = f"KOTA {inti}"
    else:
        kandidat = f"KAB. {inti}"

    return kandidat if kandidat in PETA_KABUPATEN_LHOK else teks


def bersihkan_angka(nilai):
    if nilai is None:
        return 0
    if isinstance(nilai, Decimal):
        return int(nilai)
    if isinstance(nilai, (int, float)):
        return int(nilai)
    teks = str(nilai).replace("Rp", "").replace("rp", "").replace(".", "").replace(",", "").strip()
    if teks.isdigit():
        return int(teks)
    try:
        return int(float(teks))
    except ValueError:
        return 0


def rapikan_nomor_urut(daftar):
    for idx, baris in enumerate(daftar, start=1):
        baris["no"] = idx


def normalisasi_row_penerima(row):
    item = dict(row)
    item["id"] = item.get("id")
    item["tahun"] = str(item.get("tahun") or "").strip()
    item["semester"] = str(item.get("semester") or "").strip()
    item["kabupaten_kota"] = normalisasi_kabupaten(item.get("kabupaten_kota") or "")
    item["lhok"] = str(item.get("lhok") or "").strip().upper()
    item["nama_penerima"] = re.sub(r"\s+", " ", str(item.get("nama_penerima") or "").strip().upper())
    item["alamat"] = str(item.get("alamat") or "").strip().upper()
    item["strata_pendidikan"] = normalisasi_strata(item.get("strata_pendidikan") or "")
    item["nomor_rekening"] = str(item.get("nomor_rekening") or "").strip()
    item["jumlah_dana"] = bersihkan_angka(item.get("jumlah_dana") or 0)
    item["status_data"] = str(item.get("status_data") or "AKTIF").strip().upper()
    return item


def ambil_penerima_by_status(status=None):
    sql = """
        SELECT
            id,
            tahun,
            semester,
            kabupaten_kota,
            lhok,
            nama_penerima,
            alamat,
            strata_pendidikan,
            nomor_rekening,
            jumlah_dana,
            status_data,
            tanggal_input
        FROM tabel_penerima
    """
    params = []
    if status:
        sql += " WHERE UPPER(status_data) = %s"
        params.append(status.strip().upper())
    sql += " ORDER BY id ASC"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    hasil = [normalisasi_row_penerima(r) for r in rows]
    rapikan_nomor_urut(hasil)
    return hasil

def ambil_penerima_terkendali(kabupaten="", tampilkan_semua=False, status="AKTIF"):
    kab_bersih = normalisasi_kabupaten(kabupaten or "")
    if not kab_bersih and not tampilkan_semua:
        return []

    sql = """
        SELECT
            id,
            tahun,
            semester,
            kabupaten_kota,
            lhok,
            nama_penerima,
            alamat,
            strata_pendidikan,
            nomor_rekening,
            jumlah_dana,
            status_data,
            tanggal_input
        FROM tabel_penerima
        WHERE UPPER(status_data) = %s
    """
    status_bersih = (status or "AKTIF").strip().upper()
    params = [status_bersih]

    if kab_bersih:
        sql += " AND UPPER(kabupaten_kota) = %s"
        params.append(kab_bersih.upper())

    sql += " ORDER BY id ASC"

    with get_db_connection() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()

    hasil = [normalisasi_row_penerima(r) for r in rows]
    rapikan_nomor_urut(hasil)
    return hasil

def muat_data():
    return ambil_penerima_by_status("AKTIF")


def muat_arsip():
    return ambil_penerima_by_status("ARSIP")


def muat_semua_penerima():
    return ambil_penerima_by_status(None)


def insert_penerima_db(baris, status_data="AKTIF"):
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
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    baris["tahun"],
                    baris["semester"],
                    baris["kabupaten_kota"],
                    baris["lhok"],
                    baris["nama_penerima"],
                    baris["alamat"],
                    baris["strata_pendidikan"],
                    baris["nomor_rekening"],
                    bersihkan_angka(baris["jumlah_dana"]),
                    status_data,
                ),
            )
            new_id = cur.fetchone()[0]
        conn.commit()
    return new_id


def update_penerima_db(row_id, baris):
    sql = """
        UPDATE tabel_penerima
        SET
            tahun = %s,
            semester = %s,
            kabupaten_kota = %s,
            lhok = %s,
            nama_penerima = %s,
            alamat = %s,
            strata_pendidikan = %s,
            nomor_rekening = %s,
            jumlah_dana = %s
        WHERE id = %s
    """
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    baris["tahun"],
                    baris["semester"],
                    baris["kabupaten_kota"],
                    baris["lhok"],
                    baris["nama_penerima"],
                    baris["alamat"],
                    baris["strata_pendidikan"],
                    baris["nomor_rekening"],
                    bersihkan_angka(baris["jumlah_dana"]),
                    int(row_id),
                ),
            )
            updated = cur.rowcount
        conn.commit()
    return updated > 0


def delete_penerima_db(row_id):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tabel_penerima WHERE id = %s", (int(row_id),))
            deleted = cur.rowcount
        conn.commit()
    return deleted > 0


def update_status_penerima_db(row_ids, status_baru):
    if not row_ids:
        return 0
    bersih_ids = [int(i) for i in row_ids if str(i).isdigit()]
    if not bersih_ids:
        return 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE tabel_penerima SET status_data = %s WHERE id = ANY(%s)",
                (status_baru, bersih_ids),
            )
            jumlah = cur.rowcount
        conn.commit()
    return jumlah


def hitung_dana_sesuai_semester(strata, semester):
    strata_bersih = str(strata or "").strip().upper()
    semester_bersih = str(semester or "").strip().upper()
    tarif_dasar = next(
        (t["nominal"] for t in TARIF_JENJANG if t["jenjang"] == strata_bersih),
        0,
    )
    pengali = 2 if semester_bersih == "1 + 2" else 1
    return tarif_dasar * pengali


def ekstrak_nama_penerima(nama_lengkap):
    teks = re.sub(r"\s+", " ", str(nama_lengkap or "").strip().upper())
    if not teks:
        return ""
    return teks.strip(" -–—.,")


def kunci_duplikasi_penerima(nama_lengkap, tahun=""):
    nama_bersih = ekstrak_nama_penerima(nama_lengkap)
    tahun_bersih = re.sub(r"\s+", " ", str(tahun or "").strip().upper())
    if not nama_bersih:
        return None
    return (tahun_bersih, nama_bersih)


def cari_data_sama(daftar, nama_lengkap, tahun="", abaikan_id=None):
    kunci_target = kunci_duplikasi_penerima(nama_lengkap, tahun)
    if not kunci_target:
        return []

    tahun_target, nama_target = kunci_target
    hasil_sama = []
    for baris in daftar:
        if abaikan_id is not None and str(baris.get("id")) == str(abaikan_id):
            continue
        kunci_baris = kunci_duplikasi_penerima(
            baris.get("nama_penerima", ""), baris.get("tahun", "")
        )
        if not kunci_baris:
            continue
        tahun_baris, nama_baris = kunci_baris
        if nama_baris == nama_target and (not tahun_target or tahun_baris == tahun_target):
            hasil_sama.append(baris)
    return hasil_sama


def deteksi_penerima_ganda(daftar):
    kelompok = {}
    for idx, baris in enumerate(daftar, start=1):
        kunci = kunci_duplikasi_penerima(
            baris.get("nama_penerima", ""), baris.get("tahun", "")
        )
        if not kunci:
            continue
        kelompok.setdefault(kunci, []).append((idx, baris))

    temuan_ganda = []
    for (tahun, nama_bersih), anggota in kelompok.items():
        if len(anggota) > 1:
            temuan_ganda.append({
                "tahun": tahun or "TANPA TAHUN",
                "nama": nama_bersih,
                "jumlah": len(anggota),
                "baris": [
                    {
                        "no": b.get("no") or no_urut,
                        "id": b.get("id"),
                        "nama_asli": b.get("nama_penerima", ""),
                        "kabupaten": b.get("kabupaten_kota", ""),
                        "lhok": b.get("lhok", ""),
                        "semester": b.get("semester", ""),
                        "strata": b.get("strata_pendidikan", ""),
                        "jumlah_dana": bersihkan_angka(b.get("jumlah_dana", 0)),
                    }
                    for no_urut, b in anggota
                ],
            })

    temuan_ganda.sort(key=lambda x: (x["tahun"], x["nama"]))
    return temuan_ganda


def hitung_penerima_berulang(daftar):
    if not daftar:
        return []

    kelompok_nama = {}
    for baris in daftar:
        if not isinstance(baris, dict):
            continue

        nama_asli = re.sub(r"\s+", " ", str(baris.get("nama_penerima", "")).strip())
        kunci_nama = ekstrak_nama_penerima(nama_asli)
        if not kunci_nama:
            continue

        if kunci_nama not in kelompok_nama:
            kelompok_nama[kunci_nama] = {
                "nama": nama_asli.upper(),
                "jumlah_kemunculan": 0,
                "daftar_tahun": [],
                "daftar_jenjang": [],
                "riwayat_tahun_jenjang": [],
                "daftar_kabupaten": [],
                "daftar_lhok": [],
                "daftar_alamat": [],
                "total_dana": 0,
            }

        entry = kelompok_nama[kunci_nama]
        entry["jumlah_kemunculan"] += 1
        entry["total_dana"] += bersihkan_angka(baris.get("jumlah_dana", 0))

        tahun_val = str(baris.get("tahun", "")).strip()
        if tahun_val and tahun_val not in entry["daftar_tahun"]:
            entry["daftar_tahun"].append(tahun_val)

        jenjang_val = normalisasi_strata(baris.get("strata_pendidikan", ""))
        if jenjang_val and jenjang_val not in entry["daftar_jenjang"]:
            entry["daftar_jenjang"].append(jenjang_val)

        if tahun_val and jenjang_val:
            label_pasangan = f"{tahun_val} - {jenjang_val}"
        elif tahun_val:
            label_pasangan = tahun_val
        elif jenjang_val:
            label_pasangan = jenjang_val
        else:
            label_pasangan = ""

        if label_pasangan and label_pasangan not in entry["riwayat_tahun_jenjang"]:
            entry["riwayat_tahun_jenjang"].append(label_pasangan)

        kab_val = normalisasi_kabupaten(baris.get("kabupaten_kota", ""))
        if kab_val and kab_val not in entry["daftar_kabupaten"]:
            entry["daftar_kabupaten"].append(kab_val)

        lhok_val = re.sub(r"\s+", " ", str(baris.get("lhok", "")).strip())
        if lhok_val and lhok_val not in entry["daftar_lhok"]:
            entry["daftar_lhok"].append(lhok_val)

        alamat_val = re.sub(r"\s+", " ", str(baris.get("alamat", "")).strip())
        if alamat_val and alamat_val not in entry["daftar_alamat"]:
            entry["daftar_alamat"].append(alamat_val)

    hasil_berulang = []
    for data_penerima in kelompok_nama.values():
        if data_penerima["jumlah_kemunculan"] > 1:
            data_penerima["lintas_tahun"] = len(data_penerima["daftar_tahun"]) > 1
            hasil_berulang.append(data_penerima)

    hasil_berulang.sort(
        key=lambda x: (-x["jumlah_kemunculan"], -x["total_dana"], x["nama"])
    )
    return hasil_berulang


def cocok_semester_bank(semester_baris, semester_filter):
    if not semester_filter:
        return True
    sem_baris = str(semester_baris or "").strip().upper()
    sem_pilih = str(semester_filter or "").strip().upper()

    if sem_pilih == "1 GANJIL":
        return sem_baris in ("1 GANJIL", "1 (GANJIL", "1 (GANJIL)", "1 + 2")
    if sem_pilih == "2 GENAP":
        return sem_baris in ("2 GENAP", "2 (GENAP)", "2 (GENAP", "1 + 2")
    return sem_baris == sem_pilih


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


def bentuk_baris_import(sel, tahun_bawaan="", semester_bawaan="", paksa_hitung_dana=False):
    bersih = [str(c or "").strip() for c in sel]
    if not any(bersih):
        return None

    first_upper = bersih[0].upper()
    if first_upper in ("NO", "TAHUN", "ID") and len(bersih) >= 2 and str(bersih[1]).upper() in (
        "TAHUN",
        "SEMESTER",
        "KABUPATEN",
        "KABUPATEN/KOTA",
        "KABUPATEN_KOTA",
        "NO",
    ):
        return None

    if len(bersih) >= 10 and bersih[0].isdigit():
        offset = 1
        dana_idx = 9
    elif len(bersih) >= 9:
        offset = 0
        dana_idx = 8
    else:
        offset = 0
        dana_idx = None

    def ambil(idx):
        pos = idx + offset
        return bersih[pos] if pos < len(bersih) else ""

    tahun = ambil(0) or tahun_bawaan
    semester = ambil(1) or semester_bawaan
    kabupaten_kota = normalisasi_kabupaten(ambil(2))
    lhok = ambil(3).upper()
    nama_penerima = re.sub(r"\s+", " ", ambil(4).upper()).strip()
    alamat = ambil(5).upper()
    strata_pendidikan = normalisasi_strata(ambil(6))
    nomor_rekening = ambil(7).strip()

    if not nama_penerima:
        return None

    dana_file = bersihkan_angka(bersih[dana_idx]) if dana_idx is not None and dana_idx < len(bersih) else 0
    dana_tarif = hitung_dana_sesuai_semester(strata_pendidikan, semester)

    if paksa_hitung_dana and dana_tarif > 0:
        jumlah_dana = dana_tarif
    elif dana_file > 0:
        jumlah_dana = dana_file
    else:
        jumlah_dana = dana_tarif

    return {
        "no": 0,
        "tahun": tahun.strip(),
        "semester": semester.strip(),
        "kabupaten_kota": kabupaten_kota,
        "lhok": lhok,
        "nama_penerima": nama_penerima,
        "alamat": alamat,
        "strata_pendidikan": strata_pendidikan,
        "nomor_rekening": nomor_rekening,
        "jumlah_dana": jumlah_dana,
        "status_data": "AKTIF",
    }


def urai_teks_import(teks_mentah):
    baris_list = []
    for line in str(teks_mentah or "").splitlines():
        if not line.strip():
            continue
        if "\t" in line:
            cols = line.split("\t")
        elif ";" in line:
            cols = next(csv.reader([line], delimiter=";"))
        else:
            cols = next(csv.reader([line], delimiter=","))
        baris_list.append(cols)
    return baris_list


def baca_file_import(berkas_upload):
    nama_file = (berkas_upload.filename or "").strip().lower()
    konten_bytes = berkas_upload.read()
    if not konten_bytes:
        return []

    if nama_file.endswith(".xlsx"):
        try:
            import openpyxl
        except ImportError:
            raise RuntimeError("Library openpyxl belum terpasang untuk membaca file .xlsx.")

        wb = openpyxl.load_workbook(io.BytesIO(konten_bytes), data_only=True)
        ws = wb.active
        baris_xlsx = []
        for row in ws.iter_rows(values_only=True):
            if row is None:
                continue
            sel = ["" if cell is None else str(cell).strip() for cell in row]
            if any(sel):
                baris_xlsx.append(sel)
        return baris_xlsx

    teks = None
    for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            teks = konten_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if teks is None:
        teks = konten_bytes.decode("utf-8", errors="replace")

    return urai_teks_import(teks)


@app.template_filter("rupiah")
def format_rupiah(angka):
    nilai = bersihkan_angka(angka)
    return f"{nilai:,}".replace(",", ".")


def hitung_rekap(daftar):
    rekap_jenjang = []
    total_penerima = 0
    total_dana = 0

    for item in TARIF_JENJANG:
        jenjang = item["jenjang"]
        nominal = item["nominal"]
        cocok = [d for d in daftar if str(d.get("strata_pendidikan", "")).upper() == jenjang]
        jumlah = len(cocok)
        dana_jenjang = sum(bersihkan_angka(d.get("jumlah_dana", 0)) for d in cocok)

        rekap_jenjang.append({
            "jenjang": jenjang,
            "nominal": nominal,
            "jumlah_penerima": jumlah,
            "total_dana": dana_jenjang,
        })
        total_penerima += jumlah
        total_dana += dana_jenjang

    peta_kab = {}
    for d in daftar:
        kab = normalisasi_kabupaten(d.get("kabupaten_kota", "")) or "TIDAK TERISI"
        sem = str(d.get("semester", "")).strip().upper()
        dana_baris = bersihkan_angka(d.get("jumlah_dana", 0))
        if kab not in peta_kab:
            peta_kab[kab] = {
                "kabupaten": kab,
                "jumlah_penerima": 0,
                "total_dana": 0,
                "belum_penuh": 0,
                "sudah_penuh": 0,
            }
        peta_kab[kab]["jumlah_penerima"] += 1
        peta_kab[kab]["total_dana"] += dana_baris
        if sem == "1 + 2":
            peta_kab[kab]["sudah_penuh"] += 1
        else:
            peta_kab[kab]["belum_penuh"] += 1

    rekap_kabupaten = sorted(peta_kab.values(), key=lambda x: x["kabupaten"])

    return rekap_jenjang, total_penerima, total_dana, rekap_kabupaten


def bangun_baris_dari_form(form_data, existing_id=None):
    tahun = form_data.get("tahun", "").strip()
    semester = form_data.get("semester", "").strip()
    kabupaten_kota = normalisasi_kabupaten(form_data.get("kabupaten", "") or form_data.get("kabupaten_kota", ""))
    lhok = form_data.get("lhok", "").strip().upper()
    nama_penerima = re.sub(r"\s+", " ", (form_data.get("nama", "") or form_data.get("nama_penerima", "")).strip().upper())
    alamat = form_data.get("alamat", "").strip().upper()
    strata_pendidikan = normalisasi_strata(form_data.get("strata", "") or form_data.get("strata_pendidikan", ""))
    nomor_rekening = (form_data.get("nomor_rekenig", "") or form_data.get("nomor_rekening", "")).strip()

    dana_otomatis = hitung_dana_sesuai_semester(strata_pendidikan, semester)
    jumlah_dana = dana_otomatis if dana_otomatis > 0 else bersihkan_angka(form_data.get("jumlah_dana", 0))

    return {
        "id": existing_id,
        "no": 0,
        "tahun": tahun,
        "semester": semester,
        "kabupaten_kota": kabupaten_kota,
        "lhok": lhok,
        "nama_penerima": nama_penerima,
        "alamat": alamat,
        "strata_pendidikan": strata_pendidikan,
        "nomor_rekening": nomor_rekening,
        "jumlah_dana": jumlah_dana,
        "status_data": "AKTIF",
    }


def validasi_input_penerima(baris):
    if not baris.get("nama_penerima"):
        return "Nama penerima wajib diisi sebelum menyimpan data."
    if not baris.get("kabupaten_kota"):
        return "Kabupaten / Kota wajib dipilih atau diisi."
    if not baris.get("semester"):
        return "Semester wajib dipilih sebelum menyimpan data."
    if bersihkan_angka(baris.get("jumlah_dana", 0)) <= 0:
        return "Jumlah dana harus lebih besar dari 0 (pilih jenjang & semester atau isi nominal yang valid)."
    return None


@app.before_request
def wajib_login():
    endpoint = request.endpoint or ""
    if endpoint in ("login", "static") or endpoint.startswith("static"):
        return None
    if not session.get("logged_in"):
        return redirect(url_for("login", next=request.path))
    if endpoint == "format_bank" and session.get("role") == "admin":
        flash("Menu Format Bank khusus untuk Bendahara.", "warning")
        return redirect(url_for("dashboard"))
    return None


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("logged_in"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""

        role_login = None
        if username == ADMIN_USERNAME and check_password_hash(ADMIN_PASSWORD_HASH, password):
            role_login = "admin"
        elif username == BENDAHARA_USERNAME and check_password_hash(BENDAHARA_PASSWORD_HASH, password):
            role_login = "bendahara"

        if role_login:
            session.clear()
            session["logged_in"] = True
            session["username"] = username
            session["role"] = role_login
            flash("Berhasil masuk ke sistem.", "success")
            next_url = request.args.get("next") or url_for("dashboard")
            if not next_url.startswith("/"):
                next_url = url_for("dashboard")
            if role_login == "admin" and next_url.startswith(url_for("format_bank")):
                next_url = url_for("dashboard")
            return redirect(next_url)

        flash("Username atau password tidak sesuai.", "error")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Anda telah keluar dari sesi.", "info")
    return redirect(url_for("login"))


@app.route("/")
@app.route("/dashboard")
def dashboard():
    daftar_aktif_raw = muat_data()
    daftar_arsip_raw = muat_arsip()
    gabungan = daftar_aktif_raw + daftar_arsip_raw

    tahun_dipilih = request.args.get("tahun", "").strip()
    kab_arg = request.args.get("kab", "").strip()
    kab_dipilih = "" if kab_arg.upper() == "SEMUA" else normalisasi_kabupaten(kab_arg)
    if kab_dipilih not in PETA_KABUPATEN_LHOK:
        kab_dipilih = ""

    daftar_tahun = sorted(
        {str(d.get("tahun", "") or "").strip() for d in gabungan if str(d.get("tahun", "") or "").strip()},
        reverse=True,
    )

    if tahun_dipilih:
        daftar_tahun_aktif = [
            d for d in gabungan if str(d.get("tahun", "") or "").strip() == tahun_dipilih
        ]
    else:
        daftar_tahun_aktif = gabungan

    _, _, _, rekap_kab_semua = hitung_rekap(daftar_tahun_aktif)
    peta_jumlah_kab = {item["kabupaten"]: item["jumlah_penerima"] for item in rekap_kab_semua}

    tombol_kabupaten = [
        {
            "kabupaten": nama_kab,
            "jumlah_penerima": peta_jumlah_kab.get(nama_kab, 0),
        }
        for nama_kab in PETA_KABUPATEN_LHOK.keys()
    ]

    if kab_dipilih:
        daftar_aktif = [
            d for d in daftar_tahun_aktif
            if normalisasi_kabupaten(d.get("kabupaten_kota", "")) == kab_dipilih
        ]
    else:
        daftar_aktif = daftar_tahun_aktif

    rekap_jenjang, total_penerima, total_dana, rekap_kabupaten = hitung_rekap(daftar_aktif)
    temuan_ganda = deteksi_penerima_ganda(daftar_aktif)
    penerima_berulang = hitung_penerima_berulang(daftar_aktif)
    jumlah_kab_aktif = sum(1 for k in rekap_kab_semua if k["jumlah_penerima"] > 0)

    return render_template(
        "dashboard.html",
        data_jenjang=rekap_jenjang,
        total_penerima=total_penerima,
        total_dana=total_dana,
        rekap_kabupaten=rekap_kabupaten,
        jumlah_kab_aktif=jumlah_kab_aktif,
        total_kab_sistem=len(PETA_KABUPATEN_LHOK),
        daftar_tahun=daftar_tahun,
        tahun_dipilih=tahun_dipilih,
        kab_dipilih=kab_dipilih,
        tombol_kabupaten=tombol_kabupaten,
        daftar_aktif=daftar_aktif,
        total_aktif_saja=len(daftar_aktif_raw),
        total_arsip_saja=len(daftar_arsip_raw),
        temuan_ganda=temuan_ganda,
        penerima_berulang=penerima_berulang,
    )


@app.route("/penerima", methods=["GET", "POST"])
def penerima():
    if request.method == "POST":
        baris_baru = bangun_baris_dari_form(request.form)
        pesan_validasi = validasi_input_penerima(baris_baru)
        if pesan_validasi:
            flash(pesan_validasi, "warning")
            return redirect(url_for("penerima"))

        izinkan_sama = bool(request.form.get("izinkan_nama_sama"))
        calon_sama = ambil_penerima_terkendali(
            kabupaten=baris_baru["kabupaten_kota"],
            tampilkan_semua=False,
            status="AKTIF",
        )
        data_sama = cari_data_sama(
            calon_sama,
            baris_baru["nama_penerima"],
            tahun=baris_baru["tahun"],
        )

        if data_sama and not izinkan_sama:
            info_daerah = ", ".join(
                sorted({
                    f"{d.get('kabupaten_kota') or '-'} | {d.get('lhok') or '-'} ({d.get('semester') or '-'})"
                    for d in data_sama
                })
            )
            label_tahun = f" pada Tahun Ajaran {baris_baru['tahun']}" if baris_baru["tahun"] else ""
            flash(
                f"INPUT DIBLOKIR: Nama '{baris_baru['nama_penerima']}' sudah terdaftar{label_tahun} sebanyak {len(data_sama)} data [{info_daerah}]. Periksa kembali sebelum menyimpan.",
                "warning",
            )
            return redirect(url_for("penerima"))

        insert_penerima_db(baris_baru, status_data="AKTIF")
        flash("Data penerima berhasil disimpan ke PostgreSQL.", "success")
        return redirect(url_for("penerima"))

    kabupaten_dipilih = request.args.get("kabupaten", "").strip()
    tampilkan_semua = request.args.get("tampilkan_semua") == "1"

    daftar = ambil_penerima_terkendali(
        kabupaten=kabupaten_dipilih,
        tampilkan_semua=tampilkan_semua,
        status="AKTIF",
    )

    kumpulan_tahun = {
        str(d.get("tahun", "") or "").strip()
        for d in daftar
        if str(d.get("tahun", "") or "").strip()
    }
    kumpulan_tahun.update(["2026/2027", "2025/2026", "2024/2025"])
    daftar_tahun = sorted(kumpulan_tahun, reverse=True)

    rekap_jenjang, total_penerima, total_dana, rekap_kabupaten = hitung_rekap(daftar)
    temuan_ganda = deteksi_penerima_ganda(daftar)
    penerima_berulang = hitung_penerima_berulang(daftar)

    return render_template(
        "penerima.html",
        data_jenjang=TARIF_JENJANG,
        peta_kabupaten_lhok=PETA_KABUPATEN_LHOK,
        daftar_tahun=daftar_tahun,
        rekap_jenjang=rekap_jenjang,
        rekap_kabupaten=rekap_kabupaten,
        daftar_penerima=daftar,
        total_terdaftar=total_penerima,
        total_dana=total_dana,
        temuan_ganda=temuan_ganda,
        penerima_berulang=penerima_berulang,
        kabupaten_dipilih=kabupaten_dipilih,
        tampilkan_semua=tampilkan_semua,
    )

@app.route("/penerima/edit/<row_id>", methods=["POST"])
def edit_penerima(row_id):
    daftar = muat_data()
    target = next((b for b in daftar if str(b.get("id")) == str(row_id)), None)
    if target is None:
        flash("Data penerima yang ingin diperbarui tidak ditemukan.", "warning")
        return redirect(url_for("penerima"))

    baris_diperbarui = bangun_baris_dari_form(request.form, existing_id=row_id)
    pesan_validasi = validasi_input_penerima(baris_diperbarui)
    if pesan_validasi:
        flash(pesan_validasi, "warning")
        return redirect(url_for("penerima"))

    data_sama = cari_data_sama(
        daftar,
        baris_diperbarui["nama_penerima"],
        tahun=baris_diperbarui["tahun"],
        abaikan_id=row_id,
    )
    if data_sama:
        info_daerah = ", ".join(
            sorted({
                f"{d.get('kabupaten_kota') or '-'} ({d.get('semester') or '-'})"
                for d in data_sama
            })
        )
        label_tahun = f" pada Tahun Ajaran {baris_diperbarui['tahun']}" if baris_diperbarui["tahun"] else ""
        flash(
            f"PERUBAHAN DIBLOKIR: Nama '{baris_diperbarui['nama_penerima']}' sudah dipakai data lain{label_tahun} [{info_daerah}].",
            "warning",
        )
        return redirect(url_for("penerima"))

    update_penerima_db(row_id, baris_diperbarui)
    flash("Data penerima berhasil diperbarui.", "success")
    return redirect(url_for("penerima"))


@app.route("/penerima/hapus/<row_id>", methods=["POST"])
def hapus_penerima(row_id):
    delete_penerima_db(row_id)
    flash("Data penerima berhasil dihapus.", "success")
    return redirect(url_for("penerima"))


@app.route("/realisasi-penyaluran", methods=["GET"])
def realisasi_penyaluran():
    daftar = muat_data()
    _, total_penerima, total_dana, rekap_kabupaten = hitung_rekap(daftar)

    return render_template(
        "realisasi_penyaluran.html",
        peta_kabupaten_lhok=PETA_KABUPATEN_LHOK,
        rekap_kabupaten=rekap_kabupaten,
        total_terdaftar=total_penerima,
        total_dana=total_dana,
        daftar_penerima=daftar,
    )


@app.route("/realisasi-semester-2", methods=["POST"])
def realisasi_semester_2():
    kab_terpilih = [normalisasi_kabupaten(k) for k in request.form.getlist("kabupaten_realisasi") if k.strip()]
    tahun_filter = request.form.get("tahun_realisasi", "").strip()
    semester_filter = request.form.get("semester_realisasi", "").strip().upper()

    if not kab_terpilih:
        flash("Silakan pilih minimal satu KABUPATEN/KOTA terlebih dahulu sebelum menekan REALISASI SEMESTER 2.", "warning")
        return redirect(url_for("realisasi_penyaluran"))

    daftar = muat_data()
    jumlah_diupdate = 0
    kab_sudah_penuh = []
    kab_tanpa_data = []

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            for kab in kab_terpilih:
                baris_kab = [
                    b for b in daftar
                    if normalisasi_kabupaten(b.get("kabupaten_kota", "")) == kab
                    and (not tahun_filter or str(b.get("tahun", "")).strip() == tahun_filter)
                ]

                if not baris_kab:
                    kab_tanpa_data.append(kab)
                    continue

                baris_belum_penuh = []
                for b in baris_kab:
                    sem_baris = str(b.get("semester", "")).strip().upper()
                    if sem_baris == "1 + 2":
                        continue
                    if semester_filter == "1 GANJIL":
                        if "1" in sem_baris and "2" not in sem_baris:
                            baris_belum_penuh.append(b)
                    else:
                        baris_belum_penuh.append(b)

                if not baris_belum_penuh:
                    kab_sudah_penuh.append(kab)
                    continue

                for b in baris_belum_penuh:
                    dana_baru = hitung_dana_sesuai_semester(b.get("strata_pendidikan", ""), "1 + 2")
                    if dana_baru <= 0:
                        dana_baru = bersihkan_angka(b.get("jumlah_dana", 0)) * 2

                    cur.execute(
                        """
                        UPDATE tabel_penerima
                        SET semester = '1 + 2', jumlah_dana = %s
                        WHERE id = %s
                        """,
                        (dana_baru, int(b["id"])),
                    )
                    jumlah_diupdate += 1
        conn.commit()

    if jumlah_diupdate > 0:
        flash(
            f"REALISASI SEMESTER 2 berhasil diterapkan pada {jumlah_diupdate} data penerima (SEMESTER menjadi '1 + 2' dan dana digandakan).",
            "success",
        )

    if kab_sudah_penuh:
        daftar_kab_penuh = ", ".join(kab_sudah_penuh)
        label_tahun = f" untuk Tahun Ajaran {tahun_filter}" if tahun_filter else ""
        flash(
            f"KABUPATEN/KOTA ({daftar_kab_penuh}) sudah direalisasi penuh untuk dua semester / Tahun Ajaran{label_tahun}.",
            "info",
        )

    if kab_tanpa_data and jumlah_diupdate == 0 and not kab_sudah_penuh:
        flash(
            f"Tidak ditemukan data penerima pada KABUPATEN/KOTA: {', '.join(kab_tanpa_data)}.",
            "warning",
        )

    return redirect(url_for("realisasi_penyaluran"))


@app.route("/format-bank", methods=["GET", "POST"])
def format_bank():
    daftar = muat_data()
    kab_terpilih = []
    tahun_filter = ""
    semester_filter = ""
    data_bank = []
    total_dana_bank = 0
    sudah_tampilkan = False

    if request.method == "POST":
        sudah_tampilkan = True
        kab_terpilih = [normalisasi_kabupaten(k) for k in request.form.getlist("kabupaten_bank") if k.strip()]
        tahun_filter = request.form.get("tahun_bank", "").strip()
        semester_filter = request.form.get("semester_bank", "").strip()

        if not kab_terpilih:
            flash("Silakan pilih minimal satu KABUPATEN/KOTA yang sudah siap datanya, lalu tekan TAMPILKAN BANK.", "warning")
        else:
            sumber = [
                b for b in daftar
                if normalisasi_kabupaten(b.get("kabupaten_kota", "")) in kab_terpilih
                and (not tahun_filter or str(b.get("tahun", "")).strip() == tahun_filter)
                and cocok_semester_bank(b.get("semester", ""), semester_filter)
            ]
            for idx, b in enumerate(sumber, start=1):
                dana_baris = bersihkan_angka(b.get("jumlah_dana", 0))
                total_dana_bank += dana_baris
                data_bank.append({
                    "no": idx,
                    "nomor_rekening": str(b.get("nomor_rekening", "")).strip(),
                    "nama_penerima": ekstrak_nama_penerima(b.get("nama_penerima", "")),
                    "jumlah_dana": dana_baris,
                    "kabupaten_kota": normalisasi_kabupaten(b.get("kabupaten_kota", "")),
                })

            if not data_bank:
                flash(
                    "Tidak ada data penerima yang cocok dengan pilihan KABUPATEN/KOTA, Tahun Ajaran, dan SEMESTER tersebut.",
                    "info",
                )

    return render_template(
        "format_bank.html",
        peta_kabupaten_lhok=PETA_KABUPATEN_LHOK,
        kab_terpilih=kab_terpilih,
        tahun_filter=tahun_filter,
        semester_filter=semester_filter,
        data_bank=data_bank,
        total_dana_bank=total_dana_bank,
        sudah_tampilkan=sudah_tampilkan,
    )


@app.route("/import-data", methods=["GET", "POST"])
def import_data():
    daftar = muat_data()
    ringkasan_import = None
    tahun_bawaan = ""
    semester_bawaan = ""
    paksa_hitung_dana = False
    teks_tempel = ""

    if request.method == "POST":
        tahun_bawaan = (
            request.form.get("tahun_bawaan")
            or request.form.get("tahun_import")
            or ""
        ).strip()
        semester_bawaan = (
            request.form.get("semester_bawaan")
            or request.form.get("semester_import")
            or ""
        ).strip()
        paksa_hitung_dana = bool(request.form.get("paksa_hitung_dana"))

        if "blokir_nama_sama" in request.form:
            izinkan_ganda = False
        else:
            izinkan_ganda = bool(request.form.get("izinkan_ganda_import"))

        mode_import = (request.form.get("mode_import") or "tambah").strip().lower()
        teks_tempel = request.form.get("teks_import", "")
        berkas_upload = request.files.get("file_import")

        kumpulan_sel = []

        if berkas_upload and berkas_upload.filename:
            try:
                kumpulan_sel.extend(baca_file_import(berkas_upload))
            except RuntimeError as err:
                flash(str(err), "warning")
                return redirect(url_for("import_data"))

        if teks_tempel and teks_tempel.strip():
            kumpulan_sel.extend(urai_teks_import(teks_tempel))

        if not kumpulan_sel:
            flash("File tidak terdeteksi atau kosong. Silakan pilih file (.csv / .xlsx / .txt) atau tempelkan data baris terlebih dahulu.", "warning")
            return redirect(url_for("import_data"))

        basis_data = [] if mode_import == "timpa" else list(daftar)

        ditambahkan = 0
        dilewati_duplikat = 0
        dilewati_tidak_valid = 0
        baris_untuk_disimpan = []

        for sel in kumpulan_sel:
            baris_baru = bentuk_baris_import(
                sel,
                tahun_bawaan=tahun_bawaan,
                semester_bawaan=semester_bawaan,
                paksa_hitung_dana=paksa_hitung_dana,
            )
            if not baris_baru:
                dilewati_tidak_valid += 1
                continue

            if not baris_baru.get("kabupaten_kota"):
                baris_baru["kabupaten_kota"] = "TIDAK TERISI"

            if not baris_baru.get("semester"):
                baris_baru["semester"] = "1 GANJIL"

            if bersihkan_angka(baris_baru.get("jumlah_dana", 0)) <= 0:
                dilewati_tidak_valid += 1
                continue

            data_sama = cari_data_sama(
                basis_data,
                baris_baru["nama_penerima"],
                tahun=baris_baru["tahun"],
            )
            if data_sama and not izinkan_ganda:
                dilewati_duplikat += 1
                continue

            basis_data.append(baris_baru)
            baris_untuk_disimpan.append(baris_baru)
            ditambahkan += 1

        if ditambahkan > 0 or mode_import == "timpa":
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    if mode_import == "timpa":
                        cur.execute("DELETE FROM tabel_penerima WHERE status_data = 'AKTIF'")
                    for b in baris_untuk_disimpan:
                        cur.execute(
                            """
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
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'AKTIF')
                            """,
                            (
                                b["tahun"],
                                b["semester"],
                                b["kabupaten_kota"],
                                b["lhok"],
                                b["nama_penerima"],
                                b["alamat"],
                                b["strata_pendidikan"],
                                b["nomor_rekening"],
                                bersihkan_angka(b["jumlah_dana"]),
                            ),
                        )
                conn.commit()
            daftar = muat_data()

        ringkasan_import = {
            "ditambahkan": ditambahkan,
            "dilewati_duplikat": dilewati_duplikat,
            "dilewati_tidak_valid": dilewati_tidak_valid,
        }

        flash(
            f"Import selesai: {ditambahkan} data ditambahkan, {dilewati_duplikat} duplikat dilewati, {dilewati_tidak_valid} baris tidak valid/kosong.",
            "success" if ditambahkan > 0 else "warning",
        )

    rekap_jenjang, total_penerima, total_dana, rekap_kabupaten = hitung_rekap(daftar)

    return render_template(
        "import_data.html",
        data_jenjang=TARIF_JENJANG,
        peta_kabupaten_lhok=PETA_KABUPATEN_LHOK,
        rekap_jenjang=rekap_jenjang,
        rekap_kabupaten=rekap_kabupaten,
        total_terdaftar=total_penerima,
        total_dana=total_dana,
        ringkasan_import=ringkasan_import,
        tahun_bawaan=tahun_bawaan,
        semester_bawaan=semester_bawaan,
        paksa_hitung_dana=paksa_hitung_dana,
        teks_tempel=teks_tempel,
    )


@app.route("/arsip", methods=["GET", "POST"])
def arsip():
    daftar_aktif = muat_data()
    daftar_arsip = muat_arsip()

    if request.method == "POST":
        aksi = (request.form.get("aksi") or "").strip().lower()

        if aksi == "arsipkan_tahun":
            tahun_target = (request.form.get("tahun_arsip") or "").strip()
            kab_target = normalisasi_kabupaten(request.form.get("kab_arsip") or "")

            if not tahun_target and not kab_target:
                flash("Pilih Tahun Ajaran atau Kabupaten/Kota terlebih dahulu untuk mengarsipkan data.", "warning")
                return redirect(url_for("arsip"))

            id_dipindahkan = [
                b["id"] for b in daftar_aktif
                if (not tahun_target or str(b.get("tahun", "")).strip() == tahun_target)
                and (not kab_target or normalisasi_kabupaten(b.get("kabupaten_kota", "")) == kab_target)
            ]

            if not id_dipindahkan:
                flash("Tidak ada data aktif yang cocok dengan kriteria arsip yang dipilih.", "info")
                return redirect(url_for("arsip"))

            jumlah = update_status_penerima_db(id_dipindahkan, "ARSIP")
            flash(
                f"Berhasil mengarsipkan {jumlah} data penerima ke Data Arsip (terkunci dari edit/hapus langsung).",
                "success",
            )
            return redirect(url_for("arsip"))

        if aksi == "restore_item":
            row_id = (request.form.get("row_id") or "").strip()
            target = next((b for b in daftar_arsip if str(b.get("id")) == row_id), None)
            if not target:
                flash("Data arsip yang ingin di-restore tidak ditemukan.", "warning")
                return redirect(url_for("arsip"))

            update_status_penerima_db([row_id], "AKTIF")
            flash(
                f"Data '{target.get('nama_penerima', '')}' berhasil di-restore ke Data Penerima aktif.",
                "success",
            )
            return redirect(url_for("arsip"))

        if aksi == "restore_tahun":
            tahun_restore = (request.form.get("tahun_restore") or "").strip()
            if not tahun_restore:
                flash("Pilih Tahun Ajaran arsip yang ingin di-restore terlebih dahulu.", "warning")
                return redirect(url_for("arsip"))

            id_dipulihkan = [
                b["id"] for b in daftar_arsip
                if str(b.get("tahun", "")).strip() == tahun_restore
            ]

            if not id_dipulihkan:
                flash(f"Tidak ada data arsip untuk Tahun Ajaran {tahun_restore}.", "info")
                return redirect(url_for("arsip"))

            jumlah = update_status_penerima_db(id_dipulihkan, "AKTIF")
            flash(
                f"Berhasil me-restore {jumlah} data arsip Tahun Ajaran {tahun_restore} kembali ke Data Penerima aktif.",
                "success",
            )
            return redirect(url_for("arsip"))

    tahun_filter = request.args.get("tahun", "").strip()
    kab_arg = request.args.get("kab", "").strip()
    kab_filter = normalisasi_kabupaten(kab_arg) if kab_arg else ""

    daftar_tahun_aktif = sorted(
        {str(b.get("tahun", "") or "").strip() for b in daftar_aktif if str(b.get("tahun", "") or "").strip()},
        reverse=True,
    )
    daftar_tahun_arsip = sorted(
        {str(b.get("tahun", "") or "").strip() for b in daftar_arsip if str(b.get("tahun", "") or "").strip()},
        reverse=True,
    )

    arsip_tampil = [
        b for b in daftar_arsip
        if (not tahun_filter or str(b.get("tahun", "")).strip() == tahun_filter)
        and (not kab_filter or normalisasi_kabupaten(b.get("kabupaten_kota", "")) == kab_filter)
    ]

    total_dana_arsip = sum(bersihkan_angka(b.get("jumlah_dana", 0)) for b in arsip_tampil)
    total_dana_semua_arsip = sum(bersihkan_angka(b.get("jumlah_dana", 0)) for b in daftar_arsip)

    return render_template(
        "arsip.html",
        peta_kabupaten_lhok=PETA_KABUPATEN_LHOK,
        daftar_aktif=daftar_aktif,
        daftar_arsip=daftar_arsip,
        arsip_tampil=arsip_tampil,
        daftar_tahun_aktif=daftar_tahun_aktif,
        daftar_tahun_arsip=daftar_tahun_arsip,
        tahun_filter=tahun_filter,
        kab_filter=kab_filter,
        total_dana_arsip=total_dana_arsip,
        total_dana_semua_arsip=total_dana_semua_arsip,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)