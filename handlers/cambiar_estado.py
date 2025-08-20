from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from datetime import datetime
from db import get_connection, get_config, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje, parsear_tiempo_a_minutos, cancelar_conversacion
from avisos import cancelar_avisos, programar_avisos
from config import ESTADOS
from personalidad import get_text

# Estados de la conversación (no cambian)
ELEGIR_ID, CONFIRMAR_CAMBIO, REPROGRAMAR_AVISO = range(3)

async def cambiar_estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para /cambiar. Filtra y muestra solo los recordatorios del usuario.
    """
    actualizar_recordatorios_pasados()
    chat_id = update.effective_chat.id  # <-- Obtenemos el ID del usuario

    if context.args:
        # Modo rápido: el usuario ya ha proporcionado los IDs
        return await _procesar_ids_para_cambiar(update, context, context.args)
        
    # Modo interactivo: mostramos la lista.
    chat_id = update.effective_chat.id
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo FROM recordatorios WHERE chat_id = ? ORDER BY estado, user_id",
            (chat_id,)
        )
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios para cambiar.")
        return ConversationHandler.END

    pendientes = [r for r in recordatorios if r[5] == 0]
    hechos = [r for r in recordatorios if r[5] == 1]
    pasados = [r for r in recordatorios if r[5] == 2]

    secciones_mensaje = []
    if pendientes:
        secciones_mensaje.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(pendientes)}")
    if pasados:
        secciones_mensaje.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(pasados)}")
    if hechos:
        secciones_mensaje.append(f"*{ESTADOS[1]}:*\n{formatear_lista_para_mensaje(hechos)}")

    mensaje_final = "*🔄 Lista para Cambiar Estado:*\n\n" + "\n\n".join(secciones_mensaje)
    mensaje_final += "\n\n✏️ Escribe el/los ID que quieras cambiar de estado o /cancelar para salir:"
    
    await update.message.reply_text(mensaje_final, parse_mode="Markdown")
    return ELEGIR_ID

async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe los IDs después de que el usuario vea la lista."""
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID
    
    return await _procesar_ids_para_cambiar(update, context, ids)

async def _procesar_ids_para_cambiar(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list):
    """Función centralizada que decide si pedir confirmación."""
    chat_id = update.effective_chat.id
    context.user_data["ids_a_cambiar"] = ids
    
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (2, 3):
        mensaje_confirmacion = get_text("pregunta_confirmar_cambio", count=len(ids))
        await update.message.reply_text(mensaje_confirmacion)
        return CONFIRMAR_CAMBIO
    
    return await ejecutar_cambio(update, context)

async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se activa después de que el usuario escribe 'SI'."""
    if update.message.text.strip().upper() == "SI":
        return await ejecutar_cambio(update, context)
    
    return await cancelar_conversacion(update, context)

async def ejecutar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Ejecuta el cambio de estado. Si un recordatorio se reactiva,
    en lugar de programar el aviso, preguntará al usuario.
    """
    chat_id = update.effective_chat.id
    ids_a_cambiar = context.user_data.get("ids_a_cambiar", [])
    cambiados = []
    reprogramados_info = []

    with get_connection() as conn:
        cursor = conn.cursor()
        for user_id_str in ids_a_cambiar:
            try:
                user_id = int(user_id_str.replace("#", ""))
                cursor.execute(
                    "SELECT id, estado, texto, fecha_hora, aviso_previo FROM recordatorios WHERE user_id = ? AND chat_id = ?",
                    (user_id, chat_id)
                )
                row = cursor.fetchone()

                if row:
                    recordatorio_id_global, estado_actual, texto, fecha_iso, aviso_previo = row
                    
                    nuevo_estado = estado_actual
                    if estado_actual in (1, 2): # Si estaba Hecho o Pasado
                        nuevo_estado = 0 # Pasa a Pendiente
                    elif estado_actual == 0: # Si estaba Pendiente
                        nuevo_estado = 1 # Pasa a Hecho

                    if nuevo_estado != estado_actual:
                        cursor.execute("UPDATE recordatorios SET estado = ? WHERE id = ?", (nuevo_estado, recordatorio_id_global))
                        cambiados.append(f"#{user_id}")

                        if nuevo_estado == 1: # Si pasa a Hecho
                            cancelar_avisos(str(recordatorio_id_global))
                        elif nuevo_estado == 0: # Si se reactiva
                            cancelar_avisos(str(recordatorio_id_global)) # Cancelamos cualquier aviso antiguo
                            if fecha_iso: # Solo si tiene fecha podemos reprogramar
                                reprogramados_info.append({
                                    "user_id": user_id,
                                    "global_id": recordatorio_id_global,
                                    "texto": texto,
                                    "fecha": datetime.fromisoformat(fecha_iso)
                                })
            except (ValueError, TypeError):
                pass
        conn.commit()

    mensaje = get_text("confirmacion_cambio", ids=', '.join(cambiados)) if cambiados else get_text("error_no_id") # <-- CAMBIO
    await update.message.reply_text(mensaje)

    if reprogramados_info:
        context.user_data["reprogramar_lista"] = reprogramados_info
        primer_recordatorio = reprogramados_info[0]
        
        # <-- CAMBIO: Usamos la personalidad
        mensaje_reprogramar = (
            f"🗓️ Has reactivado el recordatorio `#{primer_recordatorio['user_id']}` - _{primer_recordatorio['texto']}_.\n\n"
            f"{get_text('recordar_pide_aviso')}"
        )
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
        conn.execute("UPDATE recordatorios SET aviso_previo = ? WHERE id = ?", (minutos, recordatorio_actual["global_id"]))
        conn.commit()

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

cambiar_estado_handler = ConversationHandler(
    entry_points=[CommandHandler("cambiar", cambiar_estado_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR_CAMBIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_cambio)],
        REPROGRAMAR_AVISO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nuevo_aviso)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
)