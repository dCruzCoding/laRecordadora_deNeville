# handlers/recordar_fijo.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

from db import (
    get_config, add_recordatorio_fijo, get_fijos_by_chat_id,
    update_fijo_by_id, delete_fijo_by_id, check_fijo_exists
)
from utils import cancelar_conversacion, comando_inesperado
from avisos import programar_recordatorio_fijo_diario, cancelar_avisos
from personalidad import get_text

# --- Definición de Estados ---
(
    MENU_FIJO, AÑADIR_FIJO,
    ELEGIR_ID_BORRAR_FIJO,
    ELEGIR_ID_EDITAR_FIJO, RECIBIR_NUEVOS_DATOS_FIJOS
) = range(5)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def fijo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada. Muestra el menú de gestión de recordatorios fijos."""
    keyboard = [
        [InlineKeyboardButton("➕ Añadir nuevo", callback_data="fijo_add")],
        [InlineKeyboardButton("✍️ Editar existente", callback_data="fijo_edit")],
        [InlineKeyboardButton("🗑️ Borrar existente", callback_data="fijo_delete")],
        [InlineKeyboardButton("❌ Salir", callback_data="fijo_cancel")],
    ]
    await update.message.reply_text(
        "🔁 Gestión de Recordatorios Fijos\n\n¿Qué quieres hacer?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU_FIJO

# --- Ayudante para mostrar la lista de fijos ---
async def _mostrar_lista_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE, texto_introduccion: str):
    chat_id = update.effective_chat.id
    fijos = get_fijos_by_chat_id(chat_id)
    if not fijos:
        await context.bot.send_message(chat_id, "No tienes ningún recordatorio fijo configurado.")
        return False
    
    mensaje_lista = [texto_introduccion]
    for fijo_id, texto, hora in fijos:
        mensaje_lista.append(f"  - `#{fijo_id}`: {texto} (a las {hora.strftime('%H:%M')})")
    
    await context.bot.send_message(chat_id, "\n".join(mensaje_lista), parse_mode="Markdown")
    return True

# --- Flujos de Añadir, Editar y Borrar ---
async def fijo_pide_datos_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ **Añadir Recordatorio fijo**", parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Escribe la hora y el texto para tu nuevo recordatorio.\n\nFormato: `HH:MM * Texto`",
        parse_mode="Markdown"
    )
    return AÑADIR_FIJO

async def fijo_recibe_datos_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id, entrada = update.effective_chat.id, update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return AÑADIR_FIJO
    hora_str, texto = match.groups()
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    fijo_id = add_recordatorio_fijo(chat_id, texto, hora_str, user_tz)
    hora, minuto = map(int, hora_str.split(':'))
    programar_recordatorio_fijo_diario(chat_id, fijo_id, texto, hora, minuto, user_tz)
    await update.message.reply_text(f"✅ ¡Añadido! Recordatorio fijo `#{fijo_id}` programado.")
    return ConversationHandler.END

async def fijo_pide_id_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🗑️ **Borrar Recordatorio fijo**", parse_mode="Markdown")
    if await _mostrar_lista_fijos(update, context, "Dime el ID del recordatorio fijo que quieres borrar:"):
        return ELEGIR_ID_BORRAR_FIJO
    return ConversationHandler.END

async def fijo_ejecuta_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        fijo_id = int(update.message.text.strip().replace("#", ""))
    except ValueError:
        await update.message.reply_text("Por favor, introduce solo un número.")
        return ELEGIR_ID_BORRAR_FIJO
    
    num_borrados = delete_fijo_by_id(fijo_id)
    if num_borrados > 0:
        cancelar_avisos(f"fijo_{fijo_id}")
        await update.message.reply_text(f"✅ Recordatorio fijo `#{fijo_id}` borrado.")
    else:
        await update.message.reply_text(f"❌ No he encontrado un recordatorio fijo con el ID #{fijo_id}.")
    return ConversationHandler.END

async def fijo_pide_id_editar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ **Editar Recordatorio fijo**", parse_mode="Markdown")
    if await _mostrar_lista_fijos(update, context, "Dime el ID del recordatorio fijo a editar:"):
        return ELEGIR_ID_EDITAR_FIJO
    return ConversationHandler.END

async def fijo_pide_nuevos_datos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Valida el ID proporcionado por el usuario. Si es válido, pide los nuevos datos.
    Si no, informa del error y le permite intentarlo de nuevo.
    """
    chat_id = update.effective_chat.id
    try:
        fijo_id = int(update.message.text.strip().replace("#", ""))
    except ValueError:
        await update.message.reply_text("Eso no es un número válido. Por favor, dime el ID del recordatorio que quieres editar:")
        return ELEGIR_ID_EDITAR_FIJO # Mantenemos al usuario en el paso de elegir ID

    if check_fijo_exists(fijo_id, chat_id):
        # El ID es válido y pertenece al usuario, procedemos.
        context.user_data["fijo_id_a_editar"] = fijo_id
        await update.message.reply_text("Entendido. Ahora, escribe la nueva hora y texto con el formato `HH:MM * Texto`.")
        return RECIBIR_NUEVOS_DATOS_FIJOS
    else:
        # El ID no existe o no pertenece al usuario.
        await update.message.reply_text(f"❌ No he encontrado ningún recordatorio fijo con el ID #{fijo_id}. Prueba de nuevo.")
        return ELEGIR_ID_EDITAR_FIJO # Devolvemos al usuario al paso anterior

async def fijo_ejecuta_edicion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    fijo_id = context.user_data.get("fijo_id_a_editar")
    entrada = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return RECIBIR_NUEVOS_DATOS_FIJOS
    
    hora_str, texto = match.groups()
    update_fijo_by_id(fijo_id, texto, hora_str)
    
    user_tz = get_config(update.effective_chat.id, "user_timezone") or "UTC"
    hora, minuto = map(int, hora_str.split(':'))
    programar_recordatorio_fijo_diario(update.effective_chat.id, fijo_id, texto, hora, minuto, user_tz)
    
    await update.message.reply_text(f"✅ ¡Actualizado el recordatorio fijo `#{fijo_id}`!")
    context.user_data.clear()
    return ConversationHandler.END

async def fijo_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(get_text("cancelar"))
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
fijo_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", fijo_cmd, filters=filters.Regex(r'fijo|fijos'))],
    states={
        MENU_FIJO: [
            CallbackQueryHandler(fijo_pide_datos_add, pattern="^fijo_add$"),
            CallbackQueryHandler(fijo_pide_id_editar, pattern="^fijo_edit$"),
            CallbackQueryHandler(fijo_pide_id_borrar, pattern="^fijo_delete$"),
            CallbackQueryHandler(fijo_cancelar, pattern="^fijo_cancel$"),
        ],
        AÑADIR_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_recibe_datos_add)],
        ELEGIR_ID_BORRAR_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_ejecuta_borrado)],
        ELEGIR_ID_EDITAR_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_pide_nuevos_datos)],
        RECIBIR_NUEVOS_DATOS_FIJOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_ejecuta_edicion)],
    },
    fallbacks=[CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) 
],
)