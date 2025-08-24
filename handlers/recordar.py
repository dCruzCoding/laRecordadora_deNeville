from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from utils import parsear_recordatorio, parsear_tiempo_a_minutos, manejar_cancelacion, convertir_utc_a_local
from db import get_connection, get_config
from avisos import programar_avisos
from personalidad import get_text

# Estados de la conversación
FECHA_TEXTO, AVISO_PREVIO = range(2)

async def recordar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /recordar."""
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
    """Recibe la fecha y el texto del usuario."""
    entrada = update.message.text
    return await _procesar_fecha_texto(update, context, entrada)

async def _procesar_fecha_texto(update: Update, context: ContextTypes.DEFAULT_TYPE, entrada: str):
    """
    Función centralizada para procesar el recordatorio, guardarlo y pedir el aviso.
    AHORA CON SOPORTE PARA ZONA HORARIA.
    """
    chat_id = update.effective_chat.id # Movemos esto al principio para usarlo ya

    # --- ¡CAMBIO 1: Obtener la zona horaria del usuario! ---
    # Leemos la zona horaria guardada en la DB. Si no existe, usamos 'UTC' como valor por defecto seguro.
    user_tz = get_config(chat_id, "user_timezone") or 'UTC'

    # --- ¡CAMBIO 2: Usar la zona horaria al parsear! ---
    # Ahora le pasamos la zona horaria del usuario a la función de parseo.
    texto, fecha, error = parsear_recordatorio(entrada, user_timezone=user_tz)

    if error:
        await update.message.reply_text(get_text("error_formato"))
        return FECHA_TEXTO if not context.args else ConversationHandler.END

    # --- NUEVO FLUJO ---
    fecha_iso = fecha.isoformat() if fecha else None
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(user_id) FROM recordatorios WHERE chat_id = ?", (chat_id,))
        ultimo_id = cursor.fetchone()[0]
        nuevo_user_id = (ultimo_id or 0) + 1

        cursor.execute(
            """INSERT INTO recordatorios (user_id, chat_id, texto, fecha_hora, estado, aviso_previo) 
               VALUES (?, ?, ?, ?, 0, 0)""",
            (nuevo_user_id, chat_id, texto, fecha_iso)
        )
        recordatorio_id_global = cursor.lastrowid
        conn.commit()

    context.user_data["recordatorio_info"] = {
        "global_id": recordatorio_id_global,
        "user_id": nuevo_user_id,
        "texto": texto,
        "fecha": fecha
    }

    fecha_local_para_mostrar = convertir_utc_a_local(fecha, user_tz)

    fecha_str = fecha_local_para_mostrar.strftime("%d %b %Y, %H:%M") if fecha_local_para_mostrar else "Sin fecha"
    mensaje_guardado = get_text("recordatorio_guardado", id=nuevo_user_id, texto=texto, fecha=fecha_str)
    await update.message.reply_text(mensaje_guardado, parse_mode="Markdown")

    await update.message.reply_text(get_text("recordar_pide_aviso"), parse_mode="Markdown")
    return AVISO_PREVIO


async def recibir_aviso_previo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Recibe el tiempo de aviso previo, actualiza el recordatorio en la DB,
    y programa el aviso final.
    """
    aviso_str = update.message.text.strip().lower()
    minutos = parsear_tiempo_a_minutos(aviso_str)

    if minutos is None:
        await update.message.reply_text(get_text("error_aviso_invalido"))
        return AVISO_PREVIO

    # Recuperamos la información del recordatorio que guardamos en el paso anterior
    info = context.user_data.get("recordatorio_info")
    if not info:
        # Esto no debería pasar, pero es una salvaguarda
        await update.message.reply_text("¡Uy! Se me ha ido el santo al cielo. ¿Podemos empezar de nuevo? Usa /recordar.")
        return ConversationHandler.END

    # Actualizamos el recordatorio en la base de datos con el valor de aviso_previo
    with get_connection() as conn:
        conn.execute("UPDATE recordatorios SET aviso_previo = ? WHERE id = ?", (minutos, info["global_id"]))
        conn.commit()

    # Programamos el aviso con la información completa
    if info.get("fecha"): # Solo programamos si hay fecha
        await programar_avisos(
            update.effective_chat.id, 
            str(info["global_id"]), 
            info["user_id"], 
            info["texto"], 
            info["fecha"], 
            minutos
        )

    # Enviamos la confirmación final sobre el aviso
    if minutos > 0:
        horas = minutos // 60
        mins = minutos % 60
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        mensaje_aviso = get_text("aviso_programado", tiempo=tiempo_str)
    else:
        mensaje_aviso = get_text("aviso_no_programado")

    await update.message.reply_text(mensaje_aviso)
    
    context.user_data.clear()
    return ConversationHandler.END


# Conversational handler para registrar en main.py
recordar_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar", recordar_cmd)],
    states={
        FECHA_TEXTO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_fecha_texto)],
        AVISO_PREVIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_aviso_previo)]
    },
    fallbacks=[
        CommandHandler("cancelar", manejar_cancelacion)
    ]
)