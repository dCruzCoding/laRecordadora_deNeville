from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from db import get_connection, get_config
from utils import formatear_fecha_para_mensaje

ELEGIR_ID, CONFIRMAR = range(2)

async def borrar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra recordatorios y pide IDs para borrar."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, texto, fecha_hora, estado FROM recordatorios ORDER BY fecha_hora")
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios guardados.")
        return ConversationHandler.END

    mensaje = ["*🗑 Lista de recordatorios:*"]
    for rid, texto, fecha_iso, estado in recordatorios:
        fecha_str = formatear_fecha_para_mensaje(fecha_iso)
        estado_str = "✅ Hecho" if estado == 1 else "🕒 Pendiente"
        mensaje.append(f"`{rid}` - {texto} ({fecha_str}) [{estado_str}]")

    mensaje.append("\n✏️ Escribe el/los ID que quieras borrar (separados por espacio):")
    await update.message.reply_text("\n".join(mensaje), parse_mode="Markdown")
    return ELEGIR_ID

async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text("⚠️ No escribiste ningún ID.")
        return ELEGIR_ID

    # Guardar temporalmente en contexto para confirmar
    context.user_data["ids_a_borrar"] = ids

    modo_seguro = int(get_config("modo_seguro") or 0)
    if modo_seguro in (1, 3):
        await update.message.reply_text(
            f"⚠️ Vas a borrar {len(ids)} recordatorio(s). Escribe 'SI' para confirmar o cualquier otra cosa para cancelar."
        )
        return CONFIRMAR

    return await ejecutar_borrado(update, ids)

async def confirmar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "SI":
        ids = context.user_data.get("ids_a_borrar", [])
        return await ejecutar_borrado(update, ids)
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ejecutar_borrado(update: Update, ids):
    with get_connection() as conn:
        cursor = conn.cursor()
        borrados = []
        for rid in ids:
            cursor.execute("DELETE FROM recordatorios WHERE id = ?", (rid,))
            if cursor.rowcount > 0:
                borrados.append(rid)
        conn.commit()
    if borrados:
        await update.message.reply_text(f"🗑 Borrados: {', '.join(borrados)}")
    else:
        await update.message.reply_text("⚠️ No se encontró ningún ID válido.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

borrar_handler = ConversationHandler(
    entry_points=[CommandHandler("borrar", borrar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_borrado)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
