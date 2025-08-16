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

async def cambiar_estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra recordatorios y pide IDs para cambiar su estado."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, texto, fecha_hora, estado FROM recordatorios ORDER BY fecha_hora")
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios guardados.")
        return ConversationHandler.END

    mensaje = ["*🔄 Lista de recordatorios:*"]
    for rid, texto, fecha_iso, estado in recordatorios:
        fecha_str = formatear_fecha_para_mensaje(fecha_iso)
        estado_str = "✅ Hecho" if estado == 1 else "🕒 Pendiente"
        mensaje.append(f"`{rid}` - {texto} ({fecha_str}) [{estado_str}]")

    mensaje.append("\n✏️ Escribe el/los ID que quieras cambiar de estado (separados por espacio):")
    await update.message.reply_text("\n".join(mensaje), parse_mode="Markdown")
    return ELEGIR_ID

async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text("⚠️ No escribiste ningún ID.")
        return ELEGIR_ID

    context.user_data["ids_a_cambiar"] = ids

    modo_seguro = int(get_config("modo_seguro") or 0)
    if modo_seguro in (2, 3):
        await update.message.reply_text(
            f"⚠️ Vas a cambiar el estado de {len(ids)} recordatorio(s). Escribe 'SI' para confirmar o cualquier otra cosa para cancelar."
        )
        return CONFIRMAR

    return await ejecutar_cambio(update, ids)

async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "SI":
        ids = context.user_data.get("ids_a_cambiar", [])
        return await ejecutar_cambio(update, ids)
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ejecutar_cambio(update: Update, ids):
    with get_connection() as conn:
        cursor = conn.cursor()
        cambiados = []
        for rid in ids:
            cursor.execute("SELECT estado FROM recordatorios WHERE id = ?", (rid,))
            row = cursor.fetchone()
            if row is not None:
                nuevo_estado = 0 if row[0] == 1 else 1
                cursor.execute("UPDATE recordatorios SET estado = ? WHERE id = ?", (nuevo_estado, rid))
                cambiados.append(rid)
        conn.commit()

    if cambiados:
        await update.message.reply_text(f"🔄 Estado cambiado para: {', '.join(cambiados)}")
    else:
        await update.message.reply_text("⚠️ No se encontró ningún ID válido.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

cambiar_estado_handler = ConversationHandler(
    entry_points=[CommandHandler("cambiar", cambiar_estado_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_cambio)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
