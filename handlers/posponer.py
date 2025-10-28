# handlers/posponer.py
"""
Módulo para gestionar las interacciones con los botones de las notificaciones.

Este handler no forma parte de ninguna conversación. Es un CallbackQueryHandler
de nivel superior que reacciona a las pulsaciones de los botones que se envían
junto con los avisos de recordatorio (principal y previo).
"""

from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
import pytz

from db import get_connection, get_config
from avisos import cancelar_avisos, programar_avisos


# =============================================================================
# FUNCIÓN PRINCIPAL DEL HANDLER
# =============================================================================
async def handle_posponer_or_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja las acciones de los botones de notificación: 'Hecho', 'Posponer' y 'OK'.
    """
    query = update.callback_query
    await query.answer()

    # --- 1. Parseo seguro del callback_data ---
    # Formatos posibles: "accion:rid" (ej: "ok:123") o "accion:valor:rid" (ej: "posponer:10:123")
    parts = query.data.split(":")
    action = parts[0]
    rid = parts[-1] # El ID del recordatorio siempre es la última parte.

    # --- 2. Obtención de datos y validaciones iniciales ---
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Placeholder >> %s
            cursor.execute(
                "SELECT user_id, texto, estado, fecha_hora, aviso_previo FROM recordatorios WHERE id = %s", (rid,)
            )
            recordatorio_data = cursor.fetchone()

    if not recordatorio_data:
        await query.edit_message_text(text="👵 Vaya, parece que este recordatorio ya no existe.")
        return

    user_id, texto, estado_actual, fecha_recordatorio_utc, aviso_previo_actual = recordatorio_data

    # Si el recordatorio ya estaba marcado como "Hecho", informamos y no hacemos nada más.
    if estado_actual == 1:
        await query.edit_message_text(text=f"✅ _{texto}_ \n\n(Este recordatorio ya estaba marcado como hecho).", parse_mode="Markdown")
        return

    # --- 3. Lógica específica para cada acción ---

    if action == "mark_done":   # Acción: Marcar como Hecho.
        with get_connection() as conn:
            conn.cursor().execute("UPDATE recordatorios SET estado = 1, aviso_previo = 0 WHERE id = %s", (rid,))
        cancelar_avisos(rid) # Cancelamos cualquier job futuro que pudiera quedar.
        await query.edit_message_text(text=f"✅ ¡Bien hecho! Has completado: _{texto}_", parse_mode="Markdown")

    elif action == "posponer":  # Acción: Posponer. Se pospone el aviso 10min.
        # Validación: No se puede posponer si no hay una fecha final.
        if not fecha_recordatorio_utc:
            await query.edit_message_text(text="👵 ¡Criatura! No puedes posponer un recordatorio que no tiene una hora final establecida.")
            return
        
        minutos_posponer = int(parts[1])
        nueva_hora_aviso_utc = datetime.now(pytz.utc) + timedelta(minutes=minutos_posponer)

        # Validación: La nueva hora del aviso no puede superar la hora del recordatorio.
        if nueva_hora_aviso_utc >= fecha_recordatorio_utc:
            await query.edit_message_text(text=f"⏰ No se puede posponer más. La siguiente notificación sería después de la hora límite del recordatorio.", parse_mode="Markdown")
            # Dejamos la notificación original, pero sin el botón de posponer.
            return
        
        # Calculamos el tiempo restante para mostrarlo en el nuevo aviso.
        diferencia = fecha_recordatorio_utc - nueva_hora_aviso_utc
        nuevo_aviso_previo_min = round(diferencia.total_seconds() / 60)

        # Reprogramamos el aviso con la nueva antelación.
        #  Llamamos a 'programar_avisos', que es la función principal y robusta.
        await programar_avisos(
            query.message.chat_id,
            rid,
            user_id,
            texto,
            fecha_recordatorio_utc,
            nuevo_aviso_previo_min,
            es_pospuesto=True
        )

        # Guardamos el nuevo valor de 'aviso_previo' en la base de datos.
        with get_connection() as conn:
            conn.cursor().execute("UPDATE recordatorios SET aviso_previo = %s WHERE id = %s", (nuevo_aviso_previo_min, rid))

        # Confirmamos al usuario.
        user_tz_str = get_config(query.message.chat_id, "user_timezone") or 'UTC'
        try: user_tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError: user_tz = pytz.utc
        
        nueva_hora_aviso_local = nueva_hora_aviso_utc.astimezone(user_tz)
        hora_local_str = nueva_hora_aviso_local.strftime('%H:%M')
        
        await query.edit_message_text(
            text=f"⏰ ¡Entendido! Te lo volveré a recordar a las *{hora_local_str}*.",
            parse_mode="Markdown"
        )

    elif action == "ok":
        # Acción: Descartar la notificación.
        with get_connection() as conn:
            # Reseteamos el aviso_previo a 0 para que no aparezca en /lista.
            conn.cursor().execute("UPDATE recordatorios SET aviso_previo = 0 WHERE id = %s", (rid,))
                    
        # Cancelamos el aviso principal si aún estaba programado.
        cancelar_avisos(rid)
        
        # Editamos el mensaje para quitar los botones, manteniendo el texto original.
        await query.edit_message_text(text=query.message.text, reply_markup=None, parse_mode="Markdown")



# =============================================================================
# DEFINICIÓN DEL HANDLER
# =============================================================================
# Este handler escucha por todos los patrones de callback que pueden llegar
# desde una notificación de aviso.
posponer_handler = CallbackQueryHandler(handle_posponer_or_done, pattern=r"^(posponer|mark_done|ok):")