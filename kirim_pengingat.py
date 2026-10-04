"""Script pengingat untuk GitHub Actions (100% gratis).
Mengirim pesan pengingat ke semua CHAT_IDS via Bot API.
Contoh Secrets: CHAT_IDS = "5148775995,12345678" (pisahkan koma)
"""
import os
import urllib.request
import urllib.parse
import json

TOKEN = os.getenv("BOT_TOKEN", "")
CHAT_IDS = [c.strip() for c in os.getenv("CHAT_IDS", "").split(",") if c.strip()]

PESAN = (
    "🚨 *PENGINGAT LOGISTIK - WAKTU LAPORAN* 🚨\n\n"
    "Waktu sudah menunjukkan pukul *21.00 WIB*.\n"
    "Mohon untuk segera menyelesaikan dan mengirimkan rekap data logistik makan/snack!\n\n"
    "Silakan buka bot dan ketik /start untuk input data."
)

def kirim(chat_id):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = urllib.parse.urlencode(
        {"chat_id": chat_id, "text": PESAN, "parse_mode": "Markdown"}
    ).encode()
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

if not TOKEN:
    raise SystemExit("BOT_TOKEN belum diisi di Secrets.")
if not CHAT_IDS:
    raise SystemExit("CHAT_IDS belum diisi di Secrets/Variables.")

for cid in CHAT_IDS:
    try:
        kirim(cid)
        print(f"Terkirim ke {cid}")
    except Exception as e:
        print(f"Gagal ke {cid}: {e}")
