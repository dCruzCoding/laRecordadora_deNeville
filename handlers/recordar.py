from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from utils import parsear_recordatorio, generar_id
from db import get_connection

# Estados de la conversación
FECHA_TEXTO = 0

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada: /recordar [fecha * texto]"""
    if context.args:
        entrada = " ".join(context.args)
        texto, fecha, error = parsear_recordatorio(entrada)
        if error:
            await update.message.reply_text(error)
            return ConversationHandler.END
        await guardar_recordatorio(update, texto, fecha)
        return ConversationHandler.END
    else:
        await update.message.reply_text("📅 Dime la fecha y el texto del recordatorio (formato: `fecha * texto`):", parse_mode="Markdown")
        return FECHA_TEXTO

async def recibir_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el mensaje en modo conversacional."""
    entrada = update.message.text
    texto, fecha, error = parsear_recordatorio(entrada)
    if error:
        await update.message.reply_text(error)
        return FECHA_TEXTO
    await guardar_recordatorio(update, texto, fecha)
    return ConversationHandler.END

async def guardar_recordatorio(update: Update, texto: str, fecha):
    """Guarda en la base de datos."""
    rid = generar_id(fecha)
    fecha_iso = fecha.isoformat() if fecha else None
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO recordatorios (id, texto, fecha_hora, estado) VALUES (?, ?, ?, 0)",
            (rid, texto, fecha_iso)
        )
        conn.commit()
    fecha_str = fecha.strftime("%d %b %Y, %H:%M") if fecha else "Sin fecha"
    await update.message.reply_text(f"📝 Recordatorio guardado: `{rid}` - {texto} ({fecha_str})", parse_mode="Markdown")

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# Conversational handler para registrar en main.py
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd)],
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
