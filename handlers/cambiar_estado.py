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
from utils import formatear_lista_para_mensaje, parsear_tiempo_a_minutos, manejar_cancelacion
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
            "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone FROM recordatorios WHERE chat_id = ? ORDER BY estado, user_id",
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
        secciones_mensaje.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(chat_id, pendientes)}")
    if pasados:
        secciones_mensaje.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(chat_id, pasados)}")
    if hechos:
        secciones_mensaje.append(f"*{ESTADOS[1]}:*\n{formatear_lista_para_mensaje(chat_id, hechos)}")

    mensaje_final = "*🔄 Lista para Cambiar Estado:*\n\n" + "\n\n".join(secciones_mensaje)
    mensaje_final += "\n\n✏️ Escribe el/los ID que quieras cambiar (separados por espacio y sin #) o /cancelar para salir:"
    
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

    return await manejar_cancelacion(update, context)

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
                    if estado_actual in (1, 2): # Si estaba Hecho o Pasado
                        nuevo_estado = 0 # Pasa a Pendiente
                    elif estado_actual == 0: # Si estaba Pendiente
                        nuevo_estado = 1 # Pasa a Hecho

                    if nuevo_estado != estado_actual:
                        cursor.execute("UPDATE recordatorios SET estado = ? WHERE id = ?", (nuevo_estado, recordatorio_id_global))
                        cambiados_msg.append(f"#{user_id}")

                        if nuevo_estado == 1: # Si pasa a Hecho
                            cancelar_avisos(str(recordatorio_id_global))
                        
                        elif nuevo_estado == 0: # Si se reactiva (pasa a Pendiente)
                            cancelar_avisos(str(recordatorio_id_global)) # Siempre cancelamos el aviso antiguo
                            
                            # --- ¡NUEVA LÓGICA DE VALIDACIÓN DE FECHA! ---
                            if fecha_iso:
                                fecha_dt = datetime.fromisoformat(fecha_iso)
                                # Obtenemos la zona horaria del usuario para una comparación justa
                                user_tz_str = get_config(chat_id, "user_timezone") or 'UTC'
                                user_tz = pytz.timezone(user_tz_str)
                                
                                # Comparamos la fecha del recordatorio con la hora actual en la zona del usuario
                                if fecha_dt > datetime.now(tz=user_tz):
                                    # La fecha es en el futuro: ¡podemos reprogramar!
                                    reprogramados_info.append({
                                        "user_id": user_id,
                                        "global_id": recordatorio_id_global,
                                        "texto": texto,
                                        "fecha": fecha_dt
                                    })
                                else:
                                    # La fecha ya ha pasado: no tiene sentido reprogramar
                                    pasados_sin_aviso_msg.append(f"`#{user_id}`")
                            # Si no hay fecha_iso, no se hace nada, lo cual es correcto.
                            # --------------------------------------------------

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
            f"tiene(n) una fecha que ya ha pasado. Se han marcado como pendientes, pero no se pueden programar nuevos avisos para ellos."
        )
        await update.message.reply_text(mensaje_pasados)

    # 3. Iniciar la conversación para reprogramar solo si hay recordatorios futuros
    if reprogramados_info:
        context.user_data["reprogramar_lista"] = reprogramados_info
        primer_recordatorio = reprogramados_info[0]
        # ... (código para preguntar por el nuevo aviso, sin cambios)
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
    fallbacks=[
        CommandHandler("cancelar", manejar_cancelacion)
    ]
)