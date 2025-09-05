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
from avisos import cancelar_avisos, programar_avisos, scheduler, enviar_recordatorio


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
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, texto, estado, fecha_hora, aviso_previo FROM recordatorios WHERE id = ?", (rid,)
        )
        recordatorio_data = cursor.fetchone()

    if not recordatorio_data:
        await query.edit_message_text(text="👵 Vaya, parece que este recordatorio ya no existe.")
        return

    user_id, texto, estado_actual, fecha_hora_iso, aviso_previo_actual = recordatorio_data

    # Si el recordatorio ya estaba marcado como "Hecho", informamos y no hacemos nada más.
    if estado_actual == 1:
        await query.edit_message_text(text=f"✅ _{texto}_ \n\n(Este recordatorio ya estaba marcado como hecho).", parse_mode="Markdown")
        return

    # --- 3. Lógica específica para cada acción ---

    if action == "mark_done":
        # Acción: Marcar como Hecho.
        with get_connection() as conn:
            # Cambiamos el estado a 1 (Hecho) y reseteamos el aviso_previo a 0.
            conn.execute("UPDATE recordatorios SET estado = 1, aviso_previo = 0 WHERE id = ?", (rid,))
            conn.commit()
        cancelar_avisos(rid) # Cancelamos cualquier job futuro que pudiera quedar.
        await query.edit_message_text(text=f"✅ ¡Bien hecho! Has completado: _{texto}_", parse_mode="Markdown")

    elif action == "posponer":
        # Acción: Posponer. Se pospone el aviso 10min.
        minutos_posponer = int(parts[1])
        # Calculamos la nueva hora del aviso (ahora + los minutos a posponer).
        nueva_hora_aviso_utc = datetime.now(pytz.utc) + timedelta(minutes=minutos_posponer)

        #  Programamos un único job de tipo 'enviar_recordatorio' para la nueva hora.
        scheduler.add_job(
            enviar_recordatorio, # Reutilizamos la función del aviso principal
            'date',
            run_date=nueva_hora_aviso_utc,
            # Le damos un ID único al job de snooze para evitar colisiones.
            id=f"snooze_{rid}_{datetime.now().timestamp()}", 
            args=[update.effective_chat.id, user_id, texto, rid],
            misfire_grace_time=60
        )

        # Confirmamos al usuario con la hora del PRÓXIMO AVISO.
        user_tz_str = get_config(update.effective_chat.id, "user_timezone") or 'UTC'
        try:
            user_tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError:
            user_tz = pytz.utc
            
        nueva_hora_aviso_local = nueva_hora_aviso_utc.astimezone(user_tz)
        hora_local_str = nueva_hora_aviso_local.strftime('%H:%M')
        
        await query.edit_message_text(
            text=f"⏰ ¡Entendido! Te lo volveré a recordar a las *{hora_local_str}*.\n\nLa tarea sigue programada para su hora original.",
            parse_mode="Markdown"
        )

    elif action == "ok":
        # Acción: Descartar la notificación.
        with get_connection() as conn:
            # Reseteamos el aviso_previo a 0 para que no aparezca en /lista.
            conn.execute("UPDATE recordatorios SET aviso_previo = 0 WHERE id = ?", (rid,))
            conn.commit()
        
        # Cancelamos el aviso principal si aún estaba programado.
        cancelar_avisos(rid)
        
        # Editamos el mensaje para quitar los botones, manteniendo el texto original.
        await query.edit_message_text(text=query.message.text, parse_mode="Markdown")



# =============================================================================
# DEFINICIÓN DEL HANDLER
# =============================================================================
# Este handler escucha por todos los patrones de callback que pueden llegar
# desde una notificación de aviso.
posponer_handler = CallbackQueryHandler(handle_posponer_or_done, pattern=r"^(posponer|mark_done|ok):")