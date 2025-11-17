# handlers/borrar.py
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
from utils import cancelar_conversacion, comando_inesperado, enviar_lista_interactiva, convertir_utc_a_local, normalizar_texto
from avisos import cancelar_avisos
from handlers.lista import TITULOS, lista_cancel_handler, lista_shared_callback
from personalidad import get_text

# --- DEFINICIÓN DE ESTADOS ---
ELEGIR_ID, CONFIRMAR = range(2)


# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def borrar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /borrar. Permite el modo rápido y el filtrado inicial."""
    # Modo rápido: si el primer argumento es un número, se procesa como ID.
    if context.args and context.args[0].replace("#", "").isdigit():
        return await _procesar_ids(update, context, context.args)
    
    # Modo interactivo con filtrado
    filtro_inicial = "futuro"
    if context.args:
        arg = context.args[0].lower()
        if arg in ["hechos", "hecho"]:
            filtro_inicial = "hechos"
        elif arg in ["pasados", "pasado"]:
            filtro_inicial = "pasado"
        # Añadimos "pendientes" para consistencia
        elif arg in ["pendientes", "pendiente"]:
            filtro_inicial = "pendientes"

    await enviar_lista_interactiva(
        update, context,
        context_key="borrar",
        titulos=TITULOS["borrar"],
        filtro=filtro_inicial,
        mostrar_boton_cancelar=True
    )
    return ELEGIR_ID

async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe los IDs después de que el usuario vea la lista."""
    # .split() maneja automáticamente múltiples IDs separados por espacios.
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID # Permite al usuario intentarlo de nuevo.
    
    return await _procesar_ids(update, context, ids)


async def _procesar_ids(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list[str]) -> int:
    """
    Función centralizada para validar IDs y pedir confirmación si es necesario.
    Utiliza consultas SQL optimizadas para manejar múltiples IDs eficientemente.
    """
    chat_id = update.effective_chat.id
    
    # 1. Limpiamos y validamos los IDs para asegurarnos de que son números.
    user_ids_a_buscar = []
    for user_id_str in ids:
        try:
            # Quitamos el '#' si lo tiene y lo convertimos a entero.
            user_ids_a_buscar.append(int(user_id_str.replace("#", "")))
        except (ValueError, TypeError):
            pass # Ignoramos las entradas que no sean números.

    if not user_ids_a_buscar:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # 2. Hacemos UNA SOLA CONSULTA a la base de datos para obtener la info de todos los IDs.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: PostgreSQL usa %s como placeholder, no ?.
            # psycopg2 puede manejar una tupla de valores para 'IN' directamente.
            query = "SELECT user_id, texto, fecha_hora FROM recordatorios WHERE user_id IN %s AND chat_id = %s"

            cursor.execute(query, (tuple(user_ids_a_buscar), chat_id))
            recordatorios_encontrados = cursor.fetchall()

    if not recordatorios_encontrados:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # Guardamos la información para el siguiente paso.
    context.user_data["info_a_borrar"] = recordatorios_encontrados
    
    # 3. Comprobamos el Modo Seguro.
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (1, 3):
        # Si se requiere confirmación, construimos el mensaje y esperamos respuesta.
        user_tz = get_config(chat_id, "user_timezone") or "UTC"
        mensaje_lista = []
        for user_id, texto, fecha_utc in recordatorios_encontrados:
            fecha_str = "Sin fecha"
            if fecha_utc:
                # ELIMINAMOS la línea que daba error: datetime.fromisoformat()
                fecha_local = convertir_utc_a_local(fecha_utc, user_tz)
                fecha_str = fecha_local.strftime("%d %b, %H:%M")
            mensaje_lista.append(f"  - `#{user_id}`: _{texto}_ ({fecha_str})")
            
        mensaje_confirmacion = (
            f"👵 ¡Quieto ahí! Vas a borrar permanentemente lo siguiente:\n\n"
            f"{'\n'.join(mensaje_lista)}\n\n"
            "¿Estás completamente seguro? Escribe `SI` para confirmar."
        )
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRMAR
    
    # Si no se requiere confirmación, borramos directamente.
    return await ejecutar_borrado(update, context)


async def confirmar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Se activa si el Modo Seguro está activo. Espera la confirmacion 'si'
    Utiliza la función normalizar_texto de utils.py para formatear la entrada
    """
    texto_normalizado = normalizar_texto(update.message.text.strip())
    
    if texto_normalizado.startswith("si"):
        return await ejecutar_borrado(update, context)
    
    await update.message.reply_text(get_text("cancelar"))
    return ConversationHandler.END

async def ejecutar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final de borrado. Realiza la operación en la DB y cancela los avisos."""
    chat_id = update.effective_chat.id
    info_a_borrar = context.user_data.get("info_a_borrar", [])
    if not info_a_borrar:
        # Salvaguarda por si se llega aquí sin datos.
        return ConversationHandler.END

    user_ids_a_borrar = [recordatorio[0] for recordatorio in info_a_borrar]

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # 1. Obtenemos los IDs GLOBALES para cancelar los jobs del scheduler.
            query_ids = "SELECT id FROM recordatorios WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_ids, (tuple(user_ids_a_borrar), chat_id))
            ids_globales = [row[0] for row in cursor.fetchall()]

            # 2. Hacemos UNA SOLA CONSULTA para borrar todos los recordatorios.
            query_delete = "DELETE FROM recordatorios WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_delete, (tuple(user_ids_a_borrar), chat_id))
    
    # 3. Cancelamos todos los avisos asociados.
    for rid in ids_globales:
        cancelar_avisos(str(rid))
    
    # 4. Enviamos un único mensaje de confirmación.
    if len(info_a_borrar) == 1:
        recordatorio = info_a_borrar[0]
        mensaje_exito = f"🗑️ ¡Listo! El recordatorio `#{recordatorio[0]}` ('_{recordatorio[1]}_') ha sido borrado."
    else:
        ids_formateados = [f"`#{r[0]}`" for r in info_a_borrar]
        mensaje_exito = f"🗑️ ¡Hecho! Los recordatorios {', '.join(ids_formateados)} han sido borrados."
            
    await update.message.reply_text(mensaje_exito, parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END

async def _navegar_lista_en_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Llama al handler de navegación de listas y mantiene el estado actual."""
    await lista_shared_callback(update, context)
    # Devolvemos el estado en el que queremos permanecer (elegir el ID)
    return ELEGIR_ID


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
borrar_handler = ConversationHandler(
    entry_points=[CommandHandler(["borrar", "borrsr", "del", "delete", "bor"], borrar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids),
                    CallbackQueryHandler(_navegar_lista_en_conversacion, pattern=r"^(list_page|list_pivot):")],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_borrado)]
    },
    fallbacks=[
        lista_cancel_handler,
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)