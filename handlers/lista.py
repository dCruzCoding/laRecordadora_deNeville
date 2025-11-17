# handlers/lista.py
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

from db import borrar_recordatorios_por_filtro
from utils import enviar_lista_interactiva, enviar_lista_fijos, cancelar_callback
from avisos import cancelar_avisos

# =============================================================================
# DEFINICIÓN DE TÍTULOS
# =============================================================================

# Diccionario centralizado de títulos para cada contexto de lista.
# Esto permite que la función de UI en utils.py sea agnóstica al contenido.
TITULOS = {
    "lista": {
        "futuro": "📜  **RECORDATORIOS**  📜",
        "pasado": "🗂️  **Recordatorios PASADOS**  🗂️",
        "hechos": "✅  **Recordatorios HECHOS**  ✅",
        "pendientes": "⬜️  **Todos los PENDIENTES**  ⬜️",
    },
    "borrar": {
        "futuro": "🗑️  **BORRAR (Próximos)**  🗑️",
        "pasado": "🗑️  **BORRAR (Pasados)**  🗑️",
        "hechos": "🗑️  **BORRAR (Hechos)**  🗑️",
        "pendientes": "🗑️  **BORRAR (Pendientes)**  🗑️",
    },
    "editar": {
        "futuro": "🪄  **EDITAR (Próximos)**  🪄",
        "pasado": "🪄  **EDITAR (Pasados)**  🪄",
        "hechos": "🪄  **EDITAR (Hechos)**  🪄",
        "pendientes": "🪄  **EDITAR (Pendientes)**  🪄",
    },
    "cambiar": {
        "futuro": "🔄  **CAMBIAR ESTADO (Próximos)**  🔄",
        "pasado": "🔄  **CAMBIAR ESTADO (Pasados)**  🔄",
        "hechos": "🔄  **CAMBIAR ESTADO (Hechos)**  🔄",
        "pendientes": "🔄  **CAMBIAR ESTADO (Pendientes)**  🔄",
    }
}

# =============================================================================
# FUNCIONES DE CALLBACK
# =============================================================================

async def lista_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para el comando /lista. Muestra la vista por defecto
    o una vista filtrada si se proporcionan argumentos.
    """
    # Si hay argumentos y el primero es un alias de "fijo", muestra la lista de fijos.
    if context.args and context.args[0].lower() in ['fijo', 'fijos', 'recurrente', 'recurrentes', 'pinned']:
        await enviar_lista_fijos(update, context)
        return
    
    # Si no, procede con la lógica de la lista normal interactiva.
    filtro_inicial = "futuro"

    if context.args:
        arg = context.args[0].lower()
        if arg in ["hechos", "hecho"]:
            filtro_inicial = "hechos"
        elif arg in ["pendientes", "pendiente"]:
            filtro_inicial = "pendientes"
        elif arg in ["pasados", "pasado"]:
            filtro_inicial = "pasado"
    
    await enviar_lista_interactiva(
        update, context, context_key="lista", titulos=TITULOS["lista"], filtro=filtro_inicial
    )


async def lista_shared_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        filtro, context_key, cancel_flag = parts[2], parts[3], parts[4]
    elif action == "list_pivot":
        page = 1 # Al cambiar de vista, siempre volvemos a la página 1.
        filtro, context_key, cancel_flag = parts[1], parts[2], parts[3]
    else:
        # Fallback por si llega una acción desconocida.
        return

    mostrar_cancelar = (cancel_flag == "1")
    titulos_correctos = TITULOS.get(context_key, TITULOS["lista"])

    await enviar_lista_interactiva(
        update, context, 
        context_key=context_key, 
        titulos=titulos_correctos, 
        page=page, 
        filtro=filtro, 
        mostrar_boton_cancelar=mostrar_cancelar
    )


async def limpiar_callback_unificado(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    action, filtro_data = query.data.split(":")
    filtro, step = filtro_data.split("_") # 'pasados', 'ask'

    # Textos dinámicos según el filtro
    textos = {
        "pasados": {"nombre": "pasados", "pregunta": "todos tus recordatorios pasados"},
        "hechos": {"nombre": "Hechos", "pregunta": "todos tus recordatorios marcados como 'Hecho'"}
    }
    texto_actual = textos.get(filtro)
    if not texto_actual: return # Filtro no válido

    if step == "ask":
        keyboard = [[
            InlineKeyboardButton("✅ Sí, bórralos", callback_data=f"limpiar:{filtro}_confirm"),
            InlineKeyboardButton("❌ No", callback_data=f"limpiar:{filtro}_cancel")
        ]]
        await query.edit_message_text(
            text=f"⚠️ ¿Estás seguro de que quieres **borrar permanentemente** {texto_actual['pregunta']}? Esta acción no se puede deshacer.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif step == "confirm":
        # Llamamos a nuestra nueva función universal con el filtro correcto
        num_borrados, ids_borrados = borrar_recordatorios_por_filtro(update.effective_chat.id, filtro)
        for rid in ids_borrados:
            cancelar_avisos(str(rid))
        await query.edit_message_text(
            text=f"🪄✨ ¡Fregotego!\n\nSe han borrado {num_borrados} recordatorios '{texto_actual['nombre']}' de tu archivo.",
            parse_mode="Markdown"
        )
    elif step == "cancel":
        # Devolvemos al usuario a la lista de la que venía
        await enviar_lista_interactiva(update, context, context_key="lista", titulos=TITULOS["lista"], page=1, filtro=filtro)


async def placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a los clics en botones invisibles para que el cliente de Telegram no muestre un error."""
    await update.callback_query.answer()

async def lista_fijos_pagination_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Maneja la paginación de la lista de recordatorios fijos."""
    query = update.callback_query
    page = int(query.data.split(":")[1])
    # Reutilizamos la función de envío, pasándole la nueva página
    await enviar_lista_fijos(update, context, page=page)

# =============================================================================
# EXPORTACIÓN DE HANDLERS
# =============================================================================
# Estos handlers son importados y registrados en main.py.

# Handler para el comando inicial /lista
lista_command_handler = CommandHandler(["lista", "list"], lista_cmd)

# Handler para los botones de navegación (<<, >>, PENDIENTES, PASADOS)
lista_shared_handler = CallbackQueryHandler(lista_shared_callback, pattern=r"^(list_page|list_pivot):")

# Handler para el flujo de limpieza de recordatorios pasados
limpiar_handler_unificado = CallbackQueryHandler(limpiar_callback_unificado, pattern=r"^limpiar:")

# Handler para el botón universal de cancelación [X] en las listas
lista_cancel_handler = CallbackQueryHandler(cancelar_callback, pattern=r"^list_cancel$")

# Handler para los botones placeholder invisibles
placeholder_handler = CallbackQueryHandler(placeholder_callback, pattern=r"^placeholder$")

# Handler para la paginación de la lista de recordatorios fijos
lista_fijos_pagination_handler = CallbackQueryHandler(lista_fijos_pagination_callback, pattern=r"^fijo_list_page:")