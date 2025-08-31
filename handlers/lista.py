from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, CommandHandler, CallbackQueryHandler
from db import borrar_recordatorios_pasados
from utils import enviar_lista_interactiva, cancelar_callback
from avisos import cancelar_avisos

# --- DEFINIMOS LOS TÍTULOS PARA CADA CONTEXTO ---
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

async def lista_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /lista."""
    await enviar_lista_interactiva(update, context, context_key="lista", titulos=TITULOS["lista"])

async def lista_shared_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    UN ÚNICO HANDLER para paginación y pivote que funciona para TODOS los comandos.
    """
    query = update.callback_query
    # callback_data: "list_page:PAG:FILTRO:CONTEXTO" o "list_pivot:FILTRO:CONTEXTO"
    parts = query.data.split(":")
    action = parts[0]
    
    if action == "list_page":
        page, filtro, context_key = int(parts[1]), parts[2], parts[3]
    elif action == "list_pivot":
        page, filtro, context_key = 1, parts[1], parts[2]
    
    # Usamos el context_key para obtener los títulos correctos del diccionario
    titulos_correctos = TITULOS.get(context_key, TITULOS["lista"]) # Default a 'lista' por seguridad

    await enviar_lista_interactiva(
        update, context, context_key=context_key, titulos=titulos_correctos, page=page, filtro=filtro
    )

# --- UN ÚNICO HANDLER INTELIGENTE PARA LA LIMPIEZA ---

async def limpiar_pasados_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """El flujo de limpieza se mantiene igual, pero al cancelar vuelve a llamar a la función universal."""
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
            text=f"**¡Fregotego!** 🪄✨\n\n🧹\n🧹\n🧹\n\nSe han **borrado {num_borrados} recordatorios pasados** de tu archivo."
        )

    elif action == "limpiar_pasados_cancel":
        # Al cancelar, volvemos a la lista de pasados usando la función universal
        await enviar_lista_interactiva(
            update, context, 
            context_key="lista",
            titulos=TITULOS["lista"], 
            page=1, 
            filtro="pasado"
        )


# --- HANDLERS ---

lista_handler = CommandHandler("lista", lista_cmd)
lista_shared_handler = CallbackQueryHandler(lista_shared_callback, pattern=r"^(list_page|list_pivot):")
limpiar_pasados_handler = CallbackQueryHandler(limpiar_pasados_callback, pattern=r"^limpiar_pasados_")
lista_cancelar_handler = CallbackQueryHandler(cancelar_callback, pattern=r"^list_cancel$")