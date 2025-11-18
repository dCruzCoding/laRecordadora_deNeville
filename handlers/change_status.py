# handlers/change_status.py
"""
Módulo para el comando /cambiar.

Gestiona una conversación para permitir al usuario cambiar el estado de uno o
más recordatorios (de 'pendiente' a 'hecho' y viceversa).
Si un recordatorio pendiente se reactiva y su fecha es futura, inicia un
sub-flujo para permitir al usuario reprogramar un aviso.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from datetime import datetime
import pytz

from db import get_connection, get_config
from utils import parse_time_to_minutes, cancel_conversation, unexpected_command, send_interactive_list, normalize_text
from alerts import cancel_alerts, schedule_alerts
from handlers.list import TITLES, list_cancel_handler, shared_list_callback
from personality import get_text

# --- DEFINICIÓN DE ESTADOS ---
CHOOSE_ID, CONFIRM_CHANGE, RESCHEDULE_ALERT = range(3)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def change_status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /cambiar. Dirige al modo rápido o interactivo."""
    # Modo rápido: si el primer argumento es un número, se procesa como ID.
    if context.args and context.args[0].replace("#", "").isdigit():
        return await _process_ids_to_change(update, context, context.args)
    
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
        context_key="change",
        titles=TITLES["change"],   
        filter_type=initial_filter,
        show_cancel_button=True
    )
    return CHOOSE_ID


async def receive_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe los IDs después de que el usuario vea la lista."""
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return CHOOSE_ID
    
    return await _process_ids_to_change(update, context, ids)


async def _process_ids_to_change(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list[str]) -> int:
    """Valida los IDs proporcionados y pide confirmación si el Modo Seguro está activo."""
    chat_id = update.effective_chat.id
    user_ids_to_search = [int(uid.replace("#", "")) for uid in ids if uid.replace("#", "").isdigit()]

    if not user_ids_to_search:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: Placeholder a %s y uso de tupla para IN
            query = "SELECT user_id, text, status FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (tuple(user_ids_to_search), chat_id))
            found_reminders = cursor.fetchall()

    if not found_reminders:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    context.user_data["info_to_change"] = found_reminders
    
    safe_mode = int(get_config(chat_id, "safe_mode") or 0)
    if safe_mode in (2, 3):
        status_emoji = {0: "⬜️", 1: "✅"}
        message_lines = []
        for user_id, text, current_status in found_reminders:
            old_emoji = status_emoji.get(current_status, "❓")
            new_status = 1 - current_status # Simple interruptor 0->1, 1->0
            new_emoji = status_emoji.get(new_status, "❓")
            message_lines.append(f"  - `#{user_id}`: _{text}_\n    *Cambiará de {old_emoji} ➡️ {new_emoji}*")
            
        mensaje_confirmacion = (f"👵 ¿Estás seguro de que quieres cambiar el estado de lo siguiente?:\n\n"
                              f"{'\n\n'.join(message_lines)}\n\n"
                              "Responde `SI` para confirmar.")
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRM_CHANGE
    
    return await execute_change(update, context)
    

async def confirm_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Espera la confirmación 'SI' del usuario de forma robusta."""
    normalized_text = normalize_text(update.message.text.strip())
    if normalized_text.startswith("si"):
        return await execute_change(update, context)

    await update.message.reply_text(get_text("cancelar"))
    return ConversationHandler.END


async def execute_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final: cambia el estado en la DB, gestiona avisos y decide si reprogramar."""
    chat_id = update.effective_chat.id
    info_to_change = context.user_data.get("info_to_change", [])
    if not info_to_change: return ConversationHandler.END

    user_ids_to_change = [reminder[0] for reminder in info_to_change]
    
    # 1. Obtenemos toda la información necesaria con UNA SOLA CONSULTA.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            query = "SELECT id, user_id, status, text, datetime, pre_alert FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (tuple(user_ids_to_change), chat_id))
            full_info_reminders = cursor.fetchall()

            # La sintaxis de UPDATE ahora usa %s
            ids_to_pending = [r[1] for r in full_info_reminders if r[2] == 1]
            ids_to_done = [r[1] for r in full_info_reminders if r[2] == 0]     
            
            if ids_to_pending:
                cursor.execute("UPDATE reminders SET status = 0 WHERE user_id IN %s AND chat_id = %s", 
                               (tuple(ids_to_pending), chat_id))
            if ids_to_done:
                cursor.execute("UPDATE reminders SET status = 1 WHERE user_id IN %s AND chat_id = %s", 
                               (tuple(ids_to_done), chat_id))

    # 3. Procesamos los resultados en Python.
    reschedulable, past_without_alert = [], []
    
    for r_id, u_id, status, text, datetime_utc, alert in full_info_reminders:
        if u_id in ids_to_done:
            cancel_alerts(str(r_id))
        
        elif u_id in ids_to_pending:
            cancel_alerts(str(r_id)) 
            if datetime_utc:
                if datetime_utc > datetime.now(pytz.utc):
                    reschedulable.append({"global_id": r_id, "user_id": u_id, "text": text, "datetime": datetime_utc})
                else:
                    past_without_alert.append(f"`#{u_id}`")
    
    formatted_ids = [f"`#{r[0]}`" for r in info_to_change]
    await update.message.reply_text(f"🔄 ¡Hecho! Se ha actualizado el estado de: {', '.join(formatted_ids)}.", parse_mode="Markdown")
    
    # 4. Enviamos los mensajes de feedback al usuario.
    if past_without_alert:
        await update.message.reply_text(
            f"⚠️ Nota: El/los recordatorio(s) {', '.join(past_without_alert)} que has reactivado ya ha(n) pasado. No se pueden añadir nuevos avisos.",
            parse_mode="Markdown"
        )

    # 5. Si hay recordatorios para reprogramar, iniciamos el sub-flujo.
    if reschedulable:
        context.user_data["reprogramar_lista"] = reschedulable
        first_reminder = reschedulable[0]
        reschedule_message = (f"🗓️ Has reactivado el recordatorio `#{first_reminder['user_id']}` - _{first_reminder['text']}_.\n\n"
                               f"{get_text('recordar_pide_aviso')}")
        await update.message.reply_text(reschedule_message, parse_mode="Markdown")
        return RESCHEDULE_ALERT
    
    context.user_data.clear()
    return ConversationHandler.END

async def receive_new_alert_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el tiempo para el nuevo aviso y lo programa."""
    alert_str = update.message.text.strip().lower()
    minutes = parse_time_to_minutes(alert_str)

    if minutes is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return RESCHEDULE_ALERT

    # Obtenemos el recordatorio que estábamos reprogramando
    reschedule_list = context.user_data.get("reschedule_list", [])
    current_reminder = reschedule_list.pop(0) # Lo sacamos de la lista
    
    # Guardamos el nuevo aviso_previo en la DB
    with get_connection() as conn:
        # CAMBIO: Placeholder a %s
        conn.cursor().execute("UPDATE reminders SET alert = %s WHERE id = %s", (minutes, current_reminder["global_id"]))

    # Programamos el aviso con la nueva configuración
    await schedule_alerts(        
        update.effective_chat.id,
        str(current_reminder["global_id"]),
        current_reminder["user_id"],
        current_reminder["text"],
        current_reminder["datetime"],
        minutes
    )
    confirmation_message = get_text("alert_rescheduled", id=current_reminder['user_id']) # <-- CAMBIO
    await update.message.reply_text(confirmation_message, parse_mode="Markdown") 

    # Si quedan más recordatorios por reprogramar, preguntamos por el siguiente
    if reschedule_list:
        context.user_data["reschedule_list"] = reschedule_list
        next_reminder = reschedule_list[0]

        next_message = (
            f"🗓️ Ahora, para `#{next_reminder['user_id']}` - _{next_reminder['text']}_.\n\n"
            f"{get_text('recordar_pide_aviso')}"
        )
        await update.message.reply_text(next_message, parse_mode="Markdown")
        return RESCHEDULE_ALERT

    context.user_data.clear()
    return ConversationHandler.END

async def _navegate_list_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Llama al handler de navegación de listas y mantiene el estado actual."""
    await shared_list_callback(update, context)
    # Devolvemos el estado en el que queremos permanecer (elegir el ID)
    return CHOOSE_ID

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================

change_status_handler = ConversationHandler(
    entry_points=[CommandHandler(["cambiar", "change", "hecho", "done", "check"], change_status_cmd)],
    states={
        CHOOSE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ids),
                    CallbackQueryHandler(_navegate_list_in_conversation, pattern=r"^(list_page|list_pivot):")],
        CONFIRM_CHANGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_change)],
        RESCHEDULE_ALERT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_new_alert_time)]
    },
    fallbacks=[
        list_cancel_handler,
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)