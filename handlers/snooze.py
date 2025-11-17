# handlers/snooze.py
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
from alerts import cancel_alerts, schedule_alerts


# =============================================================================
# FUNCIÓN PRINCIPAL DEL HANDLER
# =============================================================================
async def handle_snooze_or_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja las acciones de los botones de notificación: 'Hecho', 'Posponer' y 'OK'.
    """
    query = update.callback_query
    await query.answer()

    # --- 1. Parseo seguro del callback_data ---
    # Formatos posibles: "accion:rid" (ej: "ok:123") o "accion:valor:rid" (ej: "snooze:10:123")
    parts = query.data.split(":")
    action = parts[0]
    rid = parts[-1] # El ID del recordatorio siempre es la última parte.

    # --- 2. Obtención de datos y validaciones iniciales ---
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Placeholder >> %s
            cursor.execute(
                "SELECT user_id, text, status, datetime, pre_alert FROM reminders WHERE id = %s", (rid,)
            )
            reminder_data = cursor.fetchone()

    if not reminder_data:
        await query.edit_message_text(text="👵 Vaya, parece que este recordatorio ya no existe.")
        return

    user_id, text, status_current, datetime_reminder_utc, pre_alert_current = reminder_data
    
    # Si el recordatorio ya estaba marcado como "Hecho", informamos y no hacemos nada más.
    if status_current == 1:
        await query.edit_message_text(text=f"✅ _{text}_ \n\n(Este recordatorio ya estaba marcado como hecho).", parse_mode="Markdown")
        return

    # --- 3. Lógica específica para cada acción ---

    if action == "mark_done":   # Acción: Marcar como Hecho.
        with get_connection() as conn:
            conn.cursor().execute("UPDATE reminders SET status = 1, pre_alert = 0 WHERE id = %s", (rid,))
        cancel_alerts(rid) # Cancelamos cualquier job futuro que pudiera quedar.
        await query.edit_message_text(text=f"✅ ¡Bien hecho! Has completado: _{text}_", parse_mode="Markdown")

    elif action == "posponer":  # Acción: Posponer. Se pospone el aviso 10min.
        # Validación: No se puede posponer si no hay una fecha final.
        if not datetime_reminder_utc:
            await query.edit_message_text(text="👵 ¡Criatura! No puedes posponer un recordatorio que no tiene una hora final establecida.")
            return
        
        minutes_snooze = int(parts[1])
        new_alert_time_utc = datetime.now(pytz.utc) + timedelta(minutes=minutes_snooze)

        # Validación: La nueva hora del aviso no puede superar la hora del recordatorio.
        if new_alert_time_utc >= datetime_reminder_utc:
            await query.edit_message_text(text=f"⏰ No se puede posponer más. La siguiente notificación sería después de la hora límite del recordatorio.", parse_mode="Markdown")
            # Dejamos la notificación original, pero sin el botón de posponer.
            return
        
        # Calculamos el tiempo restante para mostrarlo en el nuevo aviso.
        diff = datetime_reminder_utc - new_alert_time_utc
        new_pre_alert_min = round(diff.total_seconds() / 60)

        # Reprogramamos el aviso con la nueva antelación.
        #  Llamamos a 'programar_avisos', que es la función principal y robusta.
        await schedule_alerts(
            query.message.chat_id,
            rid,
            user_id,
            text,
            datetime_reminder_utc,
            new_pre_alert_min,
            is_snooze=True
        )

        # Guardamos el nuevo valor de 'aviso_previo' en la base de datos.
        with get_connection() as conn:
            conn.cursor().execute("UPDATE reminders SET pre_alert = %s WHERE id = %s", (new_pre_alert_min, rid))

        # Confirmamos al usuario.
        user_tz_str = get_config(query.message.chat_id, "user_timezone") or 'UTC'
        try: user_tz = pytz.timezone(user_tz_str)
        except pytz.UnknownTimeZoneError: user_tz = pytz.utc
        
        new_alert_time_local = new_alert_time_utc.astimezone(user_tz)
        time_local_str = new_alert_time_local.strftime('%H:%M')
        
        await query.edit_message_text(
            text=f"⏰ ¡Entendido! Te lo volveré a recordar a las *{time_local_str}*.",
            parse_mode="Markdown"
        )

    elif action == "ok":
        # Acción: Descartar la notificación.
        with get_connection() as conn:
            # Reseteamos el aviso_previo a 0 para que no aparezca en /lista.
            conn.cursor().execute("UPDATE recordatorios SET aviso_previo = 0 WHERE id = %s", (rid,))
                           
        # Editamos el mensaje para quitar los botones, manteniendo el texto original.
        await query.edit_message_text(text=query.message.text, reply_markup=None, parse_mode="Markdown")



# =============================================================================
# DEFINICIÓN DEL HANDLER
# =============================================================================
# Este handler escucha por todos los patrones de callback que pueden llegar
# desde una notificación de aviso.
snooze_handler = CallbackQueryHandler(handle_snooze_or_done, pattern=r"^(snooze|mark_done|ok):")