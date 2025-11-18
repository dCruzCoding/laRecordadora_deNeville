# handlers/pinned.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

from db import (
    get_config, add_pinned_reminder, get_pinned_by_chat_id,
    update_pinned_by_id, delete_pinned_by_ids, check_pinned_exists
)
from utils import (
    cancel_callback, unexpected_command, cancel_conversation,
    format_week_days, normalize_text, 
    WEEK_DAYS_MAP, WEEK_DAYS_ORDER
)
from alerts import reschedule_all_pinned_for_chat
from personality import get_text

# --- Definición de Estados ---
(
    PINNED_MENU,
    ADD_ASK_DATA, ADD_ASK_DAYS,
    CHOOSE_ID_TO_DELETE, CONFIRM_DELETE,
    CHOOSE_ID_TO_EDIT, RECEIVE_NEW_DATA,
    EDIT_ASK_DAYS 
) = range(8)

# =============================================================================
# FUNCIONES DE AYUDA PARA EL TECLADO
# =============================================================================

def _build_days_keyboard(dias_seleccionados: set) -> InlineKeyboardMarkup:
    """Construye el teclado interactivo para seleccionar los días."""
    keyboard_rows = []
    row = []
    for day_letter in WEEK_DAYS_ORDER:
        button_text = f"✅ {day_letter}" if WEEK_DAYS_MAP[day_letter] in dias_seleccionados else day_letter
        row.append(InlineKeyboardButton(button_text, callback_data=f"pinned_day_{WEEK_DAYS_MAP[day_letter]}"))
    keyboard_rows.append(row)
    keyboard_rows.append([InlineKeyboardButton("🗓️ Todos los días", callback_data="pinned_day_all")])
    keyboard_rows.append([InlineKeyboardButton("✅ ¡Listo!", callback_data="pinned_days_done")])
    return InlineKeyboardMarkup(keyboard_rows)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def pinned_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada. Muestra el menú de gestión de recordatorios fijos."""
    keyboard = [
        [InlineKeyboardButton("➕ Añadir", callback_data="pinned_add"),
         InlineKeyboardButton("✍️ Editar", callback_data="pinned_edit")],
        [InlineKeyboardButton("🗑️ Borrar", callback_data="pinned_delete"),
        InlineKeyboardButton("❌ Salir", callback_data="pinned_cancel")],
    ]
    await update.message.reply_text(
        "🔁 Gestión de Recordatorios Fijos\n\n¿Qué quieres hacer?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return PINNED_MENU

# --- Ayudante para mostrar la lista de fijos ---
async def _show_pinned_list(update: Update, context: ContextTypes.DEFAULT_TYPE, intro_text: str):
    chat_id = update.effective_chat.id
    pinned = get_pinned_by_chat_id(chat_id)
    if not pinned:
        await context.bot.send_message(chat_id, "No tienes ningún recordatorio fijo configurado.")
        return False
    
    message_list = [intro_text]
    for pinned_id, text, hour, _, days in pinned:   # Ahora 'dias' es una cadena como "mon,tue,fri"
        # Hacemos la conversión inversa para mostrar las letras
        days_str = format_week_days(days)
        message_list.append(f"`#{pinned_id}`: {text} (a las {hour.strftime('%H:%M')})")
        message_list.append(f"    └─ 📍 {days_str}")

    await context.bot.send_message(chat_id, "\n".join(message_list), parse_mode="Markdown")
    return True

# --- Flujo de Añadir (Ahora en 2 pasos) ---
async def pinned_ask_data_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ **Añadir Recordatorio Fijo**", parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="**Paso 1 de 2:** Escribe la nueva hora y texto con el formato `HH:MM * Texto`.",
        parse_mode="Markdown"
    )
    
    return ADD_ASK_DATA

async def pinned_receive_data_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", user_input, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return ADD_ASK_DATA
    
    context.user_data['add_pinned_hour'], context.user_data['add_pinned_text'] = match.groups()
    context.user_data['selected_days'] = set(WEEK_DAYS_MAP.values()) # Por defecto, todos los días

    context.user_data['pinned_context'] = 'add'  # Añadimos contexto para la función generalizada de selección de días
    
    keyboard = _build_days_keyboard(context.user_data['selected_days'])
    await update.message.reply_text(
        "📆 Paso 2 de 2: ¿Qué días quieres que se repita? (Por defecto, todos)",
        reply_markup=keyboard
    )
    return ADD_ASK_DAYS

async def pinned_receive_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    day_cod = query.data.split('_')[-1] # ej: "fijo_dia_mon" -> "mon"
    selected_days = context.user_data.get('selected_days', set())

    if day_cod == "all":
        # Si ya están todos, los quitamos todos. Si no, los seleccionamos todos.
        if len(selected_days) == 7:
            selected_days.clear()
        else:
            selected_days = set(WEEK_DAYS_MAP.values())
    else:
        if day_cod in selected_days:
            selected_days.remove(day_cod)
        else:
            selected_days.add(day_cod)
            
    context.user_data['selected_days'] = selected_days
    
    keyboard = _build_days_keyboard(selected_days)
    await query.edit_message_text(
        text="📆 Paso 2 de 2: ¿Qué días quieres que se repita?",
        reply_markup=keyboard
    )
    
    # Leemos el contexto que guardamos y devolvemos el estado correcto.
    if context.user_data.get('pinned_context') == 'edit':
        return EDIT_ASK_DAYS
    else: # Por defecto, o si es 'add'
        return ADD_ASK_DAYS

async def pinned_finalize_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    selected_days = context.user_data.get('selected_days')
    if not selected_days:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Debes seleccionar al menos un día."
        )
        return ADD_ASK_DAYS

    hour_str = context.user_data['add_pinned_hour']
    text = context.user_data['add_pinned_text']
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    
    # Ordenamos los días para guardarlos consistentemente (mon,tue,wed...)
    ordered_days = sorted(list(selected_days), key=lambda d: list(WEEK_DAYS_MAP.values()).index(d))
    days_str_db = ",".join(ordered_days)

    fijo_id = add_pinned_reminder(chat_id, text, hour_str, user_tz, days_str_db)
    
    reschedule_all_pinned_for_chat(chat_id)
    
    await query.edit_message_text(f"✅ ¡Añadido! Recordatorio fijo `#{fijo_id}` programado para los días seleccionados.")
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Flujo de Borrar ---
async def pinned_ask_id_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🗑️ **Borrar Recordatorio Fijo**", parse_mode="Markdown")
    
    # Se actualiza el texto para indicar que se pueden borrar varios.
    prompt_text = "Dime el/los ID(s) del recordatorio fijo que quieres borrar (separados por espacios):\n"
    
    if await _show_pinned_list(update, context, prompt_text):
        return CHOOSE_ID_TO_DELETE
    return ConversationHandler.END

async def pinned_process_id_to_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe uno o más IDs, los valida y, si el Modo Seguro está activo, pide confirmación.
    """
    chat_id = update.effective_chat.id
    
    # 1. Parseamos la entrada del usuario para obtener una tupla de IDs numéricos.
    try:
        ids_to_check = tuple(int(part.replace("#", "")) for part in update.message.text.split())
        if not ids_to_check: raise ValueError
    except ValueError:
        await update.message.reply_text("Por favor, introduce uno o más números de ID separados por espacios.")
        return CHOOSE_ID_TO_DELETE

    # 2. Validamos los IDs contra los que realmente existen para este usuario.
    all_pinned = get_pinned_by_chat_id(chat_id)
    all_existing_ids = {p[0] for p in all_pinned} # Usamos un set para búsquedas rápidas.
    valid_ids_to_delete = {id_ for id_ in ids_to_check if id_ in all_existing_ids} # -> {1, 5}
    
    if not valid_ids_to_delete:
        await update.message.reply_text("❌ No he encontrado ningún recordatorio con esos IDs.")
        return CHOOSE_ID_TO_DELETE
    
    # 3. Ahora que tenemos los IDs válidos, filtramos la lista original para obtener la información completa de esos recordatorios.
    reminders_to_delete = [p for p in all_pinned if p[0] in valid_ids_to_delete]

    # 4. Guardamos la lista de recordatorios (completos) para el siguiente paso.
    context.user_data["pinned_reminders_to_delete"] = reminders_to_delete

    # --- LÓGICA DE MODO SEGURO (adaptada para múltiples recordatorios) ---
    safe_mode = int(get_config(chat_id, "safe_mode") or 0)
    if safe_mode in (1, 3):
        message_lines = []
        for pinned_id, text, hour, _, days in reminders_to_delete:
            days_str = format_week_days(days)
            message_lines.append(f"  - `#{pinned_id}`: {text} (a las {hour.strftime('%H:%M')}) [{days_str}]")
        
        confirmation_message = (
            f"👵 ¡Quieto ahí! Vas a borrar permanentemente los siguientes recordatorios fijos:\n\n"
            f"{'\n'.join(message_lines)}\n\n"
            "¿Estás completamente seguro? Escribe `SI` para confirmar."
        )
        await update.message.reply_text(confirmation_message, parse_mode="Markdown")
        return CONFIRM_DELETE
    else:
        # Si no se requiere confirmación, borramos directamente.
        return await _execute_delete_pinned(update, context)

async def pinned_confirm_and_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la confirmación 'SI' y ejecuta el borrado."""
    processed_input = normalize_text(update.message.text)
    if processed_input.startswith("si"):
        return await _execute_delete_pinned(update, context)
    else:
        await update.message.reply_text(get_text("cancelar"))
        context.user_data.clear()
        return ConversationHandler.END

async def _execute_delete_pinned(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final que realiza el borrado de múltiples IDs en la DB y resincroniza el scheduler."""
    reminders_to_delete = context.user_data.get("pinned_reminders_to_delete")
    if not reminders_to_delete:
        return ConversationHandler.END
    
    # 1. Extraemos solo los IDs para pasarlos a la función de borrado.
    pinned_ids_to_delete = tuple(r[0] for r in reminders_to_delete)
    
    chat_id = update.effective_chat.id
    # 2. Llamamos a nuestra nueva función de borrado en lote.
    num_deleted = delete_pinned_by_ids(chat_id, pinned_ids_to_delete)

    if num_deleted > 0:
        # 3. Resincronizamos todo el scheduler para este usuario.
        reschedule_all_pinned_for_chat(chat_id)

        # 4. Creamos un mensaje de confirmación dinámico.
        deleted_ids_str = ", ".join(f"`#{pid}`" for pid in pinned_ids_to_delete)
        await update.message.reply_text(f"✅ Recordatorio(s) fijo(s) {deleted_ids_str} borrado(s) permanentemente.")
    else:
        await update.message.reply_text("❌ No se ha podido borrar ningún recordatorio. Puede que ya no existieran.")
        
    context.user_data.clear()
    return ConversationHandler.END

# --- Flujo de Editar ---
async def pinned_ask_id_to_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ **Editar Recordatorio Fijo**", parse_mode="Markdown")
    if await _show_pinned_list(update, context, "Dime el ID del recordatorio fijo a editar:\n"):
        return CHOOSE_ID_TO_EDIT
    return ConversationHandler.END

async def pinned_ask_new_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Valida el ID proporcionado por el usuario. Si es válido, pide los nuevos datos.
    """
    chat_id = update.effective_chat.id
    try:
        pinned_id = int(update.message.text.strip().replace("#", ""))
    except ValueError:
        await update.message.reply_text("Eso no es un número válido. Por favor, dime el ID del recordatorio que quieres editar:")
        return CHOOSE_ID_TO_EDIT # Mantenemos al usuario en el paso de elegir ID

    if check_pinned_exists(pinned_id, chat_id):
        # El ID es válido y pertenece al usuario, procedemos.
        context.user_data["pinned_id_to_edit"] = pinned_id
        await update.message.reply_text(
            "Entendido. **Paso 1 de 2:** Escribe la nueva hora y texto con el formato `HH:MM * Texto`.",
            parse_mode="Markdown"
        )
        return RECEIVE_NEW_DATA
    else:
        # El ID no existe o no pertenece al usuario.
        await update.message.reply_text(f"❌ No he encontrado ningún recordatorio fijo con el ID #{pinned_id}. Prueba de nuevo.")
        return CHOOSE_ID_TO_EDIT # Devolvemos al usuario al paso anterior
    
async def pinned_execute_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la nueva hora/texto y pasa al paso de selección de días."""
    user_input = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", user_input, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return RECEIVE_NEW_DATA
    
    # Guardamos los nuevos datos para el paso final
    context.user_data["pinned_edit_new_time"], context.user_data["pinned_edit_new_text"] = match.groups()

    # ¡REUTILIZACIÓN! Usamos el mismo teclado de días que el flujo de "Añadir".
    # Inicializamos los días con "Todos seleccionados" como en el flujo de añadir,
    # el usuario puede ajustarlo desde ahí.
    selected_days = set(WEEK_DAYS_MAP.values())
    context.user_data['selected_days'] = selected_days

    context.user_data['pinned_context'] = 'edit' # Añadimos contexto para la función generalizada de selección de días

    keyboard = _build_days_keyboard(selected_days)
    await update.message.reply_text(
        "📆 Paso 2 de 2: Hora y texto actualizados. Ahora, selecciona los días para este recordatorio:",
        reply_markup=keyboard
    )
    return EDIT_ASK_DAYS

async def pinned_finalize_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda todos los cambios del recordatorio fijo editado."""
    query = update.callback_query
    await query.answer()

    selected_days = context.user_data.get('selected_days')
    if not selected_days:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Debes seleccionar al menos un día.")
        return EDIT_ASK_DAYS

    # 1. Recuperamos los datos necesarios del contexto del usuario.
    pinned_id = context.user_data["pinned_id_to_edit"]
    new_hour = context.user_data["pinned_edit_new_time"]
    new_text = context.user_data["pinned_edit_new_text"]
    chat_id = update.effective_chat.id
    
    # 2. Preparamos la cadena de días para guardarla en la base de datos.
    ordered_days = sorted(list(selected_days), key=lambda d: list(WEEK_DAYS_MAP.values()).index(d))
    days_str_db = ",".join(ordered_days)

    # 3. Actualizamos la base de datos. Esta es nuestra "fuente de verdad".
    update_pinned_by_id(chat_id, pinned_id, new_text, new_hour, days_str_db)
    
    # 4. Le pedimos al scheduler que se resincronice con la base de datos.
    #    No necesitamos pasarle ningún dato, él mismo los leerá.
    reschedule_all_pinned_for_chat(chat_id)
    
    # 5. Confirmamos al usuario y terminamos.
    await query.edit_message_text(f"✅ ¡Actualizado! El recordatorio fijo `#{pinned_id}` ha sido modificado.")
    
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
pinned_handler = ConversationHandler(
    entry_points= [CommandHandler(['fijo', 'fijos', 'recurrente', 'recurrentes', 'pinned'], pinned_cmd)],
    states={
        PINNED_MENU: [
            CallbackQueryHandler(pinned_ask_data_add, pattern="^pinned_add$"),
            CallbackQueryHandler(pinned_ask_id_to_edit, pattern="^pinned_edit$"),
            CallbackQueryHandler(pinned_ask_id_to_delete, pattern="^pinned_delete$"),
            CallbackQueryHandler(cancel_callback, pattern="^pinned_cancel$"),
        ],

        # --- Flujo de Añadir ---
        ADD_ASK_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_receive_data_add)],
        ADD_ASK_DAYS: [
            CallbackQueryHandler(pinned_receive_day_selection, pattern="^pinned_day_"),
            CallbackQueryHandler(pinned_finalize_add, pattern="^pinned_days_done$"),
        ],

        # --- Flujo de Borrar ---
        CHOOSE_ID_TO_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_process_id_to_delete)],
        CONFIRM_DELETE: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_confirm_and_delete)],

        # --- Flujo de Editar ---
        CHOOSE_ID_TO_EDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_ask_new_data)],
        RECEIVE_NEW_DATA: [MessageHandler(filters.TEXT & ~filters.COMMAND, pinned_execute_edit)],
        EDIT_ASK_DAYS: [
            # ¡REUTILIZACIÓN! La función que maneja el clic en un día es la misma.
            CallbackQueryHandler(pinned_receive_day_selection, pattern="^pinned_day_"),
            # Pero la función que finaliza es la específica de editar.
            CallbackQueryHandler(pinned_finalize_edit, pattern="^pinned_days_done$"),
        ],
    },
    fallbacks=[CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command) 
],
)