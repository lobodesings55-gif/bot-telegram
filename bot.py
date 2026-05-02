import os
import sqlite3
import time
import subprocess
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from PIL import Image
from io import BytesIO

# ---------------- CONFIG ----------------
TOKEN = "8603013918:AAFvrsFz-V6ros2ULgjt4EZI2kh6OzE4H4U"
DESTINO_CHAT_ID = -1003856217956

# ---------------- RUTA WATERMARK ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WATERMARK_PATH = os.path.join(BASE_DIR, "watermark.png")

# ---------------- DB ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
cursor = conn.cursor()

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

# ---------------- DEBUG ----------------
async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("pong 🟢")

async def debug(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📩 Mensaje recibido")

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

    if texto in ["perma", "permanente", "∞"]:
        return -1

    texto = texto.replace("dias","d").replace("dia","d")
    texto = texto.replace("semana","w")

    try:
        if texto.isdigit():
            return int(texto)
        if "d" in texto:
            return int(texto.replace("d",""))
        if "w" in texto:
            return int(texto.replace("w","")) * 7
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
    dias = parse_tiempo(texto)

    if dias is None:
        return await update.message.reply_text("❌ Tiempo inválido")

    ahora = int(time.time())

    if dias == -1:
        cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, -1))
        conn.commit()
        return await update.message.reply_text("💎 VIP PERMANENTE")

    expira = ahora + dias * 86400

    cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?, ?, ?)", (user.id, ahora, expira))
    conn.commit()

    await update.message.reply_text(f"💎 VIP {dias} días")

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
            plan = "VIP ∞"
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
        return await update.message.reply_text("🚫 Baneado")

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
        permissions={"can_send_messages": True})
    await update.message.reply_text("🔊 Desmuteado")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.ALL, guardar_usuario))
app.add_handler(MessageHandler(filters.ALL, debug))

app.add_handler(CommandHandler("ping", ping))
app.add_handler(CommandHandler("vip", vip))
app.add_handler(CommandHandler("info", info))
app.add_handler(CommandHandler("warn", warn))
app.add_handler(CommandHandler("mute", mute))
app.add_handler(CommandHandler("unmute", unmute))

print("✅ Bot corriendo...")
app.run_polling()
