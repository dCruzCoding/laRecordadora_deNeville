from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from datetime import datetime
from db import get_connection, get_config
from utils import parsear_recordatorio, parsear_tiempo_a_minutos, cancelar_conversacion, convertir_utc_a_local, comando_inesperado, enviar_lista_interactiva
from avisos import cancelar_avisos, programar_avisos
from handlers.lista import TITULOS, lista_cancelar_handler
from personalidad import get_text

# Estados para la conversación de edición
ELEGIR_ID, ELEGIR_OPCION, EDITAR_RECORDATORIO, EDITAR_AVISO = range(4)

async def _procesar_id_y_avanzar(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id_str: str) -> int:
    """
    Función interna que busca un ID, guarda la info y muestra el menú de opciones.
    Es reutilizada por el modo rápido y el modo interactivo.
    """
    chat_id = update.effective_chat.id
    try:
        user_id_a_editar = int(user_id_str.replace("#", ""))
    except (ValueError, TypeError):
        await update.message.reply_text(get_text("error_no_id"))
        # Si el formato del ID es incorrecto, terminamos la conversación.
        return ConversationHandler.END

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, texto, fecha_hora, timezone, aviso_previo FROM recordatorios WHERE user_id = ? AND chat_id = ?", 
            (user_id_a_editar, chat_id)
        )
        recordatorio = cursor.fetchone()

    if not recordatorio:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    global_id, texto, fecha_iso, timezone, aviso_previo = recordatorio
    
    context.user_data["editar_info"] = {
        "global_id": global_id, "user_id": user_id_a_editar,
        "texto": texto, "fecha_iso": fecha_iso,
        "timezone": timezone, "aviso_previo": aviso_previo
    }

    fecha_str = "Sin fecha"
    if fecha_iso:
        fecha_local = convertir_utc_a_local(datetime.fromisoformat(fecha_iso), timezone or get_config(chat_id, "user_timezone") or "UTC")
        fecha_str = fecha_local.strftime("%d %b, %H:%M")

    keyboard = [
        [InlineKeyboardButton("📝 Contenido (Fecha/Texto)", callback_data="editar_contenido"),
        InlineKeyboardButton("⏳ Aviso Previo", callback_data="editar_aviso"),         
        InlineKeyboardButton("<< Volver", callback_data="editar_volver_lista")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensaje = get_text("editar_elige_opcion", user_id=user_id_a_editar, texto=texto, fecha=fecha_str)
  
    # Si la llamada viene de un mensaje de texto, enviamos uno nuevo.
    # Si viene de un callback (como el futuro botón "volver"), editamos el mensaje.
    if update.callback_query:
        await update.callback_query.edit_message_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
    else:
        await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
    
    # Avanzamos conversación al siguiente estado
    return ELEGIR_OPCION

async def editar_volver_a_lista(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Se activa al pulsar 'Volver a la lista'.
    Reutiliza el mensaje actual para mostrar la lista interactiva.
    """
    query = update.callback_query
    await query.answer()

    # Llamamos a la función que sabe cómo dibujar la lista, reutilizando el mensaje.
    await enviar_lista_interactiva(
        update, context, 
        context_key="editar", 
        titulos=TITULOS["editar"],
        mostrar_boton_cancelar=True
    )
    
    # Le decimos a la conversación que vuelva al estado de "esperar un ID".
    return ELEGIR_ID

async def editar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada para /editar. Ahora tiene un modo rápido y un modo interactivo.
    """
    # MODO RÁPIDO: si el usuario proporciona un argumento (ej: /editar 5)
    if context.args:
        # Validamos que solo haya un argumento
        if len(context.args) > 1:
            await update.message.reply_text("👵 ¡Tranquilidad! Solo puedes editar un recordatorio a la vez. Escribe `/editar` y elige de la lista, o `/editar ID`.")
            return ConversationHandler.END
        
        # Procesamos el ID directamente
        user_id_str = context.args[0]
        return await _procesar_id_y_avanzar(update, context, user_id_str)
    
    # MODO INTERACTIVO: si el usuario solo escribe /editar
    else:
        await enviar_lista_interactiva(
            update, context, 
            context_key="editar", 
            titulos=TITULOS["editar"],
            mostrar_boton_cancelar=True
        )
        return ELEGIR_ID



# --- HANDLER PARA EL MODO INTERACTIVO) ---
async def recibir_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el ID del recordatorio cuando el usuario lo escribe después de ver la lista."""
    user_id_str = update.message.text
    return await _procesar_id_y_avanzar(update, context, user_id_str)


# --- Rama 1: Editar Contenido ---
async def pedir_nuevo_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    
    fecha_str = "Sin fecha"
    if info.get("fecha_iso"):
        fecha_local = convertir_utc_a_local(datetime.fromisoformat(info["fecha_iso"]), info["timezone"])
        fecha_str = fecha_local.strftime("%d %b, %H:%M")
        
    mensaje = get_text("editar_pide_recordatorio_nuevo", texto_actual=info.get("texto"), fecha_actual=fecha_str)
    await query.edit_message_text(text=mensaje, parse_mode="Markdown")
    return EDITAR_RECORDATORIO

async def guardar_nuevo_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    
    texto, fecha, error = parsear_recordatorio(update.message.text, user_timezone=user_tz)
    
    if error:
        await update.message.reply_text(get_text("error_formato"))
        return EDITAR_RECORDATORIO

    fecha_iso = fecha.isoformat() if fecha else None
    with get_connection() as conn:
        conn.execute(
            "UPDATE recordatorios SET texto = ?, fecha_hora = ?, timezone = ? WHERE id = ?",
            (texto, fecha_iso, user_tz, info["global_id"])
        )
        conn.commit()
    
    cancelar_avisos(str(info["global_id"]))
    aviso_previo = info.get("aviso_previo", 0) # Usamos el aviso previo que ya tenía
    
    if fecha:
        await programar_avisos(chat_id, str(info["global_id"]), info["user_id"], texto, fecha, aviso_previo)
        
    fecha_str = fecha.strftime("%d %b, %H:%M") if fecha else "Sin fecha"
    mensaje = get_text("editar_confirmacion_recordatorio", user_id=info["user_id"], texto=texto, fecha=fecha_str)
    await update.message.reply_text(mensaje, parse_mode="Markdown")
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Rama 2: Editar Aviso Previo (COMPLETA) ---
async def pedir_nuevo_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario el nuevo tiempo de aviso previo."""
    query = update.callback_query
    await query.answer()
    info = context.user_data.get("editar_info", {})
    
    aviso_actual_min = info.get("aviso_previo", 0)
    
    # Formateamos el tiempo actual para mostrarlo
    if aviso_actual_min > 0:
        horas = aviso_actual_min // 60
        mins = aviso_actual_min % 60
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
    else:
        tiempo_str = "ninguno"
        
    mensaje = get_text("editar_pide_aviso_nuevo", aviso_actual=tiempo_str)
    await query.edit_message_text(text=mensaje, parse_mode="Markdown")
    return EDITAR_AVISO

async def guardar_nuevo_aviso(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el nuevo tiempo de aviso, lo guarda y reprograma."""
    
    # Parseo y obtención de datos
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id
    
    aviso_str = update.message.text.strip().lower()
    minutos = parsear_tiempo_a_minutos(aviso_str)

    # Validación: Formato de tiempo incorrecto
    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDITAR_AVISO # Mantenemos al usuario en este estado

    # Si el usuario elige no poner aviso (0), el flujo termina con éxito.
    if minutos == 0:
        # Guardamos en la DB y cancelamos jobs existentes
        with get_connection() as conn:
            conn.execute("UPDATE recordatorios SET aviso_previo = ? WHERE id = ?", (minutos, info["global_id"]))
            conn.commit()
        cancelar_avisos(str(info["global_id"]))

        await update.message.reply_text(f"Se ha cancelado el aviso del recordatorio indicado (#{info['user_id']}).")
        context.user_data.clear()
        return ConversationHandler.END

    # Si el recordatorio no tiene fecha, no podemos programar aviso.
    fecha_iso = info.get("fecha_iso")
    if not fecha_iso:
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        return EDITAR_AVISO

    # Validación de tiempo pasado
    fecha = datetime.fromisoformat(fecha_iso)
    se_programo_aviso = await programar_avisos(
        chat_id, 
        str(info["global_id"]), 
        info["user_id"], 
        info["texto"], 
        fecha, 
        minutos
    )

    # Si el aviso se programó con éxito, actualizamos la DB y terminamos.
    if se_programo_aviso:
        with get_connection() as conn:
            conn.execute("UPDATE recordatorios SET aviso_previo = ? WHERE id = ?", (minutos, info["global_id"]))
            conn.commit()

        # Formateamos el nuevo tiempo para el mensaje de confirmación
        horas = minutos // 60
        mins = minutos % 60
        tiempo_nuevo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"

        mensaje_confirmacion = get_text("editar_confirmacion_aviso", user_id=info["user_id"], aviso_nuevo=tiempo_nuevo_str)
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")

        context.user_data.clear()
        return ConversationHandler.END

    # Si el aviso NO se programó, informamos y nos quedamos en el mismo estado.
    else:
        mensaje_error = get_text("error_aviso_pasado_reintentar")
        await update.message.reply_text(mensaje_error)
        return EDITAR_AVISO # ¡La clave! Volvemos a pedir el dato.

# --- Conversational Handler ---
editar_handler = ConversationHandler(
    entry_points=[CommandHandler("editar", editar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_id)],
        ELEGIR_OPCION: [
            CallbackQueryHandler(pedir_nuevo_recordatorio, pattern="^editar_contenido$"),
            CallbackQueryHandler(pedir_nuevo_aviso, pattern="^editar_aviso$"),
            CallbackQueryHandler(editar_volver_a_lista, pattern="^editar_volver_lista$")
        ],
        EDITAR_RECORDATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_recordatorio)],
        EDITAR_AVISO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_aviso)],
    },
    fallbacks=[
        lista_cancelar_handler,
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)