import os
import sqlite3
import time
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from PIL import Image
from io import BytesIO

# ---------------- CONFIG ----------------
TOKEN = os.getenv("8603013918:AAFvrsFz-V6ros2ULgjt4EZI2kh6OzE4H4U")
DESTINO_CHAT_ID = -1003856217956  # CAMBIA ESTO

# ---------------- RUTA WATERMARK ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATERMARK_PATH = os.path.join(BASE_DIR, "watermark.png")

# ---------------- BASE DE DATOS ----------------
conn = sqlite3.connect("roles.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS roles (
    user_id INTEGER PRIMARY KEY,
    role TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users (
    user_id INTEGER PRIMARY KEY,
    start_at INTEGER,
    expires_at INTEGER
)
""")

conn.commit()

# ---------------- ROLES ----------------
role_styles = {
    "seller": "💰 Seller",
    "admin": "🛠 Admin",
    "owner": "👑 Owner"
}

# ---------------- ADMIN ----------------
async def es_admin(update, context):
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id
    )
    return member.status in ["administrator", "creator"]

# ---------------- ID ----------------
async def get_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🆔 Chat ID: {update.effective_chat.id}\n👤 Tu ID: {update.effective_user.id}"
    )

# ---------------- ROLES ----------------
async def addrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ Sin permisos")

    if not update.message.reply_to_message:
        return await update.message.reply_text("Responde a un usuario")

    user = update.message.reply_to_message.from_user
    role = context.args[0].lower()

    cursor.execute("INSERT OR REPLACE INTO roles VALUES (?, ?)", (user.id, role))
    conn.commit()

    await update.message.reply_text("✅ Rol asignado")

async def removerole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return

    user = update.message.reply_to_message.from_user
    cursor.execute("DELETE FROM roles WHERE user_id=?", (user.id,))
    conn.commit()

    await update.message.reply_text("🗑 Rol eliminado")

# ---------------- STAFF ----------------
async def staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)
    text = "👮 STAFF DEL GRUPO 👮\n\n"

    for admin in admins:
        user = admin.user
        name = f"@{user.username}" if user.username else user.first_name

        cursor.execute("SELECT role FROM roles WHERE user_id=?", (user.id,))
        data = cursor.fetchone()

        role = role_styles.get(data[0], data[0]) if data else "Admin"
        text += f"{role} ➤ {name}\n"

    await update.message.reply_text(text)

# ---------------- BAN ----------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.ban_chat_member(update.effective_chat.id, user_id)
        await update.message.reply_text("🚫 Usuario baneado")

# ---------------- VIP ----------------
async def vip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return

    user = update.message.reply_to_message.from_user
    dias = int(context.args[0])

    ahora = int(time.time())
    expira = ahora + dias * 86400

    cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)",
                   (user.id, ahora, expira))
    conn.commit()

    await update.message.reply_text("💎 VIP activado")

async def free(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return

    user = update.message.reply_to_message.from_user
    cursor.execute("DELETE FROM vip_users WHERE user_id=?", (user.id,))
    conn.commit()

    await update.message.reply_text("🗑 VIP eliminado")

# ---------------- INFO ----------------
def tiempo_restante(segundos):
    dias = segundos // 86400
    horas = (segundos % 86400) // 3600
    return f"{dias}d {horas}h"

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.reply_to_message.from_user
    user_id = user.id
    username = f"@{user.username}" if user.username else user.first_name

    cursor.execute("SELECT role FROM roles WHERE user_id=?", (user_id,))
    role = cursor.fetchone()
    role = role[0] if role else "user"

    cursor.execute("SELECT start_at, expires_at FROM vip_users WHERE user_id=?", (user_id,))
    vip_data = cursor.fetchone()

    if vip_data:
        _, exp = vip_data
        restante = exp - int(time.time())
        fecha = time.strftime('%d/%m/%Y', time.localtime(exp))
        restante = tiempo_restante(restante)
        plan = "VIP"
    else:
        fecha = "No"
        restante = "0"
        plan = "Free"

    texto = f"""
👑 Información de Usuario
━━━━━━━━━━━━━━━━━━
👤 ID: {user_id}
📛 Username: {username}
━━━━━━━━━━━━━━━━━━
🔰 Role: {role}
📋 Plan: {plan}
━━━━━━━━━━━━━━━━━━
⏰ Expira: {fecha}
⏳ Tiempo restante: {restante}
"""
    await update.message.reply_text(texto)

# ---------------- AUTO BAN ----------------
async def verificar_vips(context: ContextTypes.DEFAULT_TYPE):
    ahora = int(time.time())

    cursor.execute("SELECT user_id, expires_at FROM vip_users")
    for user_id, exp in cursor.fetchall():
        if ahora >= exp:
            try:
                await context.bot.ban_chat_member(DESTINO_CHAT_ID, user_id)
            except:
                pass

            cursor.execute("DELETE FROM vip_users WHERE user_id=?", (user_id,))
            conn.commit()

# ---------------- WATERMARK ----------------
def add_watermark_ffmpeg(input_file, output_file, watermark):
    command = [
        "ffmpeg", "-i", input_file, "-i", watermark,
        "-filter_complex",
        "[1]scale=350:350,format=rgba,colorchannelmixer=aa=0.6[wm];[0][wm]overlay=(main_w-overlay_w)/2:(main_h-overlay_h)/2",
        output_file, "-y"
    ]
    subprocess.run(command)

# ---------------- REFE ----------------
async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    msg = update.message.reply_to_message
    if not msg:
        return await update.message.reply_text("❌ Responde a imagen, video o gif")

    user = msg.from_user
    username = f"@{user.username}" if user.username else user.first_name
    texto_usuario = msg.caption if msg.caption else ""

    caption = f"MAMA CULOS VIP\n{username}\n{texto_usuario}"

    # -------- IMAGEN --------
    if msg.photo:
        file = await msg.photo[-1].get_file()
        img = Image.open(BytesIO(await file.download_as_bytearray())).convert("RGBA")

        wm = Image.open(WATERMARK_PATH).resize((350, 350)).convert("RGBA")
        wm.putalpha(int(255 * 0.6))

        img.alpha_composite(wm, ((img.width - 350)//2, (img.height - 350)//2))

        bio = BytesIO()
        bio.name = "img.png"
        img.save(bio, "PNG")
        bio.seek(0)

        await context.bot.send_photo(
            DESTINO_CHAT_ID,
            photo=bio,
            caption=caption
        )

    # -------- VIDEO --------
    elif msg.video:
        file = await msg.video.get_file()
        input_path = "video.mp4"
        output_path = "video_wm.mp4"

        await file.download_to_drive(input_path)

        add_watermark_ffmpeg(input_path, output_path, WATERMARK_PATH)

        with open(output_path, "rb") as vid:
            await context.bot.send_video(
                DESTINO_CHAT_ID,
                video=vid,
                caption=caption
            )

    # -------- GIF --------
    elif msg.animation:
        file = await msg.animation.get_file()
        input_path = "gif.gif"
        output_path = "gif_wm.gif"

        await file.download_to_drive(input_path)

        add_watermark_ffmpeg(input_path, output_path, WATERMARK_PATH)

        with open(output_path, "rb") as gif:
            await context.bot.send_animation(
                DESTINO_CHAT_ID,
                animation=gif,
                caption=caption
            )

    else:
        return await update.message.reply_text("❌ Solo imagen, video o gif")

    await update.message.reply_text("✅ Enviado")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("id", get_id))
app.add_handler(CommandHandler("addrole", addrole))
app.add_handler(CommandHandler("removerole", removerole))
app.add_handler(CommandHandler("staff", staff))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("vip", vip))
app.add_handler(CommandHandler("free", free))
app.add_handler(CommandHandler("info", info))
app.add_handler(CommandHandler("refe", refe))

app.job_queue.run_repeating(verificar_vips, interval=60)

print("Bot corriendo...")
app.run_polling()
