import os
import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from PIL import Image
from io import BytesIO

import os
TOKEN = os.getenv("8603013918:AAFvrsFz-V6ros2ULgjt4EZI2kh6OzE4H4U")
DESTINO_CHAT_ID = -1003856217956

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
conn.commit()

# ---------------- ESTILOS DE ROLES ----------------
role_styles = {
    "seller": "💰 Seller",
    "admin": "🛠 Admin",
    "owner": "👑 Owner"
}

# ---------------- VERIFICAR ADMIN ----------------
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

# ---------------- ADD ROLE ----------------
async def addrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    user_id = None
    username = None

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        username = f"@{user.username}" if user.username else user.first_name

        if len(context.args) < 1:
            return await update.message.reply_text("Uso: /addrole (respondiendo) rol")

        role = context.args[0].lower()

    else:
        if len(context.args) < 2:
            return await update.message.reply_text("Uso: /addrole @usuario rol")

        username_arg = context.args[0].replace("@", "")
        role = context.args[1].lower()

        admins = await context.bot.get_chat_administrators(update.effective_chat.id)

        for admin in admins:
            if admin.user.username == username_arg:
                user_id = admin.user.id
                username = f"@{username_arg}"
                break

    if not user_id:
        return await update.message.reply_text("❌ Usuario no encontrado")

    cursor.execute("INSERT OR REPLACE INTO roles VALUES (?, ?)", (user_id, role))
    conn.commit()

    await update.message.reply_text(f"✅ Rol '{role}' asignado a {username}")

# ---------------- REMOVE ROLE ----------------
async def removerole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    user_id = None
    username = None

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        username = f"@{user.username}" if user.username else user.first_name

    elif len(context.args) >= 1:
        username_arg = context.args[0].replace("@", "")
        admins = await context.bot.get_chat_administrators(update.effective_chat.id)

        for admin in admins:
            if admin.user.username == username_arg:
                user_id = admin.user.id
                username = f"@{username_arg}"
                break

    if not user_id:
        return await update.message.reply_text("❌ Usuario no encontrado")

    cursor.execute("DELETE FROM roles WHERE user_id=?", (user_id,))
    conn.commit()

    await update.message.reply_text(f"🗑 Rol eliminado de {username}")

# ---------------- EDIT ROLE ----------------
async def editrole(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    user_id = None
    username = None

    if update.message.reply_to_message:
        user = update.message.reply_to_message.from_user
        user_id = user.id
        username = f"@{user.username}" if user.username else user.first_name

        if len(context.args) < 1:
            return await update.message.reply_text("Uso: /editrole (respondiendo) rol")

        new_role = context.args[0].lower()

    elif len(context.args) >= 2:
        username_arg = context.args[0].replace("@", "")
        new_role = context.args[1].lower()

        admins = await context.bot.get_chat_administrators(update.effective_chat.id)

        for admin in admins:
            if admin.user.username == username_arg:
                user_id = admin.user.id
                username = f"@{username_arg}"
                break

    if not user_id:
        return await update.message.reply_text("❌ Usuario no encontrado")

    cursor.execute("SELECT role FROM roles WHERE user_id=?", (user_id,))
    if not cursor.fetchone():
        return await update.message.reply_text("⚠️ Ese usuario no tiene rol")

    cursor.execute("UPDATE roles SET role=? WHERE user_id=?", (new_role, user_id))
    conn.commit()

    await update.message.reply_text(f"✏️ Rol actualizado a '{new_role}' para {username}")

# ---------------- STAFF ----------------
async def staff(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admins = await context.bot.get_chat_administrators(update.effective_chat.id)

    text = "👮 STAFF DEL GRUPO 👮\n\n"

    for admin in admins:
        user = admin.user
        name = f"@{user.username}" if user.username else user.first_name

        cursor.execute("SELECT role FROM roles WHERE user_id=?", (user.id,))
        data = cursor.fetchone()

        if data:
            role = role_styles.get(data[0], data[0])
        else:
            role = "👑 Owner" if admin.status == "creator" else "🛠 Admin"

        text += f"{role} ➤ {name}\n"

    await update.message.reply_text(text)

# ---------------- BAN ----------------
async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    if update.message.reply_to_message:
        await context.bot.ban_chat_member(
            update.effective_chat.id,
            update.message.reply_to_message.from_user.id
        )
        await update.message.reply_text("🚫 Usuario baneado")

# ---------------- PROMOTE ----------------
async def promote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            user_id,
            can_delete_messages=True,
            can_restrict_members=True
        )
        await update.message.reply_text("⬆️ Ahora es admin")

# ---------------- DEMOTE ----------------
async def demote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    if update.message.reply_to_message:
        user_id = update.message.reply_to_message.from_user.id
        await context.bot.promote_chat_member(
            update.effective_chat.id,
            user_id,
            can_delete_messages=False,
            can_restrict_members=False
        )
        await update.message.reply_text("⬇️ Permisos removidos")

# ---------------- REFE ----------------
async def refe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await es_admin(update, context):
        return await update.message.reply_text("❌ No tienes permisos")

    msg = update.message.reply_to_message
    if not msg or not msg.photo:
        return await update.message.reply_text("❌ Responde a una imagen")

    user = msg.from_user
    username = f"@{user.username}" if user.username else user.first_name
    texto_usuario = msg.caption if msg.caption else ""

    file = await msg.photo[-1].get_file()
    img_bytes = await file.download_as_bytearray()
    base = Image.open(BytesIO(img_bytes)).convert("RGBA")

    width, height = base.size

    if not os.path.exists(WATERMARK_PATH):
        return await update.message.reply_text("❌ No encuentro el watermark")

    watermark = Image.open(WATERMARK_PATH).convert("RGBA")
    wm_size = min(800, width, height)
    watermark = watermark.resize((wm_size, wm_size))

    watermark.putalpha(80)

    base.alpha_composite(watermark, ((width - wm_size)//2, (height - wm_size)//2))

    output = BytesIO()
    output.name = "resultado.png"
    base.save(output, "PNG")
    output.seek(0)

    caption = f"MAMA CULOS VIP\n{username}\n{texto_usuario}"

    await context.bot.send_photo(DESTINO_CHAT_ID, output, caption=caption)
    await update.message.reply_text("✅ Imagen enviada")

# ---------------- MAIN ----------------
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("id", get_id))
app.add_handler(CommandHandler("addrole", addrole))
app.add_handler(CommandHandler("removerole", removerole))
app.add_handler(CommandHandler("editrole", editrole))
app.add_handler(CommandHandler("staff", staff))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("promote", promote))
app.add_handler(CommandHandler("demote", demote))
app.add_handler(CommandHandler("refe", refe))

print("Bot corriendo...")
app.run_polling()