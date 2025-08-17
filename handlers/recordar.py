from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from utils import parsear_recordatorio, generar_id, parsear_tiempo_a_minutos
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
    # Pasamos el chat_id a la función de guardado
    await guardar_recordatorio(update, context, texto, fecha, minutos, update.effective_chat.id)
    # Limpiamos los datos de la conversación
    context.user_data.clear()
    return ConversationHandler.END

async def guardar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE, texto: str, fecha, aviso_previo: int, chat_id: int):
    """Guarda en la base de datos y programa avisos."""
    rid = generar_id(fecha)
    fecha_iso = fecha.isoformat() if fecha else None
    with get_connection() as conn:
        cursor = conn.cursor()
        # ¡CORRECCIÓN! Añadimos chat_id a la sentencia INSERT
        cursor.execute(
            "INSERT INTO recordatorios (id, texto, fecha_hora, estado, aviso_previo, chat_id) VALUES (?, ?, ?, 0, ?, ?)",
            (rid, texto, fecha_iso, aviso_previo, chat_id)
        )
        conn.commit()
    
    fecha_str = fecha.strftime("%d %b %Y, %H:%M") if fecha else "Sin fecha"
    mensaje_confirmacion = f"📝 *Recordatorio guardado:*\n`{rid}` - {texto} ({fecha_str})"
    
    # Si hay un aviso previo, añadimos una línea extra al mensaje
    if aviso_previo > 0:
        # Reutilizamos la lógica para formatear el tiempo
        horas = aviso_previo // 60
        mins = aviso_previo % 60
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        
        # Añadimos la información del aviso previo
        mensaje_confirmacion += f"\n\n🔔 Se te avisará {tiempo_str} antes."

    # Enviamos el mensaje completo al usuario
    await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")

   
    await programar_avisos(chat_id, rid, texto, fecha, aviso_previo)

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
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