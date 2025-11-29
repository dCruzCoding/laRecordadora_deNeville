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

from db import (
    get_config, get_reminder_for_editing, update_reminder_content, 
    update_reminder_pre_alert, get_reminder_status_for_validation
)
from utils import (
    send_interactive_list, parse_reminder, parse_time_to_minutes, 
    cancel_conversation, unexpected_command, convert_utc_to_local
)
from handlers.list import TITLES, list_cancel_handler, shared_list_callback
from alerts import cancel_alerts, schedule_alerts
from personality import get_text

# --- DEFINICIÓN DE ESTADOS ---
CHOOSE_ID, CHOOSE_OPTION, EDIT_REMINDER, EDIT_ALERT, EDIT_ALL_ASK_ALERT = range(5)


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

    reminder = get_reminder_for_editing(chat_id, user_id_to_edit)

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
        [
            InlineKeyboardButton("📝 Contenido", callback_data="edit_content"),
            InlineKeyboardButton("⏳ Aviso Previo", callback_data="edit_alert")
        ],
        [InlineKeyboardButton("✍️ Todo (Contenido y Aviso)", callback_data="edit_all")],
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
# SECCIÓN 2: RAMA DE EDICIÓN DE "CONTENIDO" (y primer paso de "MODIFICAR TODO")
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
    """
    Guarda el nuevo contenido. Si es el flujo "Todo", continúa pidiendo el aviso.
    Si no, finaliza la conversación.
    """
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END

    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    
    text, dt, error = parse_reminder(update.message.text, user_timezone=user_tz)
    
    if error:
        await update.message.reply_text(get_text("error_formato"))
        return EDIT_REMINDER

    if context.user_data.get('edit_flow') == 'all':
        # Guardamos temporalmente los nuevos datos y pasamos a pedir el aviso.
        context.user_data['new_text'] = text
        context.user_data['new_datetime'] = dt
        
        # Reutilizamos el mensaje de `ask_new_alert` pero enviándolo como un nuevo mensaje
        current_alert_min = info.get("pre_alert", 0)
        time_str = "ninguno"
        if current_alert_min and current_alert_min > 0:
            hours, mins = divmod(current_alert_min, 60)
            time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        
        message = get_text("editar_pide_aviso_nuevo", current_alert=time_str)
        await update.message.reply_text(text=message, parse_mode="Markdown")
        return EDIT_ALL_ASK_ALERT
    else:
        # Flujo original: solo se editó el contenido.
        update_reminder_content(chat_id, info["global_id"], text, dt, user_tz)
        cancel_alerts(str(info["global_id"]))
        pre_alert = info.get("pre_alert", 0)
        if dt and pre_alert is not None:
            await schedule_alerts(chat_id, str(info["global_id"]), info["user_id"], text, dt, pre_alert)
            
        date_str = "Sin fecha"
        if dt:
            date_local = convert_utc_to_local(dt, user_tz)
            date_str = date_local.strftime("%d %b, %H:%M")
            
        message = get_text("editar_confirmacion_recordatorio", user_id=info["user_id"], text=text, date=date_str)
        await update.message.reply_text(message, parse_mode="Markdown")
        
        context.user_data.clear()
        return ConversationHandler.END


# =============================================================================
# SECCIÓN 3: RAMA DE EDICIÓN DE "AVISO PREVIO"
# =============================================================================

async def ask_new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario el nuevo tiempo de aviso previo, validando si es posible."""
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id

    current_reminder = get_reminder_status_for_validation(chat_id, info.get("global_id"))
    if current_reminder:
        current_status, current_datetime_utc = current_reminder
        if current_status == 1 or (current_datetime_utc and current_datetime_utc < datetime.now(pytz.utc)):
            # Usamos edit_message_text para reemplazar el menú, ya que venimos de un botón
            await query.edit_message_text(text=get_text("error_aviso_no_permitido"))
            # Finalizamos la conversación aquí, ya que no hay más pasos posibles
            return ConversationHandler.END

    current_alert_min = info.get("pre_alert", 0)
    time_str = "ninguno"
    if current_alert_min and current_alert_min > 0:
        hours, mins = divmod(current_alert_min, 60)
        time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        
    message = get_text("editar_pide_aviso_nuevo", current_alert=time_str)
    await query.edit_message_text(text=message, parse_mode="Markdown")
    return EDIT_ALERT

async def save_new_alert(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nuevo aviso, valida la fecha y reprograma."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END
    
    minutes = parse_time_to_minutes(update.message.text)
    if minutes is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDIT_ALERT
    
    chat_id = update.effective_chat.id
    if minutes == 0:
        update_reminder_pre_alert(chat_id, info["global_id"], 0)
        cancel_alerts(str(info["global_id"])) # Solo cancelamos el aviso previo
        confirmation_message = get_text("editar_confirmacion_aviso", user_id=info["user_id"], new_alert="ninguno")
    elif not info.get("datetime_utc"):
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        return EDIT_ALERT
    else:
        alert_was_scheduled = await schedule_alerts(
            chat_id, str(info["global_id"]), info["user_id"], info["text"], info["datetime_utc"], minutes
        )
        if alert_was_scheduled:
            update_reminder_pre_alert(chat_id, info["global_id"], minutes)
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
# SECCIÓN 4: NUEVO FLUJO COMPLETO DE EDICIÓN "MODIFICAR TODO"
# =============================================================================

async def ask_edit_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el flujo para editar todo, marcando el contexto y llamando al primer paso."""
    context.user_data['edit_flow'] = 'all'
    # Reutilizamos la función que pide el contenido del recordatorio
    return await ask_new_reminder(update, context)

async def save_all_changes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso final del flujo "Todo". Guarda el aviso y todos los cambios anteriores."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END

    minutes = parse_time_to_minutes(update.message.text)
    if minutes is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDIT_ALL_ASK_ALERT

    chat_id = update.effective_chat.id
    new_text = context.user_data.get('new_text')
    new_datetime = context.user_data.get('new_datetime')
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'

    # Guardamos ambos cambios en la base de datos
    update_reminder_content(chat_id, info["global_id"], new_text, new_datetime, user_tz)
    update_reminder_pre_alert(chat_id, info["global_id"], minutes)

    # Reprogramamos todo desde cero
    cancel_alerts(str(info["global_id"]))
    if new_datetime and minutes is not None:
        await schedule_alerts(chat_id, str(info["global_id"]), info["user_id"], new_text, new_datetime, minutes)

    # Mensaje de confirmación final
    date_str = "Sin fecha"
    if new_datetime:
        date_local = convert_utc_to_local(new_datetime, user_tz)
        date_str = date_local.strftime("%d %b, %H:%M")
        
    alert_str = "ninguno"
    if minutes > 0:
        hours, mins = divmod(minutes, 60)
        alert_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

    await update.message.reply_text(
        f"✅ ¡Todo actualizado para `#{info['user_id']}`!\n\n"
        f"📝 Nuevo contenido: *{new_text}*\n"
        f"🗓️ Nueva fecha: *{date_str}*\n"
        f"⏳ Nuevo aviso previo: *{alert_str}*",
        parse_mode="Markdown"
    )
    
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
            CallbackQueryHandler(ask_edit_all, pattern="^edit_all$"),
            CallbackQueryHandler(edit_back_to_list, pattern="^edit_back_to_list$"),
        ],
        EDIT_REMINDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_reminder)],
        EDIT_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_new_alert)],
        EDIT_ALL_ASK_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_all_changes)],
    },
    fallbacks=[
        list_cancel_handler,
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)