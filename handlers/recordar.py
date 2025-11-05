# handlers/recordar.py
"""
Módulo para el comando /recordar.

Gestiona una conversación de dos pasos para crear un nuevo recordatorio:
1.  Pide y procesa la fecha y el texto del recordatorio.
2.  Pide y procesa un tiempo de aviso previo opcional.
Soporta un modo rápido donde toda la información se puede dar en el comando inicial.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from db import get_connection, get_config
from utils import (
    parsear_recordatorio, parsear_tiempo_a_minutos, cancelar_conversacion,
    convertir_utc_a_local, comando_inesperado
)
from avisos import programar_avisos
from personalidad import get_text

# --- Definición de Estados ---
FECHA_TEXTO, AVISO_PREVIO = range(2)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /recordar. Dirige al modo rápido o interactivo."""
    if context.args:
        entrada = " ".join(context.args)
        return await _procesar_fecha_texto(update, context, entrada)
    else:
        await update.message.reply_text(get_text("recordar_pide_fecha"), parse_mode="Markdown")
        return FECHA_TEXTO

async def recibir_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la fecha y el texto del usuario en el modo interactivo."""
    entrada = update.message.text
    return await _procesar_fecha_texto(update, context, entrada)

async def _procesar_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE, entrada: str) -> int:
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    texto, fecha, error = parsear_recordatorio(entrada, user_timezone=user_tz)
    if error:
        await update.message.reply_text(error)
        return FECHA_TEXTO if not context.args else ConversationHandler.END
    fecha_iso = fecha.isoformat() if fecha else None
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO recordatorios (user_id, chat_id, texto, fecha_hora, aviso_previo, timezone) VALUES ((SELECT COALESCE(MAX(user_id), 0) + 1 FROM recordatorios WHERE chat_id = %s), %s, %s, %s, 0, %s) RETURNING id, user_id", (chat_id, chat_id, texto, fecha_iso, user_tz))
            global_id, user_id = cursor.fetchone()
    context.user_data["recordatorio_info"] = {"global_id": global_id, "user_id": user_id, "texto": texto, "fecha": fecha}
    fecha_local = convertir_utc_a_local(fecha, user_tz)
    fecha_str = fecha_local.strftime("%d %b, %H:%M") if fecha_local else "Sin fecha"
    msg = get_text("recordatorio_guardado", id=user_id, texto=texto, fecha=fecha_str)
    await update.message.reply_text(msg, parse_mode="Markdown")
    await update.message.reply_text(get_text("recordar_pide_aviso"), parse_mode="Markdown")
    return AVISO_PREVIO

async def recibir_aviso_previo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    minutos = parsear_tiempo_a_minutos(update.message.text)
    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return AVISO_PREVIO
    info = context.user_data.get("recordatorio_info")
    if not info or not info.get("fecha"):
        return ConversationHandler.END
    se_programo = await programar_avisos(update.effective_chat.id, str(info["global_id"]), info["user_id"], info["texto"], info["fecha"], minutos)
    if minutos > 0:
        if se_programo:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (minutos, info["global_id"]))
            horas, mins = divmod(minutos, 60)
            tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            await update.message.reply_text(get_text("aviso_programado", tiempo=tiempo_str))
        else:
            await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
            return AVISO_PREVIO
    else:
        await update.message.reply_text(get_text("aviso_no_programado"))
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd, filters=~filters.Regex(r'fijo|fijos'))], # ¡OJO! excluye los recordatorios fijos
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)],
        AVISO_PREVIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso_previo)]
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)