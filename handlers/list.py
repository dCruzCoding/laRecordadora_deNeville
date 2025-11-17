# handlers/list.py
"""
Módulo Controlador de Listas Interactivas.

Este archivo es el corazón de la interfaz de usuario para visualizar recordatorios.
No solo gestiona el comando /lista, sino que también centraliza la lógica
para manejar los botones de paginación (<<, >>), el cambio de vista (pivote)
y las acciones contextuales (Limpiar, Cancelar) para TODAS las listas del bot
(usadas en /borrar, /editar, etc.).
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from telegram.error import BadRequest

from db import delete_reminders_filtered
from utils import send_interactive_list, send_pinned_list, cancel_callback
from alerts import cancel_alerts

# =============================================================================
# DEFINICIÓN DE TÍTULOS
# =============================================================================

# Diccionario centralizado de títulos para cada contexto de lista.
# Esto permite que la función de UI en utils.py sea agnóstica al contenido.
TITLES = {
    "list": {
        "future": "📜  **RECORDATORIOS**  📜",
        "past": "🗂️  **Recordatorios PASADOS**  🗂️",
        "done": "✅  **Recordatorios HECHOS**  ✅",
        "pending": "⬜️  **Todos los PENDIENTES**  ⬜️",
    },
    "delete": {
        "future": "🗑️  **BORRAR (Próximos)**  🗑️",
        "past": "🗑️  **BORRAR (Pasados)**  🗑️",
        "done": "🗑️  **BORRAR (Hechos)**  🗑️",
        "pending": "🗑️  **BORRAR (Pendientes)**  🗑️",
    },
    "edit": {
        "future": "🪄  **EDITAR (Próximos)**  🪄",
        "past": "🪄  **EDITAR (Pasados)**  🪄",
        "done": "🪄  **EDITAR (Hechos)**  🪄",
        "pending": "🪄  **EDITAR (Pendientes)**  🪄",
    },
    "change": {
        "future": "🔄  **CAMBIAR ESTADO (Próximos)**  🔄",
        "past": "🔄  **CAMBIAR ESTADO (Pasados)**  🔄",
        "done": "🔄  **CAMBIAR ESTADO (Hechos)**  🔄",
        "pending": "🔄  **CAMBIAR ESTADO (Pendientes)**  🔄",
    }
}

# =============================================================================
# FUNCIONES DE CALLBACK
# =============================================================================

async def list_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para el comando /lista. Muestra la vista por defecto
    o una vista filtrada si se proporcionan argumentos.
    """
    # Si hay argumentos y el primero es un alias de "fijo", muestra la lista de fijos.
    if context.args and context.args[0].lower() in ['fijo', 'fijos', 'recurrente', 'recurrentes', 'pinned']:
        await send_pinned_list(update, context)
        return
    
    # Si no, procede con la lógica de la lista normal interactiva.
    initial_filter = "future"

    if context.args:
        arg = context.args[0].lower()
        if arg in ["hechos", "hecho"]:
            initial_filter = "done"
        elif arg in ["pendientes", "pendiente"]:
            initial_filter = "pending"
        elif arg in ["pasados", "pasado"]:
            initial_filter = "past"
    
    await send_interactive_list(
        update, context, context_key="list", titles=TITLES["list"], filter_type=initial_filter
    )


async def shared_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler universal para los botones de paginación y pivote.
    Extrae el estado del callback_data y redibuja la lista con los parámetros correctos.
    """
    query = update.callback_query
    # Formato del callback_data: "accion:val1:val2:contexto:cancel_flag"
    parts = query.data.split(":")
    action = parts[0]
    
    # Desempaquetamos los datos según la acción
    if action == "list_page":
        page = int(parts[1])
        filter_type, context_key, cancel_flag = parts[2], parts[3], parts[4]
    elif action == "list_pivot":
        page = 1 # Al cambiar de vista, siempre volvemos a la página 1.
        filter_type, context_key, cancel_flag = parts[1], parts[2], parts[3]
    else:
        # Fallback por si llega una acción desconocida.
        return

    show_cancel = (cancel_flag == "1")
    correct_titles = TITLES.get(context_key, TITLES["list"])

    await send_interactive_list(
        update, context, 
        context_key=context_key, 
        titles=correct_titles, 
        page=page, 
        filter_type=filter_type, 
        show_cancel_button=show_cancel
    )


async def unified_clean_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler universal para los flujos de "Limpiar Pasados" y "Limpiar Hechos".
    """
    query = update.callback_query
    # --- BLOQUE DE ROBUSTEZ ---
    try:
        await query.answer()
    except BadRequest as e:
        # Si el error es porque la query es antigua, lo ignoramos y continuamos.
        if "Query is too old" in str(e):
            print(f"[INFO] Se ignoró un error de 'Query is too old' para el callback: {query.data}")
            pass
        else:
            # Si es otro tipo de BadRequest, sí que queremos saberlo.
            raise e
    
    # Formato: "accion:filtro" -> ej: "limpiar:pasados_ask", "limpiar:hechos_confirm"
    action, filter_data = query.data.split(":")
    filter_type, step = filter_data.split("_") # 'pasados', 'ask'

    # Textos dinámicos según el filtro
    texts = {
        "past": {"nombre": "pasados", "pregunta": "todos tus recordatorios pasados"},
        "done": {"nombre": "Hechos", "pregunta": "todos tus recordatorios marcados como 'Hecho'"}
    }
    current_text = texts.get(filter_type)
    if not current_text: return # Filtro no válido

    if step == "ask":
        keyboard = [[
            InlineKeyboardButton("✅ Sí, bórralos", callback_data=f"clean:{filter_type}_confirm"),
            InlineKeyboardButton("❌ No", callback_data=f"clean:{filter_type}_cancel")
        ]]
        await query.edit_message_text(
            text=f"⚠️ ¿Estás seguro de que quieres **borrar permanentemente** {current_text['pregunta']}? Esta acción no se puede deshacer.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif step == "confirm":
        # Llamamos a nuestra nueva función universal con el filtro correcto
        num_borrados, ids_borrados = delete_reminders_filtered(update.effective_chat.id, filter_type)
        for rid in ids_borrados:
            cancel_alerts(str(rid))
        await query.edit_message_text(
            text=f"🪄✨ ¡Fregotego!\n\nSe han borrado {num_borrados} recordatorios '{current_text['nombre']}' de tu archivo.",
            parse_mode="Markdown"
        )
    elif step == "cancel":
        # Devolvemos al usuario a la lista de la que venía
        await send_interactive_list(update, context, context_key="list", titles=TITLES["list"], page=1, filter_type=filter_type)


async def placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a los clics en botones invisibles para que el cliente de Telegram no muestre un error."""
    await update.callback_query.answer()

async def pinned_list_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la paginación de la lista de recordatorios fijos."""
    query = update.callback_query
    page = int(query.data.split(":")[1])
    # Reutilizamos la función de envío, pasándole la nueva página
    await send_pinned_list(update, context, page=page)

# =============================================================================
# EXPORTACIÓN DE HANDLERS
# =============================================================================
# Estos handlers son importados y registrados en main.py.

# Handler para el comando inicial /lista
list_command_handler = CommandHandler(["lista", "list"], list_cmd)

# Handler para los botones de navegación (<<, >>, PENDIENTES, PASADOS)
shared_list_callback_handler = CallbackQueryHandler(shared_list_callback, pattern=r"^(list_page|list_pivot):")

# Handler para el flujo de limpieza de recordatorios pasados
clean_list_callback_handler = CallbackQueryHandler(unified_clean_callback, pattern=r"^clean:")

# Handler para el botón universal de cancelación [X] en las listas
list_cancel_handler = CallbackQueryHandler(cancel_callback, pattern=r"^list_cancel$")

# Handler para los botones placeholder invisibles
placeholder_handler = CallbackQueryHandler(placeholder_callback, pattern=r"^placeholder$")

# Handler para la paginación de la lista de recordatorios fijos
pinned_list_pagination_handler = CallbackQueryHandler(pinned_list_pagination_callback, pattern=r"^pinned_list_page:")