import os
import sqlite3
import time
import subprocess
from telegram import Update
from telegram.ext import *
from PIL import Image
from io import BytesIO

# ---------------- CONFIG ----------------
TOKEN = "TU_TOKEN_AQUI"
DESTINO_CHAT_ID = -100XXXXXXXXX  # cambia esto

# ---------------- RUTA WATERMARK ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATERMARK_PATH = os.path.join(BASE_DIR, "watermark.png")

# ---------------- DB ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS roles (user_id INTEGER PRIMARY KEY, role TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS vip_users (user_id INTEGER PRIMARY KEY, start_at INTEGER, expires_at INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, name TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS warns (user_id INTEGER PRIMARY KEY, warns INTEGER)")
conn.commit()

# ---------------- GUARDAR USERS ----------------
async def guardar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
                   (user.id, user.username or "", user.first_name))
    conn.commit()

# ---------------- ADMIN ----------------
async def es_admin(update, context):
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ["administrator", "creator"]

# ---------------- USER FETCH ----------------
async def obtener_usuario(update, context):
    if update.message.reply_to_message:
        return update.message.reply_to_message.from_user

    if context.args:
        arg = context.args[0]

        if arg.isdigit():
            try:
                return (await context.bot.get_chat_member(update.effective_chat.id, int(arg))).user
            except:
                return None

        username = arg.replace("@", "")
        cursor.execute("SELECT * FROM users WHERE username=?", (username,))
        data = cursor.fetchone()

        if data:
            class U:
                def __init__(self, id, username, name):
                    self.id=id; self.username=username; self.first_name=name
            return U(*data)

    return None

# ---------------- PARSER TIEMPO ----------------
def parse_tiempo(texto):
    texto = texto.lower()

    if texto in ["perma", "permanente", "infinito", "∞"]:
        return -1

    texto = texto.replace("dias","d").replace("dia","d")
    texto = texto.replace("semanas","w").replace("semana","w")
    texto = texto.replace("mes","m")

    try:
        if texto.isdigit():
            return int(texto)
        if "d" in texto:
            return int(texto.replace("d",""))
        if "w" in texto:
            return int(texto.replace("w",""))*7
        if "m" in texto:
            return int(texto.replace("m",""))*30
    except:
        return None

    return None

# ---------------- VIP ----------------
async def vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ Sin permisos")

    texto = " ".join(context.args)

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
    else:
        user = await obtener_usuario(update, context)

    if not user:
        return await update.message.reply_text("❌ Usuario no encontrado")

    dias = parse_tiempo(texto.replace(f"@{user.username}", "").strip())

    if dias is None:
        return await update.message.reply_text("❌ Tiempo inválido")

    ahora = int(time.time())

    # VIP PERMANENTE
    if dias == -1:
        cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, -1))
        conn.commit()
        return await update.message.reply_text("💎 VIP PERMANENTE activado")

    if dias < 1 or dias > 30:
        return await update.message.reply_text("❌ 1 a 30 días máximo")

    cursor.execute("SELECT expires_at FROM vip_users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if data and data[0] > ahora:
        nuevo = data[0] + dias*86400
    else:
        nuevo = ahora + dias*86400

    cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, nuevo))
    conn.commit()

    await update.message.reply_text(f"💎 VIP {dias} días activado")

# ---------------- INFO ----------------
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await obtener_usuario(update, context)
    if not user:
        return await update.message.reply_text("❌ Usuario no encontrado")

    cursor.execute("SELECT * FROM vip_users WHERE user_id=?", (user.id,))
    vip_data = cursor.fetchone()

    if vip_data:
        _, start, exp = vip_data

        if exp == -1:
            fecha = "∞"
            restante = "∞"
            plan = "VIP PERMANENTE"
        else:
            restante_seg = exp - int(time.time())
            fecha = time.strftime('%d/%m/%Y', time.localtime(exp))
            restante = f"{restante_seg//86400}d {(restante_seg%86400)//3600}h"
            plan = "VIP"
    else:
        plan="Free"; fecha="No"; restante="0"

    await update.message.reply_text(f"""
👑 Usuario
ID: {user.id}
User: @{user.username}

Plan: {plan}
Expira: {fecha}
Restante: {restante}
""")

# ---------------- WARN ----------------
async def warn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return

    user = await obtener_usuario(update, context)
    if not user: return

    cursor.execute("SELECT warns FROM warns WHERE user_id=?", (user.id,))
    data = cursor.fetchone()
    warns = data[0]+1 if data else 1

    cursor.execute("INSERT OR REPLACE INTO warns VALUES (?, ?)", (user.id, warns))
    conn.commit()

    if warns >= 3:
        await context.bot.ban_chat_member(update.effective_chat.id, user.id)
        cursor.execute("DELETE FROM warns WHERE user_id=?", (user.id,))
        conn.commit()
        return await update.message.reply_text("🚫 Baneado por warns")

    await update.message.reply_text(f"⚠️ {warns}/3 warns")

# ---------------- MUTE ----------------
async def mute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    user = await obtener_usuario(update, context)
    if not user: return

    await context.bot.restrict_chat_member(update.effective_chat.id, user.id, permissions={})
    await update.message.reply_text("🔇 Muteado")

async def unmute(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return
    user = await obtener_usuario(update, context)
    if not user: return

    await context.bot.restrict_chat_member(update.effective_chat.id, user.id,
        permissions={"can_send_messages":True})
    await update.message.reply_text("🔊 Desmuteado")

# ---------------- AUTO VIP ----------------
async def verificar_vips(context: ContextTypes.DEFAULT_TYPE):
    ahora = int(time.time())

    cursor.execute("SELECT user_id, expires_at FROM vip_users")
    for user_id, exp in cursor.fetchall():

        # ⏰ AVISO 1 DÍA ANTES
        if exp != -1 and 0 < (exp - ahora) <= 86400:
            try:
                await context.bot.send_message(user_id, "⚠️ Tu VIP expira en menos de 24h")
            except:
                pass

        # 🚫 EXPIRÓ
        if exp != -1 and ahora >= exp:
            try:
                await context.bot.ban_chat_member(DESTINO_CHAT_ID, user_id)
            except:
                pass

            cursor.execute("DELETE FROM vip_users WHERE user_id=?", (user_id,))
            conn.commit()

# ---------------- REFE ----------------
def add_watermark_ffmpeg(input_file, output_file):
    subprocess.run([
        "ffmpeg","-i",input_file,"-i",WATERMARK_PATH,
        "-filter_complex","[1]scale=350:350,format=rgba,colorchannelmixer=aa=0.6[wm];[0][wm]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2",
        output_file,"-y"
    ])

async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context): return

    msg = update.message.reply_to_message
    if not msg: return await update.message.reply_text("Responde a contenido")

    user = msg.from_user
    caption = f"MAMA CULOS VIP\n@{user.username}"

    if msg.photo:
        file = await msg.photo[-1].get_file()
        img = Image.open(BytesIO(await file.download_as_bytearray())).convert("RGBA")
        wm = Image.open(WATERMARK_PATH).resize((350,350)).convert("RGBA")
        wm.putalpha(int(255*0.6))
        img.alpha_composite(wm, ((img.width-350)//2,(img.height-350)//2))
        bio = BytesIO(); bio.name="img.png"
        img.save(bio,"PNG"); bio.seek(0)
        await context.bot.send_photo(DESTINO_CHAT_ID, bio, caption=caption)

    elif msg.video:
        await msg.video.get_file().download_to_drive("v.mp4")
        add_watermark_ffmpeg("v.mp4","out.mp4")
        await context.bot.send_video(DESTINO_CHAT_ID, open("out.mp4","rb"), caption=caption)

    elif msg.animation:
        await msg.animation.get_file().download_to_drive("g.gif")
        add_watermark_ffmpeg("g.gif","out.gif")
        await context.bot.send_animation(DESTINO_CHAT_ID, open("out.gif","rb"), caption=caption)

    await update.message.reply_text("✅ Enviado")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, guardar_usuario))

app.add_handler(CommandHandler("vip", vip))
app.add_handler(CommandHandler("info", info))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))
app.add_handler(CommandHandler("refe", refe))

app.job_queue.run_repeating(verificar_vips, interval=60)

print("Bot corriendo...")
app.run_polling()
