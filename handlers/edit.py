# handlers/edit.py
"""
Módulo para el comando /editar.

Gestiona una conversación compleja y ramificada para permitir al usuario
modificar un recordatorio existente. El flujo es el siguiente:
1.  Elige un ID (modo rápido o interactivo).
2.  Se presenta un sub-menú para elegir qué editar: el contenido o el aviso.
3.a. Si elige contenido, se pide el nuevo `fecha * texto`.
3.b. Si elige aviso, se pide el nuevo tiempo de aviso.
4.  Se guarda el cambio, se reprograman los avisos si es necesario, y se finaliza.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, 
    MessageHandler, CallbackQueryHandler, filters
)
from datetime import datetime
import pytz

from db import get_connection, get_config
from utils import (
    send_interactive_list, parse_reminder, parse_time_to_minutes, 
    cancel_conversation, unexpected_command, convert_utc_to_local
)
from handlers.list import TITLES, list_cancel_handler, shared_list_callback
from alerts import cancel_alerts, schedule_alerts
from personality import get_text

# --- DEFINICIÓN DE ESTADOS ---
CHOOSE_ID, CHOOSE_OPTION, EDIT_REMINDER, EDIT_ALERT = range(4)



# =============================================================================
# SECCIÓN 1: SELECCIÓN DEL RECORDATORIO A EDITAR
# =============================================================================

async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /editar. Dirige al modo rápido o interactivo."""
    if context.args:
        if len(context.args) > 1:
            await update.message.reply_text("👵 ¡Tranquilidad! Solo puedes editar un recordatorio a la vez.")
            return ConversationHandler.END
        return await _process_id_and_advance(update, context, context.args[0])
    
    # Modo interactivo con filtrado
    initial_filter = "future"
    if context.args:
        arg = context.args[0].lower()
        if arg in ["hechos", "hecho"]:
            initial_filter = "done"
        elif arg in ["pasados", "pasado"]:
            initial_filter = "past"
        # Añadimos "pendientes" para consistencia
        elif arg in ["pendientes", "pendiente"]:
            initial_filter = "pending"

    await send_interactive_list(
        update, context,
        context_key="edit",
        titles=TITLES["edit"],
        filter_type=initial_filter,
        show_cancel_button=True
    )
    return CHOOSE_ID


async def receive_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el ID escrito por el usuario tras ver la lista."""
    return await _process_id_and_advance(update, context, update.message.text)


async def _process_id_and_advance(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_str: str) -> int:
    """
    Busca el recordatorio por ID, lo guarda en el contexto y muestra el menú de opciones de edición.
    """
    chat_id = update.effective_chat.id
    try:
        user_id_to_edit = int(user_id_str.replace("#", ""))
    except (ValueError, TypeError):
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: Placeholder a %s
            cursor.execute(
                "SELECT id, text, datetime , timezone, pre_alert FROM reminders WHERE user_id = %s AND chat_id = %s", 
                (user_id_to_edit, chat_id)
            )
            reminder = cursor.fetchone()

    if not reminder:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # Guardamos toda la información necesaria para los siguientes pasos.
    global_id, text, datetime_utc, timezone, pre_alert = reminder
    context.user_data["editar_info"] = {
        "global_id": global_id, "user_id": user_id_to_edit, "text": text,
        "datetime_utc": datetime_utc, "timezone": timezone, "pre_alert": pre_alert
    }

    # Preparamos y enviamos el menú de opciones.
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    date_str = "Sin fecha"
    if datetime_utc:
        date_local = convert_utc_to_local(datetime_utc, timezone or user_tz)
        date_str = date_local.strftime("%d %b, %H:%M")

    keyboard = [
        [InlineKeyboardButton("📝 Contenido (Fecha/Texto)", callback_data="edit_content")],
        [InlineKeyboardButton("⏳ Aviso Previo", callback_data="edit_alert")],
        [InlineKeyboardButton("<< Volver a la lista", callback_data="edit_back_to_list")]
    ]
    
    message = get_text("editar_elige_opcion", user_id=user_id_to_edit, text=text, date=date_str)
    
    # Reutilizamos el mensaje si venimos de un callback (ej: 'Volver'), si no, enviamos uno nuevo.
    if update.callback_query:
        await update.callback_query.edit_message_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return CHOOSE_OPTION


async def edit_back_to_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback para el botón 'Volver'. Muestra la lista interactiva de nuevo."""
    await send_interactive_list(
        update, context, context_key="edit", titles=TITLES["edit"], show_cancel_button=True
    )
    return CHOOSE_ID



# =============================================================================
# SECCIÓN 2: RAMA DE EDICIÓN DE "CONTENIDO"
# =============================================================================

async def ask_new_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario que escriba el nuevo `fecha * texto`."""
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    
    user_tz = get_config(update.effective_chat.id, "user_timezone") or 'UTC'
    date_str = "Sin fecha"

    datetime_utc = info.get("fecha_utc")
    if datetime_utc:
        date_local = convert_utc_to_local(datetime_utc, info.get("timezone") or user_tz)
        date_str = date_local.strftime("%d %b, %H:%M")
        
    message = get_text("editar_pide_recordatorio_nuevo", current_text=info.get("text", ""), current_date=date_str)
    await query.edit_message_text(text=message, parse_mode="Markdown")
    return EDIT_REMINDER


async def save_new_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nuevo contenido, reprograma el aviso (si lo tenía) y finaliza."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END

    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    
    text, datetime, error = parse_reminder(update.message.text, user_timezone=user_tz)
    
    if error:
        await update.message.reply_text(get_text("error_formato"))
        return EDIT_REMINDER

    with get_connection() as conn:
        conn.cursor().execute(
            "UPDATE reminders SET text = %s, datetime = %s, timezone = %s WHERE id = %s",
            (text, datetime, user_tz, info["global_id"])
        )
    
    # Reprogramamos los avisos usando el 'aviso_previo' que ya estaba guardado.
    cancel_alerts(str(info["global_id"]))
    pre_alert = info.get("pre_alert", 0)
    if datetime and pre_alert is not None:
        await schedule_alerts(chat_id, str(info["global_id"]), info["user_id"], text, datetime, pre_alert)
        
    if datetime:
        # Convertimos la fecha UTC a la zona horaria local del usuario ANTES de formatearla.
        date_local = convert_utc_to_local(datetime, user_tz)
        date_str = date_local.strftime("%d %b, %H:%M")
    else:
        date_str = "Sin fecha"
        
    message = get_text("editar_confirmacion_recordatorio", user_id=info["user_id"], text=text, date=date_str)
    await update.message.reply_text(message, parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 3: RAMA DE EDICIÓN DE "AVISO PREVIO"
# =============================================================================

async def ask_new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Pide al usuario el nuevo tiempo de aviso previo, PERO PRIMERO VALIDA
    si el recordatorio puede tener un aviso.
    """
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id


    # --- LÓGICA DE VALIDACIÓN ---
    # 1. Obtenemos el estado actual desde la base de datos para estar seguros.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Placeholder >> %s
            cursor.execute("SELECT status, datetime FROM reminders WHERE id = %s", (info.get("global_id"),))
            current_reminder = cursor.fetchone()
    
    if current_reminder:
        current_status, current_datetime_utc = current_reminder
        
        # 2. Comprobamos si el recordatorio está hecho (estado 1).
        if current_status == 1:
            await context.bot.send_message(chat_id=chat_id, text=get_text("error_aviso_no_permitido"))
            # Devolvemos al usuario al menú anterior (elegir opción)
            return CHOOSE_OPTION
            
        # 3. Comprobamos si la fecha ya ha pasado.
        if current_datetime_utc:
            if current_datetime_utc < datetime.now(pytz.utc):
                await context.bot.send_message(chat_id=chat_id, text=get_text("error_aviso_no_permitido"))
                return CHOOSE_OPTION

    # Si pasa todas las validaciones, continuamos con el flujo normal.
    current_alert_min = info.get("pre_alert", 0)
    if current_alert_min and current_alert_min > 0:
        hours, mins = divmod(current_alert_min, 60)
        time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
    else:
        time_str = "ninguno"
        
    message = get_text("editar_pide_aviso_nuevo", current_alert=time_str)
    await query.edit_message_text(text=message , parse_mode="Markdown")
    return EDIT_ALERT


async def save_new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nuevo aviso, valida la fecha y reprograma."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END
    
    minutes = parse_time_to_minutes(update.message.text)
    if minutes is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDIT_ALERT
        
    if minutes == 0:
        with get_connection() as conn:
            conn.cursor().execute("UPDATE reminders SET pre_alert = %s WHERE id = %s", (0, info["global_id"]))
        cancel_alerts(str(info["global_id"]))
        confirmation_message = get_text("editar_confirmacion_aviso", user_id=info["user_id"], new_alert="ninguno")
    
    elif not info.get("datetime_utc"):
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        return EDIT_ALERT
    
    else:
        # CAMBIO: Usamos directamente el objeto datetime guardado.
        date = info["datetime_utc"]
        alert_was_scheduled = await schedule_alerts(
            update.effective_chat.id, str(info["global_id"]), info["user_id"], info["text"], date, minutes
        )
        if alert_was_scheduled:
            with get_connection() as conn:
                conn.cursor().execute("UPDATE reminders SET pre_alert = %s WHERE id = %s", (minutes, info["global_id"]))
            hours, mins = divmod(minutes, 60)
            new_time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            confirmation_message = get_text("editar_confirmacion_aviso", user_id=info["user_id"], new_alert=new_time_str)
        else:
            await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
            return EDIT_ALERT

    await update.message.reply_text(confirmation_message, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================

# Justo antes del ConversationHandler
async def _navigate_list_to_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Llama al handler de navegación de listas y mantiene el estado actual."""
    await shared_list_callback(update, context)
    # Devolvemos el estado en el que queremos permanecer (elegir el ID)
    return CHOOSE_ID

edit_handler = ConversationHandler(
    entry_points=[CommandHandler(["editar", "editsr", "edit", "modificar", "mod"], edit_cmd)],
    states={
        CHOOSE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id),
                    CallbackQueryHandler(_navigate_list_to_conversation, pattern=r"^(list_page|list_pivot):")],
        CHOOSE_OPTION: [
            CallbackQueryHandler(ask_new_reminder, pattern="^edit_content$"),
            CallbackQueryHandler(ask_new_alert, pattern="^edit_alert$"),
            CallbackQueryHandler(edit_back_to_list, pattern="^edit_back_to_list$"),
        ],
        EDIT_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_reminder)],
        EDIT_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_alert)],
    },
    fallbacks=[
        list_cancel_handler,
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)