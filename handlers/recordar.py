from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from utils import parsear_recordatorio, parsear_tiempo_a_minutos
from db import get_connection
from avisos import programar_avisos

# Estados de la conversación
FECHA_TEXTO, AVISO_PREVIO = range(2)

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada: /recordar [fecha * texto]"""
    if context.args:
        entrada = " ".join(context.args)
        texto, fecha, error = parsear_recordatorio(entrada)
        if error:
            await update.message.reply_text(error)
            return ConversationHandler.END
        context.user_data["texto"] = texto
        context.user_data["fecha"] = fecha
        await update.message.reply_text("⏳ ¿Cuánto antes quieres que te avise? (ej: `2h`, `1d`, `30m`, `0` para ninguno)", parse_mode="Markdown")
        return AVISO_PREVIO
    else:
        await update.message.reply_text("📅 Dime la fecha y el texto del recordatorio (formato: `fecha * texto`):", parse_mode="Markdown")
        return FECHA_TEXTO

async def recibir_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe fecha y texto, y pide el aviso previo."""
    entrada = update.message.text
    texto, fecha, error = parsear_recordatorio(entrada)
    if error:
        await update.message.reply_text(error)
        return FECHA_TEXTO
    context.user_data["texto"] = texto
    context.user_data["fecha"] = fecha
    await update.message.reply_text("⏳ ¿Cuánto antes quieres que te avise? (ej: `2h`, `1d`, `30m`, `0` para ninguno)", parse_mode="Markdown")
    return AVISO_PREVIO

async def recibir_aviso_previo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el tiempo de aviso previo y guarda el recordatorio."""
    aviso_str = update.message.text.strip().lower()
    minutos = parsear_tiempo_a_minutos(aviso_str)
    if minutos is None:
        await update.message.reply_text("⚠️ Formato no válido. Usa por ejemplo `2h`, `1d`, `30m`, `0`.")
        return AVISO_PREVIO

    texto = context.user_data["texto"]
    fecha = context.user_data["fecha"]
    chat_id = update.effective_chat.id # <-- CAMBIO: Obtenemos chat_id
    await guardar_recordatorio(update, context, texto, fecha, minutos, chat_id) # <-- CAMBIO: Pasamos chat_id
    # Limpiamos los datos de la conversación
    context.user_data.clear()
    return ConversationHandler.END

async def guardar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, fecha, aviso_previo: int, chat_id: int):
    """Guarda en la base de datos y programa avisos."""
    fecha_iso = fecha.isoformat() if fecha else None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Calculamos el siguiente user_id para este usuario
        cursor.execute("SELECT MAX(user_id) FROM recordatorios WHERE chat_id = ?", (chat_id,))
        ultimo_id = cursor.fetchone()[0]
        nuevo_user_id = (ultimo_id or 0) + 1

        # 2. Insertamos el nuevo recordatorio
        cursor.execute(
            """INSERT INTO recordatorios (user_id, chat_id, texto, fecha_hora, estado, aviso_previo) 
               VALUES (?, ?, ?, ?, 0, ?)""",
            (nuevo_user_id, chat_id, texto, fecha_iso, aviso_previo)
        )
        # Obtenemos el ID autoincremental global que se acaba de crear
        recordatorio_id_global = cursor.lastrowid
        conn.commit()
    
    fecha_str = fecha.strftime("%d %b %Y, %H:%M") if fecha else "Sin fecha"
    # Mostramos al usuario su ID secuencial
    await update.message.reply_text(f"📝 Recordatorio guardado: `#{nuevo_user_id}` - {texto} ({fecha_str})", parse_mode="Markdown")
    
    # IMPORTANTE: APScheduler necesita un ID único GLOBAL. Usaremos el ID autoincremental.
    await programar_avisos(chat_id, str(recordatorio_id_global), nuevo_user_id, texto, fecha, aviso_previo)

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# Conversational handler para registrar en main.py
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd)],
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)],
        AVISO_PREVIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso_previo)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)