# handlers/cambiar_estado.py
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
from utils import parsear_tiempo_a_minutos, cancelar_conversacion, comando_inesperado, enviar_lista_interactiva, normalizar_texto
from avisos import cancelar_avisos, programar_avisos
from handlers.lista import TITULOS, lista_cancel_handler, lista_shared_callback
from personalidad import get_text

# --- DEFINICIÓN DE ESTADOS ---
ELEGIR_ID, CONFIRMAR_CAMBIO, REPROGRAMAR_AVISO = range(3)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def cambiar_estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /cambiar. Dirige al modo rápido o interactivo."""
    # Modo rápido: si el primer argumento es un número, se procesa como ID.
    if context.args and context.args[0].replace("#", "").isdigit():
        return await _procesar_ids_para_cambiar(update, context, context.args)
    
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
        context_key="cambiar",
        titulos=TITULOS["cambiar"],
        filtro=filtro_inicial,
        mostrar_boton_cancelar=True
    )
    return ELEGIR_ID


async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe los IDs después de que el usuario vea la lista."""
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID
    
    return await _procesar_ids_para_cambiar(update, context, ids)


async def _procesar_ids_para_cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list[str]) -> int:
    """Valida los IDs proporcionados y pide confirmación si el Modo Seguro está activo."""
    chat_id = update.effective_chat.id
    user_ids_a_buscar = [int(uid.replace("#", "")) for uid in ids if uid.replace("#", "").isdigit()]

    if not user_ids_a_buscar:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: Placeholder a %s y uso de tupla para IN
            query = "SELECT user_id, texto, estado FROM recordatorios WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (tuple(user_ids_a_buscar), chat_id))
            recordatorios_encontrados = cursor.fetchall()

    if not recordatorios_encontrados:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    context.user_data["info_a_cambiar"] = recordatorios_encontrados
    
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (2, 3):
        emojis_estado = {0: "⬜️", 1: "✅"}
        mensaje_lista = []
        for user_id, texto, estado_actual in recordatorios_encontrados:
            emoji_viejo = emojis_estado.get(estado_actual, "❓")
            estado_nuevo = 1 - estado_actual # Simple interruptor 0->1, 1->0
            emoji_nuevo = emojis_estado.get(estado_nuevo, "❓")
            mensaje_lista.append(f"  - `#{user_id}`: _{texto}_\n    *Cambiará de {emoji_viejo} ➡️ {emoji_nuevo}*")
            
        mensaje_confirmacion = (f"👵 ¿Estás seguro de que quieres cambiar el estado de lo siguiente?:\n\n"
                              f"{'\n\n'.join(mensaje_lista)}\n\n"
                              "Responde `SI` para confirmar.")
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRMAR_CAMBIO
    
    return await ejecutar_cambio(update, context)
    

async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Espera la confirmación 'SI' del usuario de forma robusta."""
    texto_normalizado = normalizar_texto(update.message.text.strip())
    if texto_normalizado.startswith("si"):
        return await ejecutar_cambio(update, context)

    await update.message.reply_text(get_text("cancelar"))
    return ConversationHandler.END


async def ejecutar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final: cambia el estado en la DB, gestiona avisos y decide si reprogramar."""
    chat_id = update.effective_chat.id
    info_a_cambiar = context.user_data.get("info_a_cambiar", [])
    if not info_a_cambiar: return ConversationHandler.END

    user_ids_a_cambiar = [recordatorio[0] for recordatorio in info_a_cambiar]
    
    # 1. Obtenemos toda la información necesaria con UNA SOLA CONSULTA.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: Placeholder a %s y uso de tupla para IN
            query = "SELECT id, user_id, estado, texto, fecha_hora, aviso_previo FROM recordatorios WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (tuple(user_ids_a_cambiar), chat_id))
            full_info_recordatorios = cursor.fetchall()

            # CAMBIO: La sintaxis de UPDATE ahora usa %s
            ids_a_pendiente = [r[1] for r in full_info_recordatorios if r[2] == 1]
            ids_a_hecho = [r[1] for r in full_info_recordatorios if r[2] == 0]     
            
            if ids_a_pendiente:
                cursor.execute("UPDATE recordatorios SET estado = 0 WHERE user_id IN %s AND chat_id = %s", 
                               (tuple(ids_a_pendiente), chat_id))
            if ids_a_hecho:
                cursor.execute("UPDATE recordatorios SET estado = 1 WHERE user_id IN %s AND chat_id = %s", 
                               (tuple(ids_a_hecho), chat_id))

    # 3. Procesamos los resultados en Python.
    reprogramables, pasados_sin_aviso = [], []
    
    for r_id, u_id, estado, texto, fecha_utc, aviso in full_info_recordatorios:
        if u_id in ids_a_hecho:
            cancelar_avisos(str(r_id))
        
        elif u_id in ids_a_pendiente:
            cancelar_avisos(str(r_id))
            if fecha_utc:
                # ELIMINAMOS la línea que daba error: datetime.fromisoformat()
                if fecha_utc > datetime.now(pytz.utc):
                    reprogramables.append({"global_id": r_id, "user_id": u_id, "texto": texto, "fecha": fecha_utc})
                else:
                    pasados_sin_aviso.append(f"`#{u_id}`")

    ids_formateados = [f"`#{r[0]}`" for r in info_a_cambiar]
    await update.message.reply_text(f"🔄 ¡Hecho! Se ha actualizado el estado de: {', '.join(ids_formateados)}.", parse_mode="Markdown")
    
    # 4. Enviamos los mensajes de feedback al usuario.
    if pasados_sin_aviso:
        await update.message.reply_text(
            f"⚠️ Nota: El/los recordatorio(s) {', '.join(pasados_sin_aviso)} que has reactivado ya ha(n) pasado. No se pueden añadir nuevos avisos.",
            parse_mode="Markdown"
        )

    # 5. Si hay recordatorios para reprogramar, iniciamos el sub-flujo.
    if reprogramables:
        context.user_data["reprogramar_lista"] = reprogramables
        primer_recordatorio = reprogramables[0]
        mensaje_reprogramar = (f"🗓️ Has reactivado el recordatorio `#{primer_recordatorio['user_id']}` - _{primer_recordatorio['texto']}_.\n\n"
                               f"{get_text('recordar_pide_aviso')}")
        await update.message.reply_text(mensaje_reprogramar, parse_mode="Markdown")
        return REPROGRAMAR_AVISO
    
    context.user_data.clear()
    return ConversationHandler.END

async def recibir_nuevo_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el tiempo para el nuevo aviso y lo programa."""
    aviso_str = update.message.text.strip().lower()
    minutos = parsear_tiempo_a_minutos(aviso_str)

    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return REPROGRAMAR_AVISO

    # Obtenemos el recordatorio que estábamos reprogramando
    reprogramar_lista = context.user_data.get("reprogramar_lista", [])
    recordatorio_actual = reprogramar_lista.pop(0) # Lo sacamos de la lista
    
    # Guardamos el nuevo aviso_previo en la DB
    with get_connection() as conn:
        # CAMBIO: Placeholder a %s
        conn.cursor().execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (minutos, recordatorio_actual["global_id"]))

    # Programamos el aviso con la nueva configuración
    await programar_avisos(
        update.effective_chat.id,
        str(recordatorio_actual["global_id"]),
        recordatorio_actual["user_id"],
        recordatorio_actual["texto"],
        recordatorio_actual["fecha"],
        minutos
    )
    mensaje_confirmacion = get_text("aviso_reprogramado", id=recordatorio_actual['user_id']) # <-- CAMBIO
    await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown") 

    # Si quedan más recordatorios por reprogramar, preguntamos por el siguiente
    if reprogramar_lista:
        context.user_data["reprogramar_lista"] = reprogramar_lista
        siguiente_recordatorio = reprogramar_lista[0]

        mensaje_siguiente = (
            f"🗓️ Ahora, para `#{siguiente_recordatorio['user_id']}` - _{siguiente_recordatorio['texto']}_.\n\n"
            f"{get_text('recordar_pide_aviso')}"
        )
        await update.message.reply_text(mensaje_siguiente, parse_mode="Markdown")
        return REPROGRAMAR_AVISO

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

cambiar_estado_handler = ConversationHandler(
    entry_points=[CommandHandler("cambiar", cambiar_estado_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids),
                    CallbackQueryHandler(_navegar_lista_en_conversacion, pattern=r"^(list_page|list_pivot):")],
        CONFIRMAR_CAMBIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_cambio)],
        REPROGRAMAR_AVISO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nuevo_aviso)]
    },
    fallbacks=[
        lista_cancel_handler,
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)