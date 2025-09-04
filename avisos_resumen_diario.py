# resumen_diario.py
"""
Módulo para la gestión integral del Resumen Diario Proactivo.

Este archivo contiene toda la lógica relacionada con el resumen diario:
- La función que envía el resumen a un usuario.
- Las funciones para programar y cancelar la tarea recurrente en el scheduler.
"""

from telegram.error import Forbidden
import bot_state
from db import get_recordatorios
from utils import construir_mensaje_lista_completa
from personalidad import get_text

from avisos import scheduler   # Necesitamos acceso directo al scheduler para gestionar los jobs.



# =============================================================================
# FUNCIÓN PRINCIPAL DE ENVÍO
# =============================================================================

async def enviar_resumen_para_usuario(chat_id: int):
    """
    Función ejecutada por el scheduler para enviar el resumen diario a un usuario específico.
    """
    print(f"🌞 Ejecutando resumen diario para el chat_id: {chat_id}")
    try:
        recordatorios_hoy, total = get_recordatorios(chat_id, filtro="hoy")
        if recordatorios_hoy:
            introduccion = get_text("resumen_diario_con_tareas")
            cuerpo_lista = construir_mensaje_lista_completa(chat_id, recordatorios_hoy)
            mensaje_final = introduccion + "\n\n" + cuerpo_lista

            await bot_state.telegram_app.bot.send_message(
                chat_id=chat_id, text=mensaje_final, parse_mode="Markdown"
            )
            print(f"  ✅ Resumen enviado al chat {chat_id}")
    except Forbidden:
        print(f"⚠️ No se pudo enviar resumen al chat {chat_id}, el usuario ha bloqueado el bot.")
    except Exception as e:
        print(f"🚨 Error enviando resumen al chat {chat_id}: {e}")



# =============================================================================
# FUNCIONES DE GESTIÓN DEL SCHEDULER
# =============================================================================

def programar_resumen_diario_usuario(chat_id: int, hora_str: str, tz_str: str):
    """
    Programa o actualiza el job recurrente (cron) para el resumen diario de un usuario.
    """
    try:
        hora, minuto = map(int, hora_str.split(':'))
        scheduler.add_job(
            enviar_resumen_para_usuario, trigger='cron', hour=hora, minute=minuto,
            timezone=tz_str, id=f'resumen_diario_{chat_id}', args=[chat_id],
            replace_existing=True
        )
        print(f"🗓️ Resumen diario (re)programado para el usuario {chat_id} a las {hora_str} ({tz_str})")
    except Exception as e:
        print(f"🚨 Error al programar el resumen para {chat_id}: {e}")

def cancelar_resumen_diario_usuario(chat_id: int):
    """Cancela el job recurrente del resumen diario para un usuario."""
    job_id = f'resumen_diario_{chat_id}'
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"🗓️ Resumen diario cancelado para el usuario {chat_id}")
    except Exception as e:
        print(f"🚨 Error al cancelar el resumen para {chat_id}: {e}")