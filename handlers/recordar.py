# handlers/recordar.py
"""
Módulo para el comando /recordar.

Gestiona una conversación de dos pasos para crear un nuevo recordatorio:
1.  Pide y procesa la fecha y el texto del recordatorio.
2.  Pide y procesa un tiempo de aviso previo opcional.
Soporta un modo rápido donde toda la información se puede dar en el comando inicial.
"""

import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from db import get_connection, get_config, add_recordatorio_fijo
from utils import parsear_recordatorio, parsear_tiempo_a_minutos, cancelar_conversacion, convertir_utc_a_local, comando_inesperado
from avisos import programar_avisos, programar_recordatorio_fijo_diario
from personalidad import get_text

# --- DEFINICIÓN DE ESTADOS ---
FECHA_TEXTO, AVISO_PREVIO , PEDIR_DATOS_FIJOS = range(3)


# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

# SECCIÓN 1: PUNTO DE ENTRADA Y DESPACHADOR
# =============================================================================

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada unificado para /recordar.
    Actúa como despachador para iniciar el flujo correcto.
    """
    args = context.args
    
    # CASO 1: El usuario quiere un recordatorio FIJO
    if args and args[0].lower() in ["fijo", "fijos"]:
        await update.message.reply_text(
            "👵 Vas a fijar un recordatorio que se repetirá todos los días.\n\n"
            "Por favor, dime la hora y el texto con el formato `HH:MM * Texto del recordatorio`.\n\n"
            "Ejemplo: `08:30 * Tomar la poción multijugos`"
        )
        return PEDIR_DATOS_FIJOS

    # CASO 2: El usuario quiere un recordatorio normal en MODO RÁPIDO
    elif args:
        entrada = " ".join(args)
        return await _procesar_fecha_texto(update, context, entrada)
        
    # CASO 3: El usuario quiere un recordatorio normal en MODO INTERACTIVO
    else:
        await update.message.reply_text(get_text("recordar_pide_fecha"), parse_mode="Markdown")
        return FECHA_TEXTO


# SECCIÓN 2: LÓGICA DEL RECORDATORIO NORMAL
# =============================================================================

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

            # --- LÓGICA DE ID ---
            # CAMBIOS PostgreSQL: %s en lugar de ?, COALESCE en lugar de IFNULL, uso de RETURNING id.
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
        return ConversationHandler.END
    
    # Validación 2: El recordatorio DEBE tener fecha para programar CUALQUIER COSA.
    if not info.get("fecha"):
        await update.message.reply_text(get_text("error_aviso_sin_fecha"))
        # Si no hay fecha, no se puede programar ni el principal ni el previo.
        return AVISO_PREVIO
    
    # --- CAMBIO FUNDAMENTAL: PROGRAMAMOS PRIMERO --- ###
    # Llamamos a programar_avisos SIEMPRE. Esta función se encargará de
    # programar el job principal, y el previo SOLO SI minutos > 0.
    se_programo_aviso_previo = await programar_avisos(
        update.effective_chat.id, str(info["global_id"]), info["user_id"], 
        info["texto"], info["fecha"], minutos
    )

    # --- AHORA, MANEJAMOS LOS DIFERENTES CASOS --- ###

    # Caso 1: El usuario pidió un aviso (minutos > 0)
    if minutos > 0:
        if se_programo_aviso_previo:
            # Éxito total: El aviso previo se programó. Guardamos en la DB y confirmamos.
            with get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (minutos, info["global_id"]))
            
            horas, mins = divmod(minutos, 60)
            tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            mensaje_confirmacion = get_text("aviso_programado", tiempo=tiempo_str)
            await update.message.reply_text(mensaje_confirmacion)
        else:
            # Fallo: El aviso previo estaba en el pasado. Informamos y pedimos reintentar.
            await update.message.reply_text(get_text("error_aviso_pasado_reintentar"))
            return AVISO_PREVIO # Mantenemos al usuario en este paso.
    
    # Caso 2: El usuario NO quería aviso (minutos == 0)
    else: # Esto es equivalente a 'if minutos == 0:'
        # El recordatorio principal YA se ha programado. Simplemente informamos.
        await update.message.reply_text(get_text("aviso_no_programado"))
        # No hace falta tocar la DB porque 'aviso_previo' ya es 0.

    # --- LIMPIEZA Y FINALIZACIÓN --- ###
    # Si llegamos aquí, significa que el flujo ha sido exitoso.
    context.user_data.clear()
    return ConversationHandler.END


# SECCIÓN 3: LÓGICA DEL RECORDATORIO FIJO
# =============================================================================

async def recibir_datos_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la entrada del usuario, guarda y programa el recordatorio fijo."""
    chat_id = update.effective_chat.id
    entrada = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ ¡Formato incorrecto! Recuerda usar `HH:MM * Texto`.")
        return PEDIR_DATOS_FIJOS
    hora_str, texto = match.groups()
    try:
        from datetime import datetime
        datetime.strptime(hora_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(f"❗ La hora '{hora_str}' no es válida. ¡Inténtalo de nuevo!")
        return PEDIR_DATOS_FIJOS
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    fijo_id = add_recordatorio_fijo(chat_id, texto, hora_str, user_tz)
    hora, minuto = map(int, hora_str.split(':'))
    programar_recordatorio_fijo_diario(chat_id, fijo_id, texto, hora, minuto, user_tz)
    await update.message.reply_text(
        f"✅ ¡Entendido! He fijado un recordatorio diario para las *{hora_str}* con el texto: _{texto}_",
        parse_mode="Markdown"
    )
    return ConversationHandler.END



# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd)],
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)],
        AVISO_PREVIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso_previo)],

        PEDIR_DATOS_FIJOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_datos_fijos)],
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)