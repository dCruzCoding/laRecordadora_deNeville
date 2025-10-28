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

from db import borrar_recordatorios_pasados
from utils import enviar_lista_interactiva, cancelar_callback
from avisos import cancelar_avisos

# =============================================================================
# DEFINICIÓN DE TÍTULOS
# =============================================================================

# Diccionario centralizado de títulos para cada contexto de lista.
# Esto permite que la función de UI en utils.py sea agnóstica al contenido.
TITULOS = {
    "lista": {
        "futuro": "📜  **RECORDATORIOS**  📜",
        "pasado": "🗂️  **Recordatorios PASADOS**  🗂️"
    },
    "borrar": {
        "futuro": "🗑️  **BORRAR (Pendientes)**  🗑️",
        "pasado": "🗑️  **BORRAR (Pasados)**  🗑️"
    },
    "editar": {
        "futuro": "🪄  **EDITAR (Pendientes)**  🪄",
        "pasado": "🪄  **EDITAR (Pasados)**  🪄"
    },
    "cambiar": {
        "futuro": "🔄  **CAMBIAR ESTADO (Pendientes)**  🔄",
        "pasado": "🔄  **CAMBIAR ESTADO (Pasados)**  🔄"
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
    # NUEVO: Por defecto, mostramos los recordatorios futuros (pendientes).
    filtro = "futuro"

    # NUEVO: Comprobamos si el usuario ha escrito algo después del comando.
    if context.args:
        # Tomamos la primera palabra, la pasamos a minúsculas para que no importe cómo la escriba.
        arg = context.args[0].lower()
        
        # Mapeamos las palabras que el usuario podría usar a nuestro filtro interno.
        if arg in ["pasados", "hechos", "pasado", "hecho"]:
            filtro = "pasado"
        # Si escribe "pendientes" o cualquier otra cosa, se quedará con el filtro "futuro" por defecto.

    # NUEVO: Pasamos el filtro determinado a la función que dibuja la lista.
    await enviar_lista_interactiva(
        update, context, context_key="lista", titulos=TITULOS["lista"], filtro=filtro
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


async def limpiar_pasados_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja el flujo de confirmación para limpiar el archivo de recordatorios pasados.
    """
    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "limpiar_pasados_ask":
        keyboard = [[
            InlineKeyboardButton("✅ Sí, bórralos", callback_data="limpiar_pasados_confirm"),
            InlineKeyboardButton("❌ No", callback_data="limpiar_pasados_cancel")
        ]]
        await query.edit_message_text(
            text="⚠️ ¿Estás seguro de que quieres **borrar permanentemente** todos tus recordatorios pasados? Esta acción no se puede deshacer.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    elif action == "limpiar_pasados_confirm":
        num_borrados, ids_borrados = borrar_recordatorios_pasados(update.effective_chat.id)
        for rid in ids_borrados:
            cancelar_avisos(str(rid))
        await query.edit_message_text(
            text=f"🪄✨ ¡Fregotego!\n\nSe han borrado {num_borrados} recordatorios pasados de tu archivo.",
            parse_mode="Markdown"
        )
    elif action == "limpiar_pasados_cancel":
        # Si cancela, le volvemos a mostrar la lista de pasados.
        await enviar_lista_interactiva(update, context, context_key="lista", titulos=TITULOS["lista"], page=1, filtro="pasado")


async def placeholder_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Responde a los clics en botones invisibles para que el cliente de Telegram no muestre un error."""
    await update.callback_query.answer()


# =============================================================================
# EXPORTACIÓN DE HANDLERS
# =============================================================================
# Estos handlers son importados y registrados en main.py.

# Handler para el comando inicial /lista
lista_command_handler = CommandHandler("lista", lista_cmd)

# Handler para los botones de navegación (<<, >>, PENDIENTES, PASADOS)
lista_shared_handler = CallbackQueryHandler(lista_shared_callback, pattern=r"^(list_page|list_pivot):")

# Handler para el flujo de limpieza de recordatorios pasados
limpiar_pasados_handler = CallbackQueryHandler(limpiar_pasados_callback, pattern=r"^limpiar_pasados_")

# Handler para el botón universal de cancelación [X] en las listas
lista_cancel_handler = CallbackQueryHandler(cancelar_callback, pattern=r"^list_cancel$")

# Handler para los botones placeholder invisibles
placeholder_handler = CallbackQueryHandler(placeholder_callback, pattern=r"^placeholder$")