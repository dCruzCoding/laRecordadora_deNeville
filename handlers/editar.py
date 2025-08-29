from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
)
from datetime import datetime
from db import get_connection, get_config, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje, parsear_recordatorio, parsear_tiempo_a_minutos, cancelar_conversacion, convertir_utc_a_local, comando_inesperado
from avisos import cancelar_avisos, programar_avisos
from config import ESTADOS
from personalidad import get_text

# Estados para la conversación de edición
ELEGIR_ID, ELEGIR_OPCION, EDITAR_RECORDATORIO, EDITAR_AVISO = range(4)

async def editar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para /editar. Muestra la lista de recordatorios."""
    actualizar_recordatorios_pasados()
    chat_id = update.effective_chat.id
    
    with get_connection() as conn:
        cursor = conn.cursor()
        # Mostramos solo los recordatorios que se pueden editar (Pendientes y Pasados)
        cursor.execute(
            "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone FROM recordatorios WHERE chat_id = ? AND estado != 1 ORDER BY estado, user_id",
            (chat_id,)
        )
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 Criatura, no tienes recordatorios pendientes o pasados que puedas editar.")
        return ConversationHandler.END

    pendientes = [r for r in recordatorios if r[5] == 0]
    pasados = [r for r in recordatorios if r[5] == 2]
    
    secciones = []
    if pendientes:
        secciones.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(chat_id, pendientes)}")
    if pasados:
        secciones.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(chat_id, pasados)}")

    mensaje_lista = "*✏️ Lista para Editar:*\n\n" + "\n\n".join(secciones)
    mensaje_lista += "\n\n" + get_text("editar_pide_id")
    
    await update.message.reply_text(mensaje_lista, parse_mode="Markdown")
    return ELEGIR_ID

async def recibir_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el ID del recordatorio a editar y muestra las opciones."""
    chat_id = update.effective_chat.id
    try:
        user_id_a_editar = int(update.message.text.replace("#", ""))
    except (ValueError, TypeError):
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID

    with get_connection() as conn:
        cursor = conn.cursor()
        # Pedimos toda la info que necesitaremos
        cursor.execute(
            "SELECT id, texto, fecha_hora, timezone, aviso_previo FROM recordatorios WHERE user_id = ? AND chat_id = ?", 
            (user_id_a_editar, chat_id)
        )
        recordatorio = cursor.fetchone()

    if not recordatorio:
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID

    global_id, texto, fecha_iso, timezone, aviso_previo = recordatorio
    
    context.user_data["editar_info"] = {
        "global_id": global_id, "user_id": user_id_a_editar,
        "texto": texto, "fecha_iso": fecha_iso,
        "timezone": timezone, "aviso_previo": aviso_previo
    }

    fecha_str = "Sin fecha"
    if fecha_iso:
        fecha_local = convertir_utc_a_local(datetime.fromisoformat(fecha_iso), timezone)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")

    keyboard = [
        [InlineKeyboardButton("📝 Contenido (Fecha/Texto)", callback_data="editar_contenido")],
        [InlineKeyboardButton("⏳ Aviso Previo", callback_data="editar_aviso")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensaje = get_text("editar_elige_opcion", user_id=user_id_a_editar, texto=texto, fecha=fecha_str)
    await update.message.reply_text(mensaje, parse_mode="Markdown", reply_markup=reply_markup)
    return ELEGIR_OPCION

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
    info = context.user_data.get("editar_info", {})
    chat_id = update.effective_chat.id
    
    aviso_str = update.message.text.strip().lower()
    minutos = parsear_tiempo_a_minutos(aviso_str)

    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return EDITAR_AVISO

    with get_connection() as conn:
        conn.execute("UPDATE recordatorios SET aviso_previo = ? WHERE id = ?", (minutos, info["global_id"]))
        conn.commit()

    cancelar_avisos(str(info["global_id"]))
    
    # Necesitamos la fecha (que está en texto) para reprogramar
    fecha = datetime.fromisoformat(info["fecha_iso"]) if info.get("fecha_iso") else None
    if fecha:
        await programar_avisos(chat_id, str(info["global_id"]), info["user_id"], info["texto"], fecha, minutos)

    # Formateamos el nuevo tiempo para el mensaje de confirmación
    if minutos > 0:
        horas = minutos // 60
        mins = minutos % 60
        tiempo_nuevo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
    else:
        tiempo_nuevo_str = "ninguno"

    mensaje = get_text("editar_confirmacion_aviso", user_id=info["user_id"], aviso_nuevo=tiempo_nuevo_str)
    await update.message.reply_text(mensaje, parse_mode="Markdown")

    context.user_data.clear()
    return ConversationHandler.END

# --- Conversational Handler ---
editar_handler = ConversationHandler(
    entry_points=[CommandHandler("editar", editar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_id)],
        ELEGIR_OPCION: [
            CallbackQueryHandler(pedir_nuevo_recordatorio, pattern="^editar_contenido$"),
            CallbackQueryHandler(pedir_nuevo_aviso, pattern="^editar_aviso$"),
        ],
        EDITAR_RECORDATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_recordatorio)],
        EDITAR_AVISO: [MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_nuevo_aviso)],
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) # <-- Maneja las interrupciones
    ],
)