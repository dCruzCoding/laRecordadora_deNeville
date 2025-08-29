from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from datetime import datetime
from db import get_connection, get_config
from utils import parsear_tiempo_a_minutos, cancelar_conversacion, comando_inesperado, construir_mensaje_lista_completa
from avisos import cancelar_avisos, programar_avisos
from config import ESTADOS
from personalidad import get_text
import pytz

# Estados de la conversación (no cambian)
ELEGIR_ID, CONFIRMAR_CAMBIO, REPROGRAMAR_AVISO = range(3)

async def cambiar_estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para /cambiar. Filtra y muestra solo los recordatorios del usuario.
    """
    chat_id = update.effective_chat.id  # <-- Obtenemos el ID del usuario

    if context.args:
        # Modo rápido: el usuario ya ha proporcionado los IDs
        return await _procesar_ids_para_cambiar(update, context, context.args)
        
    # Modo interactivo: mostramos la lista.
    chat_id = update.effective_chat.id
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone FROM recordatorios WHERE chat_id = ? ORDER BY estado, user_id",
            (chat_id,)
        )
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios para cambiar.")
        return ConversationHandler.END

    mensaje_lista = construir_mensaje_lista_completa(chat_id, recordatorios, titulo_general="🔄 Recordatorios para Cambiar estado 🔄\n")
    mensaje_final = mensaje_lista + "\n\n\n✏️ Escribe el/los ID que quieras cambiar (separados por espacio y sin #) o /cancelar para salir:"
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
    """
    Función centralizada. Ahora busca los detalles de los recordatorios
    y los muestra en la pregunta de confirmación.
    """
    chat_id = update.effective_chat.id
    recordatorios_a_cambiar_info = []

    # --- ¡NUEVA LÓGICA DE BÚSQUEDA! ---
    with get_connection() as conn:
        cursor = conn.cursor()
        for user_id_str in ids:
            try:
                user_id = int(user_id_str.replace("#", ""))
                # Obtenemos también el estado actual para mostrarlo
                cursor.execute(
                    "SELECT user_id, texto, fecha_hora, estado FROM recordatorios WHERE user_id = ? AND chat_id = ?",
                    (user_id, chat_id)
                )
                row = cursor.fetchone()
                if row:
                    recordatorios_a_cambiar_info.append(row)
            except (ValueError, TypeError):
                pass

    if not recordatorios_a_cambiar_info:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    context.user_data["ids_a_cambiar"] = [str(r[0]) for r in recordatorios_a_cambiar_info]
    context.user_data["info_a_cambiar"] = recordatorios_a_cambiar_info
    
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (2, 3):
        # --- MENSAJE DE CONFIRMACIÓN MEJORADO ---
        mensaje_lista = []
        for user_id, texto, fecha_iso, estado_actual in recordatorios_a_cambiar_info:
            estado_viejo_str = ESTADOS.get(estado_actual, "")
            estado_nuevo_str = ESTADOS.get(0 if estado_actual in (1, 2) else 1, "")
            mensaje_lista.append(f"  - `#{user_id}`: _{texto}_ (Pasará de {estado_viejo_str} a {estado_nuevo_str})")
            
        mensaje_confirmacion = (
            f"👵 ¿Estás seguro de que quieres cambiar el estado de lo siguiente?:\n\n"
            f"{'\n'.join(mensaje_lista)}\n\n"
            "Responde `SI` para confirmar."
        )
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRMAR_CAMBIO
    
    return await ejecutar_cambio(update, context)

async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se activa después de que el usuario escribe 'SI'."""
    if update.message.text.strip().upper() == "SI":
        return await ejecutar_cambio(update, context)

    return await cancelar_conversacion(update, context)

async def ejecutar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lógica final de cambio de estado con la nueva validación de fecha."""
    chat_id = update.effective_chat.id
    ids_a_cambiar = context.user_data.get("ids_a_cambiar", [])
    cambiados_msg = []
    reprogramados_info = []
    pasados_sin_aviso_msg = [] # <-- Lista para los recordatorios reactivados pero pasados

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
                    if estado_actual in (1, 2): nuevo_estado = 0
                    elif estado_actual == 0: nuevo_estado = 1

                    if nuevo_estado != estado_actual:
                        cursor.execute("UPDATE recordatorios SET estado = ? WHERE id = ?", (nuevo_estado, recordatorio_id_global))
                        cambiados_msg.append(f"#{user_id}")

                        # --- LÓGICA DE AVISOS REFINADA ---
                        if nuevo_estado == 1:
                            # 1. Si pasa a HECHO (desde Pendiente o Pasado)
                            #    Simplemente cancelamos cualquier aviso. No se necesita mensaje.
                            cancelar_avisos(str(recordatorio_id_global))
                        
                        elif nuevo_estado == 0: # Si se reactiva (pasa a PENDIENTE)
                            cancelar_avisos(str(recordatorio_id_global))
                            
                            if fecha_iso:
                                fecha_dt = datetime.fromisoformat(fecha_iso)
                                user_tz_str = get_config(chat_id, "user_timezone") or 'UTC'
                                user_tz = pytz.timezone(user_tz_str)
                                
                                if fecha_dt > datetime.now(tz=user_tz):
                                    # 2. La fecha es futura: procedemos a reprogramar.
                                    reprogramados_info.append({ ... })
                                else:
                                    # 3. La fecha es pasada: ¡AQUÍ MOSTRAMOS LA ADVERTENCIA!
                                    pasados_sin_aviso_msg.append(f"`#{user_id}`")
                            # Si no hay fecha, no hacemos nada.

            except (ValueError, TypeError):
                pass
        conn.commit()

        # --- MENSAJES DE CONFIRMACIÓN MEJORADOS ---
    
    # 1. Mensaje principal sobre los estados cambiados (siempre se muestra si hay cambios)
    if cambiados_msg:
        info_cambiada = context.user_data.get("info_a_cambiar", [])
        
        if len(info_cambiada) == 1:
            recordatorio = info_cambiada[0]
            mensaje_exito = f"🔄 ¡Listo! El estado del recordatorio `#{recordatorio[0]}` ('_{recordatorio[1]}_') ha sido actualizado."
        else:
            nombres_cambiados = [f"`#{r[0]}`" for r in info_cambiada]
            mensaje_exito = f"🔄 ¡Hecho! Se ha actualizado el estado de los recordatorios {', '.join(nombres_cambiados)}."
            
        await update.message.reply_text(mensaje_exito, parse_mode="Markdown")
    else:
        await update.message.reply_text(get_text("error_no_id"))

    # 2. Mensaje adicional si algún recordatorio reactivado ya estaba pasado
    if pasados_sin_aviso_msg:
        mensaje_pasados = (
            f"⚠️ Nota: El/los recordatorio(s) {', '.join(pasados_sin_aviso_msg)} que has reactivado "
            f"tiene(n) una fecha que ya ha *pasado*. Por tanto, no se pueden añadir nuevos avisos."
        )
        await update.message.reply_text(mensaje_pasados, parse_mode="Markdown")

    # 3. Iniciar la conversación para reprogramar solo si hay recordatorios futuros
    if reprogramados_info:
        # Guardamos la lista de recordatorios a reprogramar en el contexto para los siguientes pasos
        context.user_data["reprogramar_lista"] = reprogramados_info
        
        # Sacamos el primer recordatorio de la lista para preguntar por él
        primer_recordatorio = reprogramados_info[0]
        
        # Construimos el mensaje usando la personalidad del bot
        mensaje_reprogramar = (
            f"🗓️ Has reactivado el recordatorio `#{primer_recordatorio['user_id']}` - _{primer_recordatorio['texto']}_.\n\n"
            f"{get_text('recordar_pide_aviso')}"
        )
        
        await update.message.reply_text(
            mensaje_reprogramar,
            parse_mode="Markdown"
        )
        
        # Le decimos al ConversationHandler que pase al estado de esperar el nuevo aviso
        return REPROGRAMAR_AVISO
    
    # Si no hay nada que reprogramar, limpiamos y terminamos.
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
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) # <-- Maneja las interrupciones
    ],
)