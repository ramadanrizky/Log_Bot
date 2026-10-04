import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import re
import schedule
import time
import threading
from datetime import datetime
from flask import Flask, request, abort

TOKEN = os.getenv("BOT_TOKEN", '8820103343:AAEpQjFpp7PsHJucdPei-GEc_JOPILmjKt8')
if not TOKEN:
    raise SystemExit("BOT_TOKEN belum diisi! Isi di Environment Variable Railway/Render.")
bot = telebot.TeleBot(TOKEN)

FILE_USERS = 'daftar_chat.txt'
NAMA_FILE = 'LOG'

user_data = {}

# Set untuk mencatat chat_id yang sedang dalam status harus diingatkan terus-menerus
pengingat_aktif = set()

# --- MANAJEMEN CHAT ID ---

def simpan_chat_id(chat_id):
    if not os.path.exists(FILE_USERS):
        open(FILE_USERS, 'w').close()

    with open(FILE_USERS, 'r') as f:
        daftar = [baris.strip() for baris in f.readlines()]

    if str(chat_id) not in daftar:
        with open(FILE_USERS, 'a') as f:
            f.write(f"{chat_id}\n")
        print(f"[{datetime.now()}] Chat ID baru didaftarkan: {chat_id}")
    else:
        print(f"[{datetime.now()}] Chat ID sudah terdaftar: {chat_id}")

# --- SISTEM PENGINGAT BERULANG ---

def picu_pengingat_malam():
    """Dijalankan tepat pukul 21.00 untuk mengaktifkan status pengingat bagi semua user"""
    print(f"[{datetime.now()}] picu_pengingat_malam dijalankan...")
    if not os.path.exists(FILE_USERS):
        print("File daftar_chat.txt tidak ada, pengingat batal.")
        return

    with open(FILE_USERS, 'r') as f:
        daftar_chat = [baris.strip() for baris in f.readlines() if baris.strip()]

    if not daftar_chat:
        print("Daftar chat kosong, pengingat batal.")
        return

    # Masukkan semua pengguna/grup ke dalam antrean pengingat aktif
    for c_id in daftar_chat:
        pengingat_aktif.add(c_id)

    print(f"Pengingat diaktifkan untuk: {daftar_chat}")
    # Langsung kirim pesan pertama tanpa menunggu 5 menit
    kirim_loop_pengingat()

def kirim_loop_pengingat():
    """Mengirim pesan berulang ke chat_id yang belum menekan tombol konfirmasi"""
    if not pengingat_aktif:
        return

    print(f"[{datetime.now()}] Mengirim pengingat ke: {list(pengingat_aktif)}")
    # Tombol konfirmasi resmi untuk mematikan pengingat
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("✅ Saya Sudah Input / Matikan Pengingat", callback_data="stop_pengingat"))

    pesan = (
        "🚨 **PENGINGAT LOGISTIK - WAKTU LAPORAN** 🚨\n\n"
        "Waktu sudah menunjukkan pukul **21.00 WIB**.\n"
        "Mohon untuk segera menyelesaikan dan mengirimkan rekap data logistik makan/snack!\n\n"
        "⚠️ *Notifikasi ini akan terus muncul sampai Anda menekan tombol di bawah.*"
    )

    # Kirim ke setiap pengguna yang statusnya masih aktif
    for c_id in list(pengingat_aktif):
        try:
            bot.send_message(c_id, pesan, reply_markup=markup, parse_mode="Markdown")
            print(f"Pengingat terkirim ke {c_id}")
        except Exception as e:
            print(f"Gagal kirim ke {c_id}: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "stop_pengingat")
def konfirmasi_matikan_pengingat(call):
    chat_id_str = str(call.message.chat.id)
    
    if chat_id_str in pengingat_aktif:
        pengingat_aktif.remove(chat_id_str)
        bot.answer_callback_query(call.id, "Pengingat berhasil dinonaktifkan!")
        bot.edit_message_text(
            "✅ **Pengingat dimatikan.** Terima kasih atas konfirmasinya. Silakan ketik /start jika ingin memulai input data.",
            call.message.chat.id,
            call.message.message_id
        )
    else:
        bot.answer_callback_query(call.id, "Pengingat untuk Anda sudah tidak aktif.")

def jalankan_jadwal():
    # PENTING: schedule memakai jam server lokal (jam laptop/VPS).
    # Pastikan jam laptop sudah WIB. Jika bot jalan di VPS UTC,
    # ganti "21:00" menjadi "14:00" (14:00 UTC = 21:00 WIB).
    schedule.clear()
    schedule.every().day.at("21:00").do(picu_pengingat_malam)

    # 2. Kirim pesan setiap 5 menit (hanya dikirim ke user yang masih ada di set pengingat_aktif)
    schedule.every(5).minutes.do(kirim_loop_pengingat)

    print(f"[{datetime.now()}] Scheduler aktif. Jadwal: {schedule.get_jobs()}")
    while True:
        schedule.run_pending()
        time.sleep(10)

# NOTE: thread scheduler HANYA dijalankan di __main__ di bawah.
# Jangan start thread di sini agar tidak double (pesan ganda).
# --- HANDLER BOT TELEGRAM ---

@bot.message_handler(commands=['cek_jadwal', 'test_pengingat'])
def test_pengingat(message):
    """Perintah debug: /test_pengingat untuk tes pengingat langsung tanpa menunggu jam 21.00"""
    simpan_chat_id(message.chat.id)
    pengingat_aktif.add(str(message.chat.id))
    bot.send_message(message.chat.id, f"🧪 Tes pengingat... (jadwal aktif: {schedule.get_jobs()}, antrean: {list(pengingat_aktif)})")
    kirim_loop_pengingat()

@bot.message_handler(commands=['stop'])
def stop_manual(message):
    chat_id_str = str(message.chat.id)
    if chat_id_str in pengingat_aktif:
        pengingat_aktif.remove(chat_id_str)
        bot.send_message(message.chat.id, "✅ Pengingat dimatikan via /stop.")
    else:
        bot.send_message(message.chat.id, "ℹ️ Tidak ada pengingat aktif untuk Anda.")

@bot.message_handler(commands=['start'])
def start(message):
    # Daftarkan chat_id pengguna/grup untuk menerima notifikasi berkala
    simpan_chat_id(message.chat.id)
    tampilkan_menu_utama(message.chat.id)

def tampilkan_menu_utama(chat_id):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("📝 Data Makan", callback_data="menu_data"),
        InlineKeyboardButton("🧪 Test Pengingat", callback_data="menu_test")
    )
    bot.send_message(chat_id, "Kamu mau apa?", reply_markup=markup)

def tampilkan_pilihan_logistik(chat_id, message_id=None):
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🍱 Makanan", callback_data="kat_makanan"),
        InlineKeyboardButton("🍿 Snack", callback_data="kat_snack")
    )
    teks = "Pilih jenis logistik:"
    if message_id:
        bot.edit_message_text(teks, chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, teks, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data in ("menu_data", "menu_test"))
def proses_menu_utama(call):
    chat_id = call.message.chat.id
    if call.data == "menu_data":
        bot.answer_callback_query(call.id, "Silakan pilih jenis logistik")
        tampilkan_pilihan_logistik(chat_id, call.message.message_id)
    else:
        bot.answer_callback_query(call.id, "Menjalankan tes pengingat...")
        simpan_chat_id(chat_id)
        pengingat_aktif.add(str(chat_id))
        bot.edit_message_text(
            f"🧪 Tes pengingat dijalankan... (antrean: {len(pengingat_aktif)} chat)",
            chat_id,
            call.message.message_id
        )
        kirim_loop_pengingat()

@bot.message_handler(commands=['tambah'])
def tambah(message):
    # Langsung ke pilihan logistik tanpa menu utama
    simpan_chat_id(message.chat.id)
    tampilkan_pilihan_logistik(message.chat.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('kat_'))
def proses_kategori(call):
    chat_id = call.message.chat.id
    kategori = call.data.split('_')[1]
    user_data[chat_id] = {'kategori': kategori.capitalize(), 'drops': [], 'terisi': 0, 'rukan': 0}

    if kategori == 'makanan':
        markup = InlineKeyboardMarkup()
        markup.row(
            InlineKeyboardButton("🌅 Pagi", callback_data="wkt_Pagi"),
            InlineKeyboardButton("☀️ Siang", callback_data="wkt_Siang"),
            InlineKeyboardButton("🌙 Malam", callback_data="wkt_Malam")
        )
        bot.edit_message_text("Pilih waktu makan:", chat_id, call.message.message_id, reply_markup=markup)
    else:
        user_data[chat_id]['waktu'] = ''
        tampilkan_pilihan_co(chat_id, call.message.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('wkt_'))
def proses_waktu(call):
    chat_id = call.message.chat.id
    user_data[chat_id]['waktu'] = call.data.split('_')[1]
    tampilkan_pilihan_co(chat_id, call.message.message_id)

def tampilkan_pilihan_co(chat_id, message_id):
    markup = InlineKeyboardMarkup(row_width=4)
    tombol = [InlineKeyboardButton(f"CO-{i}", callback_data=f"co_{i}") for i in range(1, 9)]
    markup.add(*tombol)
    bot.edit_message_text("Pilih CO (Kompi):", chat_id, message_id, reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith('co_'))
def proses_co(call):
    chat_id = call.message.chat.id
    user_data[chat_id]['co'] = call.data.split('_')[1]
    
    msg = bot.edit_message_text(
        "Masukkan **Hari dan Tanggal**\nContoh: `Selasa, 22 September 2026`", 
        chat_id, 
        call.message.message_id, 
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(msg, proses_tanggal)

def proses_tanggal(message):
    chat_id = message.chat.id
    user_data[chat_id]['tanggal'] = message.text.strip()
    
    msg = bot.send_message(chat_id, "Masukkan **TOTAL KADET** (hanya angka):", parse_mode="Markdown")
    bot.register_next_step_handler(msg, proses_total_kadet)

def proses_total_kadet(message):
    chat_id = message.chat.id
    try:
        total = int(message.text.strip())
        user_data[chat_id]['total_kadet'] = total
        
        if user_data[chat_id]['kategori'] == 'Makanan':
            msg = bot.send_message(chat_id, "Masukkan jumlah porsi makan di **Rukan** (hanya angka):", parse_mode="Markdown")
            bot.register_next_step_handler(msg, proses_rukan)
        else:
            user_data[chat_id]['rukan'] = 0
            user_data[chat_id]['terisi'] = 0
            tanya_opsi_drop(chat_id)
            
    except ValueError:
        msg = bot.send_message(chat_id, "⚠️ Harap masukkan angka saja!")
        bot.register_next_step_handler(msg, proses_total_kadet)

def proses_rukan(message):
    chat_id = message.chat.id
    try:
        rukan = int(message.text.strip())
        user_data[chat_id]['rukan'] = rukan
        user_data[chat_id]['terisi'] = rukan
        
        sisa = user_data[chat_id]['total_kadet'] - rukan
        if sisa < 0:
            msg = bot.send_message(
                chat_id, 
                f"⚠️ Porsi Rukan ({rukan}) melebihi Total Kadet ({user_data[chat_id]['total_kadet']}). Masukkan ulang angka Rukan:"
            )
            bot.register_next_step_handler(msg, proses_rukan)
            return

        if sisa == 0:
            selesaikan_dan_cetak(chat_id)
        else:
            tanya_opsi_drop(chat_id)
    except ValueError:
        msg = bot.send_message(chat_id, "⚠️ Masukkan angka yang valid!")
        bot.register_next_step_handler(msg, proses_rukan)

def tanya_opsi_drop(chat_id):
    sisa = user_data[chat_id]['total_kadet'] - user_data[chat_id]['terisi']
    kategori = user_data[chat_id]['kategori']
    satuan = "Kotak" if kategori == "Makanan" else "Porsi/Kotak"
    
    teks = (
        f"📌 Sisa {kategori.lower()} yang belum dialokasikan: **{sisa}** dari total {user_data[chat_id]['total_kadet']}.\n\n"
        "Silakan **salin template di bawah ini** lalu ubah isinya:\n\n"
        "🔹 **Template Tanpa Keterangan Tambahan:**\n"
        f"```\nTempat | Jam | Jumlah {satuan}\n```\n"
        "*Contoh:*\n"
        "```\nMako Lama | 04.30 | 3\n```\n\n"
        "🔹 **Template Dengan Keterangan Sakit / A.N:**\n"
        f"```\nTempat | Jam | Jumlah {satuan} | Keterangan\n```\n"
        "*Contoh:*\n"
        "```\nMess KDA A1 Lama | 04.30 | 19 | 18 Sakit + 1 bubur A.N SK FIS M. Arvan\n```"
    )
    msg = bot.send_message(chat_id, teks, parse_mode="Markdown")
    bot.register_next_step_handler(msg, proses_input_drop)

def proses_input_drop(message):
    chat_id = message.chat.id
    teks = message.text.strip()
    
    teks_dibersihkan = re.sub(r'\s+[Ili/]\s+', '|', teks)
    teks_dibersihkan = teks_dibersihkan.replace(',', '|')
    
    parts = [p.strip() for p in teks_dibersihkan.split('|') if p.strip() != '']
    
    if len(parts) < 3:
        msg = bot.send_message(
            chat_id, 
            "⚠️ **Format belum lengkap!**\n\nContoh yang benar:\n```\nNama Tempat | 04.30 | 5\n```",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(msg, proses_input_drop)
        return

    tempat = parts[0]
    jam = parts[1]
    
    try:
        kotak = int(parts[2])
    except ValueError:
        msg = bot.send_message(chat_id, f"⚠️ Jumlah (`{parts[2]}`) harus berupa angka!\nSilakan coba lagi:")
        bot.register_next_step_handler(msg, proses_input_drop)
        return
        
    keterangan = parts[3] if len(parts) > 3 else ""

    sisa_tersedia = user_data[chat_id]['total_kadet'] - user_data[chat_id]['terisi']
    if kotak > sisa_tersedia:
        msg = bot.send_message(
            chat_id, 
            f"⚠️ Jumlah ({kotak}) melebihi sisa porsi yang ada ({sisa_tersedia}). Masukkan data yang sesuai:"
        )
        bot.register_next_step_handler(msg, proses_input_drop)
        return

    if keterangan:
        baris = f"{tempat} ({jam}) : {kotak} Kotak ({keterangan})"
    else:
        baris = f"{tempat} ({jam}) : {kotak} Kotak"

    user_data[chat_id]['drops'].append(baris)
    user_data[chat_id]['terisi'] += kotak
    sisa_baru = user_data[chat_id]['total_kadet'] - user_data[chat_id]['terisi']

    if sisa_baru == 0:
        selesaikan_dan_cetak(chat_id)
    else:
        tanya_opsi_drop(chat_id)

def selesaikan_dan_cetak(chat_id):
    d = user_data[chat_id]
    kategori = d['kategori']
    
    hasil = []
    if kategori == "Makanan":
        hasil.append(f"DATA MAKAN CO-{d['co']}")
        hasil.append(f"{d['tanggal']}\n")
        hasil.append(f"• Makan {d['waktu']} ({d['total_kadet']})")
        hasil.append(f"Rukan                                       : {d['rukan']}")
    else:
        hasil.append(f"DATA SNACK CO-{d['co']}")
        hasil.append(f"{d['tanggal']}\n")
        hasil.append(f"• Snack ({d['total_kadet']})")
    
    for item in d['drops']:
        hasil.append(item)

    laporan_teks = "\n".join(hasil)

    with open(NAMA_FILE, 'a') as f:
        f.write(laporan_teks + "\n" + "-"*40 + "\n")

    bot.send_message(chat_id, "✅ **DATA BERHASIL DIINPUT SESUAI JUMLAH KADET**\n\nBerikut format laporannya:\n")
    bot.send_message(chat_id, f"```\n{laporan_teks}\n```", parse_mode="Markdown")

    # Otomatis matikan pengingat karena user sudah input laporan
    if str(chat_id) in pengingat_aktif:
        pengingat_aktif.remove(str(chat_id))
        bot.send_message(chat_id, "🔕 Pengingat otomatis dimatikan karena Anda sudah input laporan. Terima kasih!")

    del user_data[chat_id]

# --- FLASK APP UNTUK KOYEB / FLY.IO / RENDER (WEBHOOK + CRON) ---
app = Flask(__name__)

@app.route('/', methods=['GET'])
def health():
    return "Bot Logistik Hidup! OK", 200

@app.route('/reminder', methods=['GET'])
def trigger_reminder():
    """Dipanggil cron-job.org tiap jam 21:00 WIB (14:00 UTC) tanpa perlu laptop hidup"""
    picu_pengingat_malam()
    return f"OK - Pengingat dipicu jam {datetime.now()}, antrean: {list(pengingat_aktif)}", 200

@app.route(f'/{TOKEN}', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return 'OK', 200
    abort(403)

@app.route('/setWebhook', methods=['GET'])
def set_webhook():
    url = request.args.get('url')
    if not url:
        base = request.url_root.rstrip('/')
        url = f"{base}/{TOKEN}"
    bot.remove_webhook()
    result = bot.set_webhook(url=url)
    return f"Webhook set to {url}: {result}", 200

# --- MENJALANKAN THREAD DAN BOT ---

if __name__ == "__main__":
    PORT = os.getenv("PORT")
    if PORT:
        thread_jadwal = threading.Thread(target=jalankan_jadwal, daemon=True)
        thread_jadwal.start()
        print(f"Mode WEBHOOK aktif di port {PORT}...")
        app.run(host='0.0.0.0', port=int(PORT))
    else:
        thread_jadwal = threading.Thread(target=jalankan_jadwal, daemon=True)
        thread_jadwal.start()
        print("Mode POLLING lokal aktif...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)