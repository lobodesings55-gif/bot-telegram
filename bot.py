import os
import sqlite3
import time
import subprocess
from telegram import Update
from telegram.ext import *
from PIL import Image
from io import BytesIO

# ---------------- CONFIG ----------------
TOKEN = "8664024055:AAGI2btOAzCViMTW7TXPDre5RyJzmS3D60k"
DESTINO_CHAT_ID = -1003856217956  # grupo destino

# ---------------- RUTA WATERMARK ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATERMARK_PATH = os.path.join(BASE_DIR, "watermark.png")

# ---------------- DB ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS vip_users (user_id INTEGER PRIMARY KEY, start_at INTEGER, expires_at INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, name TEXT)")
conn.commit()

# ---------------- GUARDAR USUARIOS ----------------
async def guardar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user:
        cursor.execute("INSERT OR REPLACE INTO users VALUES (?, ?, ?)",
                       (user.id, user.username or "", user.first_name))
        conn.commit()

# ---------------- ADMIN ----------------
async def es_admin(update, context):
    member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
    return member.status in ["administrator", "creator"]

# ---------------- OBTENER USUARIO ----------------
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

    if texto in ["perma", "permanente", "∞"]:
        return -1

    texto = texto.replace("dias","d").replace("dia","d")
    texto = texto.replace("semanas","w").replace("semana","w")
    texto = texto.replace("meses","m").replace("mes","m")

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

    user = await obtener_usuario(update, context)
    if not user:
        return await update.message.reply_text("❌ Usuario no encontrado")

    texto = " ".join(context.args)
    dias = parse_tiempo(texto.replace(f"@{user.username}", "").strip())

    if dias is None:
        return await update.message.reply_text("❌ Tiempo inválido")

    ahora = int(time.time())

    if dias == -1:
        cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, -1))
        conn.commit()
        return await update.message.reply_text("💎 VIP PERMANENTE activado")

    expira = ahora + dias * 86400

    cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, expira))
    conn.commit()

    await update.message.reply_text(f"💎 VIP {dias} días activado")

# ---------------- INFO ----------------
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = await obtener_usuario(update, context)
    if not user:
        return await update.message.reply_text("❌ Usuario no encontrado")

    cursor.execute("SELECT * FROM vip_users WHERE user_id=?", (user.id,))
    data = cursor.fetchone()

    if data:
        _, start, exp = data

        if exp == -1:
            plan = "VIP PERMANENTE"
            fecha = "∞"
            restante = "∞"
        else:
            restante_seg = exp - int(time.time())
            fecha = time.strftime('%d/%m/%Y', time.localtime(exp))
            restante = f"{restante_seg//86400}d {(restante_seg%86400)//3600}h"
            plan = "VIP"
    else:
        plan="Free"; fecha="No"; restante="0"

    await update.message.reply_text(f"""
👤 {user.first_name}
🆔 {user.id}

📋 Plan: {plan}
⏰ Expira: {fecha}
⏳ Restante: {restante}
""")

# ---------------- STAFF ----------------
async def staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    text = "👮 STAFF 👮\n\n"

    for admin in admins:
        user = admin.user
        name = f"@{user.username}" if user.username else user.first_name
        rol = "👑 Owner" if admin.status == "creator" else "🛠 Admin"
        text += f"{rol} ➤ {name}\n"

    await update.message.reply_text(text)

# ---------------- WATERMARK ----------------
def add_watermark_ffmpeg(input_file, output_file):
    subprocess.run([
        "ffmpeg","-i",input_file,"-i",WATERMARK_PATH,
        "-filter_complex","[1]scale=350:350,format=rgba,colorchannelmixer=aa=0.6[wm];[0][wm]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2",
        output_file,"-y"
    ])

# ---------------- REFE ----------------
async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ Sin permisos")

    msg = update.message.reply_to_message
    if not msg:
        return await update.message.reply_text("Responde a imagen/video/gif")

    user = msg.from_user
    caption = f"VIP\n@{user.username}"

    # FOTO
    if msg.photo:
        file = await msg.photo[-1].get_file()
        img = Image.open(BytesIO(await file.download_as_bytearray())).convert("RGBA")

        wm = Image.open(WATERMARK_PATH).resize((350,350)).convert("RGBA")
        wm.putalpha(int(255*0.6))

        img.alpha_composite(wm, ((img.width-350)//2,(img.height-350)//2))

        bio = BytesIO()
        bio.name="img.png"
        img.save(bio,"PNG")
        bio.seek(0)

        await context.bot.send_photo(DESTINO_CHAT_ID, bio, caption=caption)

    # VIDEO
    elif msg.video:
        await msg.video.get_file().download_to_drive("v.mp4")
        add_watermark_ffmpeg("v.mp4","out.mp4")
        await context.bot.send_video(DESTINO_CHAT_ID, open("out.mp4","rb"), caption=caption)

    # GIF
    elif msg.animation:
        await msg.animation.get_file().download_to_drive("g.gif")
        add_watermark_ffmpeg("g.gif","out.gif")
        await context.bot.send_animation(DESTINO_CHAT_ID, open("out.gif","rb"), caption=caption)

    else:
        return await update.message.reply_text("❌ Solo imagen/video/gif")

    await update.message.reply_text("✅ Enviado")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, guardar_usuario))

app.add_handler(CommandHandler("vip", vip))
app.add_handler(CommandHandler("info", info))
app.add_handler(CommandHandler("staff", staff))
app.add_handler(CommandHandler("refe", refe))

print("Bot corriendo...")
app.run_polling()
