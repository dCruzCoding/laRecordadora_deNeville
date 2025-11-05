# handlers/editar.py
"""
Módulo para el comando /editar.

Gestiona una conversación compleja y ramificada para permitir al usuario
modificar un recordatorio existente. El flujo es el siguiente:
1.  Elige un ID (modo rápido o interactivo).
2.  Se presenta un sub-menú para elegir qué editar: el contenido o el aviso.
3.a. Si elige contenido, se pide el nuevo `fecha * texto`.
3.b. Si elige aviso, se pide el nuevo tiempo de aviso.
4.  Se guarda el cambio, se reprograman los avisos si es necesario, y se finaliza.
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from datetime import datetime
import pytz

from db import get_connection, get_config
from utils import (
    enviar_lista_interactiva, parsear_recordatorio, parsear_tiempo_a_minutos, 
    cancelar_conversacion, comando_inesperado, convertir_utc_a_local
)
from handlers.lista import TITULOS, lista_cancel_handler, lista_shared_callback
from avisos import cancelar_avisos, programar_avisos
from personalidad import get_text

# --- DEFINICIÓN DE ESTADOS ---
ELEGIR_ID, ELEGIR_OPCION, EDITAR_RECORDATORIO, EDITAR_AVISO = range(4)



# =============================================================================
# SECCIÓN 1: SELECCIÓN DEL RECORDATORIO A EDITAR
# =============================================================================

async def editar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /editar. Dirige al modo rápido o interactivo."""
    if context.args:
        if len(context.args) > 1:
            await update.message.reply_text("👵 ¡Tranquilidad! Solo puedes editar un recordatorio a la vez.")
            return ConversationHandler.END
        return await _procesar_id_y_avanzar(update, context, context.args[0])
    
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
        context_key="editar",
        titulos=TITULOS["editar"],
        filtro=filtro_inicial,
        mostrar_boton_cancelar=True
    )
    return ELEGIR_ID


async def recibir_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el ID escrito por el usuario tras ver la lista."""
    return await _procesar_id_y_avanzar(update, context, update.message.text)


async def _procesar_id_y_avanzar(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_str: str) -> int:
    """
    Busca el recordatorio por ID, lo guarda en el contexto y muestra el menú de opciones de edición.
    """
    chat_id = update.effective_chat.id
    try:
        user_id_a_editar = int(user_id_str.replace("#", ""))
    except (ValueError, TypeError):
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: Placeholder a %s
            cursor.execute(
                "SELECT id, texto, fecha_hora, timezone, aviso_previo FROM recordatorios WHERE user_id = %s AND chat_id = %s", 
                (user_id_a_editar, chat_id)
            )
            recordatorio = cursor.fetchone()

    if not recordatorio:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # Guardamos toda la información necesaria para los siguientes pasos.
    global_id, texto, fecha_utc, timezone, aviso_previo = recordatorio
    context.user_data["editar_info"] = {
        "global_id": global_id, "user_id": user_id_a_editar, "texto": texto,
        "fecha_utc": fecha_utc, "timezone": timezone, "aviso_previo": aviso_previo
    }

    # Preparamos y enviamos el menú de opciones.
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    fecha_str = "Sin fecha"
    if fecha_utc:
        fecha_local = convertir_utc_a_local(fecha_utc, timezone or user_tz)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")

    keyboard = [
        [InlineKeyboardButton("📝 Contenido (Fecha/Texto)", callback_data="editar_contenido")],
        [InlineKeyboardButton("⏳ Aviso Previo", callback_data="editar_aviso")],
        [InlineKeyboardButton("<< Volver a la lista", callback_data="editar_volver_lista")]
    ]
    
    mensaje = get_text("editar_elige_opcion", user_id=user_id_a_editar, texto=texto, fecha=fecha_str)
    
    # Reutilizamos el mensaje si venimos de un callback (ej: 'Volver'), si no, enviamos uno nuevo.
    if update.callback_query:
        await update.callback_query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    
    return ELEGIR_OPCION


async def editar_volver_a_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback para el botón 'Volver'. Muestra la lista interactiva de nuevo."""
    await enviar_lista_interactiva(
        update, context, context_key="editar", titulos=TITULOS["editar"], mostrar_boton_cancelar=True
    )
    return ELEGIR_ID



# =============================================================================
# SECCIÓN 2: RAMA DE EDICIÓN DE "CONTENIDO"
# =============================================================================

async def pedir_nuevo_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario que escriba el nuevo `fecha * texto`."""
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    
    user_tz = get_config(update.effective_chat.id, "user_timezone") or 'UTC'
    fecha_str = "Sin fecha"

    fecha_utc = info.get("fecha_utc")
    if fecha_utc:
        fecha_local = convertir_utc_a_local(fecha_utc, info.get("timezone") or user_tz)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")
        
    mensaje = get_text("editar_pide_recordatorio_nuevo", texto_actual=info.get("texto", ""), fecha_actual=fecha_str)
    await query.edit_message_text(text=mensaje, parse_mode="Markdown")
    return EDITAR_RECORDATORIO


async def guardar_nuevo_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nuevo contenido, reprograma el aviso (si lo tenía) y finaliza."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END

    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    
    texto, fecha, error = parsear_recordatorio(update.message.text, user_timezone=user_tz)
    
    if error:
        await update.message.reply_text(get_text("error_formato"))
        return EDITAR_RECORDATORIO

    with get_connection() as conn:
        # CAMBIO: Placeholder a %s
        conn.cursor().execute(
            "UPDATE recordatorios SET texto = %s, fecha_hora = %s, timezone = %s WHERE id = %s",
            (texto, fecha, user_tz, info["global_id"])
        )
    
    # Reprogramamos los avisos usando el 'aviso_previo' que ya estaba guardado.
    cancelar_avisos(str(info["global_id"]))
    aviso_previo = info.get("aviso_previo", 0)
    if fecha and aviso_previo is not None:
        await programar_avisos(chat_id, str(info["global_id"]), info["user_id"], texto, fecha, aviso_previo)
        
    if fecha:
        # Convertimos la fecha UTC a la zona horaria local del usuario ANTES de formatearla.
        fecha_local = convertir_utc_a_local(fecha, user_tz)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")
    else:
        fecha_str = "Sin fecha"
        
    mensaje = get_text("editar_confirmacion_recordatorio", user_id=info["user_id"], texto=texto, fecha=fecha_str)
    await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 3: RAMA DE EDICIÓN DE "AVISO PREVIO"
# =============================================================================

async def pedir_nuevo_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Pide al usuario el nuevo tiempo de aviso previo, PERO PRIMERO VALIDA
    si el recordatorio puede tener un aviso.
    """
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id


    # --- LÓGICA DE VALIDACIÓN ---
    # 1. Obtenemos el estado actual desde la base de datos para estar seguros.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Placeholder >> %s
            cursor.execute("SELECT estado, fecha_hora FROM recordatorios WHERE id = %s", (info.get("global_id"),))
            recordatorio_actual = cursor.fetchone()
    
    if recordatorio_actual:
        estado_actual, fecha_utc_actual = recordatorio_actual
        
        # 2. Comprobamos si el recordatorio está hecho (estado 1).
        if estado_actual == 1:
            await context.bot.send_message(chat_id=chat_id, text=get_text("error_aviso_no_permitido"))
            # Devolvemos al usuario al menú anterior (elegir opción)
            return ELEGIR_OPCION
            
        # 3. Comprobamos si la fecha ya ha pasado.
        if fecha_utc_actual:
            if fecha_utc_actual < datetime.now(pytz.utc):
                await context.bot.send_message(chat_id=chat_id, text=get_text("error_aviso_no_permitido"))
                return ELEGIR_OPCION

    # Si pasa todas las validaciones, continuamos con el flujo normal.
    aviso_actual_min = info.get("aviso_previo", 0)
    if aviso_actual_min and aviso_actual_min > 0:
        horas, mins = divmod(aviso_actual_min, 60)
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
    else:
        tiempo_str = "ninguno"
        
    mensaje = get_text("editar_pide_aviso_nuevo", aviso_actual=tiempo_str)
    await query.edit_message_text(text=mensaje, parse_mode="Markdown")
    return EDITAR_AVISO


async def guardar_nuevo_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nuevo aviso, valida la fecha y reprograma."""
    info = context.user_data.get("editar_info")
    if not info: return ConversationHandler.END
    
    minutos = parsear_tiempo_a_minutos(update.message.text)
    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDITAR_AVISO
        
    if minutos == 0:
        with get_connection() as conn:
            conn.cursor().execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (0, info["global_id"]))
        cancelar_avisos(str(info["global_id"]))
        mensaje_confirmacion = get_text("editar_confirmacion_aviso", user_id=info["user_id"], aviso_nuevo="ninguno")
    
    elif not info.get("fecha_utc"):
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        return EDITAR_AVISO
    
    else:
        # CAMBIO: Usamos directamente el objeto datetime guardado.
        fecha = info["fecha_utc"]
        se_programo_aviso = await programar_avisos(
            update.effective_chat.id, str(info["global_id"]), info["user_id"], info["texto"], fecha, minutos
        )
        if se_programo_aviso:
            with get_connection() as conn:
                conn.cursor().execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (minutos, info["global_id"]))
            horas, mins = divmod(minutos, 60)
            tiempo_nuevo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            mensaje_confirmacion = get_text("editar_confirmacion_aviso", user_id=info["user_id"], aviso_nuevo=tiempo_nuevo_str)
        else:
            await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
            return EDITAR_AVISO

    await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================

# Justo antes del ConversationHandler
async def _navegar_lista_en_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Llama al handler de navegación de listas y mantiene el estado actual."""
    await lista_shared_callback(update, context)
    # Devolvemos el estado en el que queremos permanecer (elegir el ID)
    return ELEGIR_ID

editar_handler = ConversationHandler(
    entry_points=[CommandHandler("editar", editar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_id),
                    CallbackQueryHandler(_navegar_lista_en_conversacion, pattern=r"^(list_page|list_pivot):")],
        ELEGIR_OPCION: [
            CallbackQueryHandler(pedir_nuevo_recordatorio, pattern="^editar_contenido$"),
            CallbackQueryHandler(pedir_nuevo_aviso, pattern="^editar_aviso$"),
            CallbackQueryHandler(editar_volver_a_lista, pattern="^editar_volver_lista$"),
        ],
        EDITAR_RECORDATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_recordatorio)],
        EDITAR_AVISO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_aviso)],
    },
    fallbacks=[
        lista_cancel_handler,
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)