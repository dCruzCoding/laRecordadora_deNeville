# handlers/remind.py
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
    parse_reminder, parse_time_to_minutes, cancel_conversation,
    convert_utc_to_local, unexpected_command
)
from alerts import schedule_alerts
from personality import get_text

# --- Definición de Estados ---
AWAITING_DATE_TEXT, AWAITING_PRE_ALERT = range(2)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def remind_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /recordar. Dirige al modo rápido o interactivo."""
    if context.args:
        user_input = " ".join(context.args)
        return await _process_date_text(update, context, user_input)
    else:
        await update.message.reply_text(get_text("recordar_pide_fecha"), parse_mode="Markdown")
        return AWAITING_DATE_TEXT

async def receive_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la fecha y el texto del usuario en el modo interactivo."""
    user_input = update.message.text
    return await _process_date_text(update, context, user_input)

async def _process_date_text(update: Update, context: ContextTypes.DEFAULT_TYPE, user_input: str) -> int:
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    text, date_obj, error = parse_reminder(user_input, user_timezone=user_tz)
    if error:
        await update.message.reply_text(error)
        return AWAITING_DATE_TEXT if not context.args else ConversationHandler.END
    date_iso = date_obj.isoformat() if date_obj else None
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("INSERT INTO reminders (user_id, chat_id, text, datetime, pre_alert, timezone) VALUES ((SELECT COALESCE(MAX(user_id), 0) + 1 FROM reminders WHERE chat_id = %s), %s, %s, %s, 0, %s) RETURNING id, user_id", (chat_id, chat_id, text, date_iso, user_tz))
            global_id, user_id = cursor.fetchone()
    context.user_data["reminder_info"] = {"global_id": global_id, "user_id": user_id, "text": text, "date": date_obj}
    date_local = convert_utc_to_local(date_obj, user_tz)
    date_str = date_local.strftime("%d %b, %H:%M") if date_local else "Sin fecha"
    msg = get_text("recordatorio_guardado", id=user_id, text=text, date=date_str)
    await update.message.reply_text(msg, parse_mode="Markdown")
    await update.message.reply_text(get_text("recordar_pide_aviso"), parse_mode="Markdown")
    return AWAITING_PRE_ALERT

async def receive_pre_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    minutes = parse_time_to_minutes(update.message.text)
    if minutes is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return AWAITING_PRE_ALERT
    info = context.user_data.get("reminder_info")
    if not info or not info.get("date"):
        return ConversationHandler.END
    scheduled = await schedule_alerts(update.effective_chat.id, str(info["global_id"]), info["user_id"], info["text"], info["date"], minutes)
    if minutes > 0:
        if scheduled:
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE reminders SET pre_alert = %s WHERE id = %s", (minutes, info["global_id"]))
            hours, mins = divmod(minutes, 60)
            time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            await update.message.reply_text(get_text("aviso_programado", time=time_str))
        else:
            await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
            return AWAITING_PRE_ALERT
    else:
        await update.message.reply_text(get_text("aviso_no_programado"))
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
remind_handler = ConversationHandler(
    entry_points=[CommandHandler(["recordar", "recordatorio", "recordatorios", "add"], remind_cmd)], 
    states={
        AWAITING_DATE_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date_text)],
        AWAITING_PRE_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_pre_alert)]
    },
    fallbacks=[
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)