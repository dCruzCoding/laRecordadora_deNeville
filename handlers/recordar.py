# handlers/recordar.py
"""
Módulo para el comando /recordar.

Gestiona una conversación de dos pasos para crear un nuevo recordatorio:
1.  Pide y procesa la fecha y el texto del recordatorio.
2.  Pide y procesa un tiempo de aviso previo opcional.
Soporta un modo rápido donde toda la información se puede dar en el comando inicial.
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from db import get_connection, get_config
from utils import parsear_recordatorio, parsear_tiempo_a_minutos, cancelar_conversacion, convertir_utc_a_local, comando_inesperado
from avisos import programar_avisos
from personalidad import get_text

# --- DEFINICIÓN DE ESTADOS ---
FECHA_TEXTO, AVISO_PREVIO = range(2)


# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /recordar. Dirige al modo rápido o interactivo"""
    if context.args:
        # Modo rápido: si ya se da la info, se salta el primer paso
        entrada = " ".join(context.args)
        # Delegamos a la misma función que el modo interactivo para no duplicar código
        return await _procesar_fecha_texto(update, context, entrada)
    else:
        # Modo interactivo
        await update.message.reply_text(get_text("recordar_pide_fecha"), parse_mode="Markdown")
        return FECHA_TEXTO

async def recibir_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la fecha y el texto del usuario en el modo interactivo."""
    entrada = update.message.text
    return await _procesar_fecha_texto(update, context, entrada)

async def _procesar_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE, entrada: str):
    """
    Función central del primer paso: parsea, valida y guarda el recordatorio inicial en la DB.
    """
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'

    # 1. Parsear la entrada del usuario.
    texto, fecha, error = parsear_recordatorio(entrada, user_timezone=user_tz)

    if error:
        await update.message.reply_text(error)
        # Si estamos en modo rápido y falla el parseo, terminamos. Si no, pedimos reintentar.
        return FECHA_TEXTO if not context.args else ConversationHandler.END
    
    # 2. Validación extra: no permitir recordatorios con texto vacío.
    if not texto:
        await update.message.reply_text("👵 ¡Criatura, no puedes crear un recordatorio sin nada que recordar! Inténtalo de nuevo.")
        return FECHA_TEXTO if not context.args else ConversationHandler.END

    # 3. Guardar en la base de datos y obtener IDs.
    fecha_iso = fecha.isoformat() if fecha else None
    with get_connection() as conn:
        with conn.cursor() as cursor:
            
            # --- LÓGICA DE ID OPTIMIZADA ---
            # CAMBIO 1: PostgreSQL usa %s en lugar de ?.
            # CAMBIO 2: IFNULL (SQLite) se reemplaza por COALESCE (SQL estándar).
            # CAMBIO 3: Para obtener el ID insertado en PostgreSQL, usamos 'RETURNING id'.
            cursor.execute(
                """INSERT INTO recordatorios (user_id, chat_id, texto, fecha_hora, aviso_previo, timezone) 
                   VALUES ((SELECT COALESCE(MAX(user_id), 0) + 1 FROM recordatorios WHERE chat_id = %s), %s, %s, %s, 0, %s)
                   RETURNING id, user_id""",
                (chat_id, chat_id, texto, fecha_iso, user_tz)
            )
            # Obtenemos los IDs directamente del resultado de la inserción
            recordatorio_id_global, nuevo_user_id = cursor.fetchone()

    # 4. Guardar información para el siguiente paso y confirmar al usuario.
    context.user_data["recordatorio_info"] = {
        "global_id": recordatorio_id_global, "user_id": nuevo_user_id,
        "texto": texto, "fecha": fecha
    }

    fecha_local = convertir_utc_a_local(fecha, user_tz)
    fecha_str = fecha_local.strftime("%d %b, %H:%M") if fecha_local else "Sin fecha"
    mensaje_guardado = get_text("recordatorio_guardado", id=nuevo_user_id, texto=texto, fecha=fecha_str)
    
    await update.message.reply_text(mensaje_guardado, parse_mode="Markdown")
    await update.message.reply_text(get_text("recordar_pide_aviso"), parse_mode="Markdown")
    
    return AVISO_PREVIO


async def recibir_aviso_previo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Segundo paso: recibe el tiempo de aviso, lo valida, lo guarda y programa los jobs.
    """
    minutos = parsear_tiempo_a_minutos(update.message.text)

    # Validación 1: Formato de tiempo incorrecto.
    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return AVISO_PREVIO # Mantiene al usuario en este paso.

    info = context.user_data.get("recordatorio_info")
    if not info:
        await update.message.reply_text("👵 ¡Uy! Algo se ha perdido. ¿Podemos empezar de nuevo con /recordar?")
        return ConversationHandler.END
    
    # Caso 1: El usuario no quiere aviso.
    if minutos == 0:
        await update.message.reply_text(get_text("aviso_no_programado"))
        # El 'aviso_previo' en la DB ya es 0 por defecto, no hace falta actualizar.
        context.user_data.clear()
        return ConversationHandler.END
    
    # Caso 2: El recordatorio no tiene fecha.
    if not info.get("fecha"):
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        return AVISO_PREVIO
    
    # Caso 3: Intentamos programar el aviso.
    se_programo_aviso = await programar_avisos(
        update.effective_chat.id, str(info["global_id"]), info["user_id"], 
        info["texto"], info["fecha"], minutos
    )

    if se_programo_aviso:
        # Si tiene éxito, guardamos los minutos en la DB y terminamos.
        with get_connection() as conn:
            # CAMBIO: Placeholder a %s
            conn.cursor().execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (minutos, info["global_id"]))
            
        horas, mins = divmod(minutos, 60)
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        mensaje_confirmacion = get_text("aviso_programado", tiempo=tiempo_str)
        
        await update.message.reply_text(mensaje_confirmacion)
        context.user_data.clear()
        return ConversationHandler.END
    else:
        # Si falla (hora pasada), informamos y pedimos reintentar.
        await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
        return AVISO_PREVIO


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd)],
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)],
        AVISO_PREVIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso_previo)]
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)