# handlers/delete.py
"""
Módulo para el comando /borrar.

Gestiona una conversación para permitir al usuario borrar uno o más recordatorios.
Soporta dos modos:
- Modo Rápido: /borrar ID1 ID2 ...
- Modo Interactivo: /borrar (muestra una lista para elegir).
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler

from db import get_connection, get_config
from utils import cancel_conversation, unexpected_command, send_interactive_list, convert_utc_to_local, normalize_text
from alerts import cancel_alerts
from handlers.list import TITLES, list_cancel_handler, shared_list_callback
from personality import get_text

# --- DEFINICIÓN DE ESTADOS ---
CHOOSE_ID, CONFIRM_DELETE = range(2)


# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /borrar. Permite el modo rápido y el filtrado inicial."""
    # Modo rápido: si el primer argumento es un número, se procesa como ID.
    if context.args and context.args[0].replace("#", "").isdigit():
        return await _process_ids(update, context, context.args)
    
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
        context_key="delete",
        titles=TITLES["delete"],
        filter_type=initial_filter,
        show_cancel_button=True
    )
    return CHOOSE_ID

async def receive_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe los IDs después de que el usuario vea la lista."""
    # .split() maneja automáticamente múltiples IDs separados por espacios.
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return CHOOSE_ID # Permite al usuario intentarlo de nuevo.
    
    return await _process_ids(update, context, ids)


async def _process_ids(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list[str]) -> int:
    """
    Función centralizada para validar IDs y pedir confirmación si es necesario.
    Utiliza consultas SQL optimizadas para manejar múltiples IDs eficientemente.
    """
    chat_id = update.effective_chat.id
    
    # 1. Limpiamos y validamos los IDs para asegurarnos de que son números.
    user_ids_to_find = []
    for user_id_str in ids:
        try:
            # Quitamos el '#' si lo tiene y lo convertimos a entero.
            user_ids_to_find.append(int(user_id_str.replace("#", "")))
        except (ValueError, TypeError):
            pass # Ignoramos las entradas que no sean números.

    if not user_ids_to_find:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # 2. Hacemos UNA SOLA CONSULTA a la base de datos para obtener la info de todos los IDs.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: PostgreSQL usa %s como placeholder, no ?.
            # psycopg2 puede manejar una tupla de valores para 'IN' directamente.
            query = "SELECT user_id, text, datetime FROM reminders WHERE user_id IN %s AND chat_id = %s"

            cursor.execute(query, (tuple(user_ids_to_find), chat_id))
            found_reminders = cursor.fetchall()

    if not found_reminders:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # Guardamos la información para el siguiente paso.
    context.user_data["info_to_delete"] = found_reminders
    
    # 3. Comprobamos el Modo Seguro.
    safe_mode = int(get_config(chat_id, "modo_seguro") or 0)
    if safe_mode in (1, 3):
        # Si se requiere confirmación, construimos el mensaje y esperamos respuesta.
        user_tz = get_config(chat_id, "user_timezone") or "UTC"
        message_lines = []
        for user_id, text, utc_datetime in found_reminders:
            date_str = "Sin fecha"
            if utc_datetime:
                # ELIMINAMOS la línea que daba error: datetime.fromisoformat()
                local_date = convert_utc_to_local(utc_datetime, user_tz)
                date_str = local_date.strftime("%d %b, %H:%M")
            message_lines.append(f"  - `#{user_id}`: _{text}_ ({date_str})")
            
        confirmation_message = (
            f"👵 ¡Quieto ahí! Vas a borrar permanentemente lo siguiente:\n\n"
            f"{'\n'.join(message_lines)}\n\n"
            "¿Estás completamente seguro? Escribe `SI` para confirmar."
        )
        await update.message.reply_text(confirmation_message, parse_mode="Markdown")
        return CONFIRM_DELETE
    
    # Si no se requiere confirmación, borramos directamente.
    return await execute_delete(update, context)


async def confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Se activa si el Modo Seguro está activo. Espera la confirmacion 'si'
    Utiliza la función normalizar_texto de utils.py para formatear la entrada
    """
    normalized_text = normalize_text(update.message.text.strip())
    
    if normalized_text.startswith("si"):
        return await execute_delete(update, context)
    
    await update.message.reply_text(get_text("cancelar"))
    return ConversationHandler.END

async def execute_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final de borrado. Realiza la operación en la DB y cancela los avisos."""
    chat_id = update.effective_chat.id
    info_to_delete = context.user_data.get("info_to_delete", [])
    if not info_to_delete:
        # Salvaguarda por si se llega aquí sin datos.
        return ConversationHandler.END

    user_ids_to_delete = [recordatorio[0] for recordatorio in info_to_delete]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # 1. Obtenemos los IDs GLOBALES para cancelar los jobs del scheduler.
            query_ids = "SELECT id FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_ids, (tuple(user_ids_to_delete), chat_id))
            global_ids = [row[0] for row in cursor.fetchall()]

            # 2. Hacemos UNA SOLA CONSULTA para borrar todos los recordatorios.
            query_delete = "DELETE FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_delete, (tuple(user_ids_to_delete), chat_id))
    
    # 3. Cancelamos todos los avisos asociados.
    for rid in global_ids:
        cancel_alerts(str(rid))
    
    # 4. Enviamos un único mensaje de confirmación.
    if len(info_to_delete) == 1:
        reminder = info_to_delete[0]
        success_message = f"🗑️ ¡Listo! El recordatorio `#{reminder[0]}` ('_{reminder[1]}_') ha sido borrado."
    else:
        formatted_ids = [f"`#{r[0]}`" for r in info_to_delete]
        success_message = f"🗑️ ¡Hecho! Los recordatorios {', '.join(formatted_ids)} han sido borrados."
            
    await update.message.reply_text(success_message, parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END

async def _navigate_list_in_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Llama al handler de navegación de listas y mantiene el estado actual."""
    await shared_list_callback(update, context)
    # Devolvemos el estado en el que queremos permanecer (elegir el ID)
    return CHOOSE_ID


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
delete_handler = ConversationHandler(
    entry_points=[CommandHandler(["borrar", "borrsr", "del", "delete", "bor"], delete_cmd)],
    states={
        CHOOSE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_ids),
                    CallbackQueryHandler(_navigate_list_in_conversation, pattern=r"^(list_page|list_pivot):")],
        CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_delete)]
    },
    fallbacks=[
        list_cancel_handler,
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)