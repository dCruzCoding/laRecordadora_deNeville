from telegram import Update
from telegram.ext import ContextTypes, CallbackQueryHandler
from datetime import datetime, timedelta
import pytz

from db import get_connection, get_config
from avisos import cancelar_avisos, programar_avisos

async def handle_posponer_or_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Maneja las pulsaciones de los botones de las notificaciones con la nueva lógica.
    """
    query = update.callback_query
    await query.answer()

    parts = query.data.split(":")
    action = parts[0]
    rid = parts[-1] 

    with get_connection() as conn:
        cursor = conn.cursor()
        # Pedimos más datos: la fecha_hora y el aviso_previo originales
        cursor.execute("SELECT user_id, texto, estado, fecha_hora, aviso_previo FROM recordatorios WHERE id = ?", (rid,))
        recordatorio_data = cursor.fetchone()

        if not recordatorio_data:
            await query.edit_message_text(text="👵 Vaya, parece que este recordatorio ya fue borrado o modificado.")
            return

        user_id, texto, estado_actual, fecha_hora_iso, aviso_previo_actual = recordatorio_data

        if estado_actual == 1:
             await query.edit_message_text(text=f"✅ _{texto}_ \n\n(Este recordatorio ya estaba marcado como hecho).", parse_mode="Markdown")
             return

    # --- Lógica para cada acción ---

    if action == "mark_done":
        with get_connection() as conn:
            # Ponemos estado a HECHO y borramos el aviso_previo
            conn.execute("UPDATE recordatorios SET estado = 1, aviso_previo = 0 WHERE id = ?", (rid,))
            conn.commit()
        cancelar_avisos(rid)
        await query.edit_message_text(text=f"✅ ¡Bien hecho! Has completado: _{texto}_", parse_mode="Markdown")

    elif action == "posponer":
        # REGLA 2: "Posponer" actualiza la fecha del recordatorio.
        minutos_posponer = int(parts[1])
        fecha_hora_actual_utc = datetime.fromisoformat(fecha_hora_iso)
        
        # Calculamos la nueva fecha del recordatorio principal
        nueva_fecha_utc = fecha_hora_actual_utc + timedelta(minutes=minutos_posponer)
        
        with get_connection() as conn:
            # Actualizamos la fecha_hora en la DB y reseteamos el aviso_previo
            conn.execute("UPDATE recordatorios SET fecha_hora = ?, aviso_previo = 0 WHERE id = ?", (nueva_fecha_utc.isoformat(), rid))
            conn.commit()
        
        # Cancelamos los viejos avisos y reprogramamos TODO con la nueva fecha.
        # Esto es más robusto. Mantenemos el aviso previo original si lo tenía.
        cancelar_avisos(rid)
        if aviso_previo_actual and aviso_previo_actual > 0:
             await programar_avisos(
                 update.effective_chat.id, rid, user_id, texto, nueva_fecha_utc, aviso_previo_actual
             )
        else: # Si no tenía aviso previo, solo se programa el principal
             await programar_avisos(
                 update.effective_chat.id, rid, user_id, texto, nueva_fecha_utc, 0
             )

        # Confirmamos al usuario
        user_tz_str = get_config(update.effective_chat.id, "user_timezone") or 'UTC'
        nueva_fecha_local = nueva_fecha_utc.astimezone(pytz.timezone(user_tz_str))
        hora_local_str = nueva_fecha_local.strftime('%d %b, %H:%M')
        
        await query.edit_message_text(text=f"⏰ ¡De acuerdo! He pospuesto el recordatorio. Nueva hora: *{hora_local_str}*. \n\n Tarea: _{texto}_", parse_mode="Markdown")

    elif action == "ok":
        # REGLA 3: "OK" desactiva el aviso.
        with get_connection() as conn:
            # Reseteamos el aviso_previo a 0 para que no aparezca en /lista.
            conn.execute("UPDATE recordatorios SET aviso_previo = 0 WHERE id = ?", (rid,))
            conn.commit()
        
        # También cancelamos los jobs por si quedara el aviso principal
        cancelar_avisos(rid)
        
        await query.edit_message_text(text=query.message.text, parse_mode="Markdown")


# --- HANDLER ---
posponer_handler = CallbackQueryHandler(handle_posponer_or_done, pattern=r"^(posponer|mark_done|ok):")