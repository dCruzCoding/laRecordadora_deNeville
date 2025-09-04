# avisos.py
"""
Módulo de Gestión de Tareas Programadas (Scheduler).

Este archivo se encarga de toda la interacción con la librería APScheduler.
Sus responsabilidades incluyen:
- Iniciar y detener el scheduler de forma segura.
- Programar, reprogramar y cancelar los avisos de recordatorios individuales.
- Programar y cancelar las tareas recurrentes, como el resumen diario.
"""





from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from telegram.ext import Application
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

import bot_state # Módulo de estado global para acceder a la instancia de la app
from personalidad import get_text





# --- CONFIGURACIÓN DEL SCHEDULER ---
# Se utiliza una base de datos SQLite para la persistencia de los trabajos (jobs),
# lo que permite que las tareas programadas sobrevivan a reinicios del bot.
# Todas las fechas se manejan internamente en UTC para evitar ambigüedades.
scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')},
    timezone=pytz.utc
)



# =============================================================================
# FUNCIONES DE CONTROL PRINCIPAL DEL SCHEDULER
# =============================================================================

async def iniciar_scheduler(app: Application):
    """
    Punto de entrada del scheduler. Se llama una vez al iniciar el bot.
    Guarda la instancia de la aplicación en el estado global y arranca el scheduler.
    """
    bot_state.telegram_app = app
    if not scheduler.running:
        scheduler.start()
        print("⏰ Scheduler iniciado.")

def detener_scheduler():
    """Detiene el scheduler de forma segura al apagar el bot."""
    if scheduler.running:
        scheduler.shutdown()



# =============================================================================
# GESTIÓN DE RECORDATORIOS INDIVIDUALES
# =============================================================================

async def programar_avisos(chat_id: int, rid: str, user_id: int, texto: str, fecha: datetime, aviso_previo_min: int) -> bool:
    """
    Programa el aviso principal y, si corresponde, el aviso previo para un recordatorio.

    Args:
        (Varios): Datos del recordatorio.
        aviso_previo_min (int): Minutos de antelación para el aviso previo.

    Returns:
        bool: True si el aviso previo fue programado con éxito, False en caso contrario
              (ya sea porque no se pidió o porque su hora ya había pasado).
    """

    aviso_previo_programado = False  # Inicializamos la variable de retorno para evitar errores.
    if not fecha:
        return aviso_previo_programado

    # 1. Programar el aviso principal (a la hora del recordatorio)
    scheduler.add_job(
        enviar_recordatorio, 'date', run_date=fecha, id=f"recordatorio_{rid}",
        args=[chat_id, user_id, texto, rid], misfire_grace_time=60, replace_existing=True
    )
    print(f"✅ Recordatorio programado: '{rid}' para las {fecha.strftime('%Y-%m-%d %H:%M:%S')}")

    # 2. Programar el aviso previo (si aplica y es en el futuro)
    if aviso_previo_min > 0:
        aviso_time = fecha - timedelta(minutes=aviso_previo_min)
        if aviso_time > datetime.now(pytz.utc):
            scheduler.add_job(
                enviar_aviso_previo, 'date', run_date=aviso_time, id=f"aviso_{rid}",
                args=[chat_id, user_id, texto, aviso_previo_min, rid],
                misfire_grace_time=60, replace_existing=True
            )
            horas, mins = divmod(aviso_previo_min, 60)
            tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            print(f"  🔔└─ Aviso previo: {tiempo_str} antes, a las {aviso_time.strftime('%Y-%m-%d %H:%M:%S')}")
            aviso_previo_programado = True
        else:
            print(f"  ❌└─ Aviso previo para '{rid}' omitido porque su hora ya ha pasado.")
            # La variable de retorno se queda en False, como debe ser.
    
    return aviso_previo_programado

async def enviar_recordatorio(chat_id: int, user_id: int, texto: str, rid: str):
    """Función ejecutada por el scheduler para enviar la notificación principal."""
    if bot_state.telegram_app:
        mensaje = get_text("aviso_principal", id=user_id, texto=texto)
        keyboard = [[
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{rid}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{rid}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=mensaje, parse_mode="Markdown", reply_markup=reply_markup
        )

async def enviar_aviso_previo(chat_id: int, user_id: int, texto: str, minutos: int, rid: str):
    """Función ejecutada por el scheduler para enviar el aviso previo."""
    if bot_state.telegram_app:
        horas, mins = divmod(minutos, 60)
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        mensaje = get_text("aviso_previo", tiempo=tiempo_str, id=user_id, texto=texto)
        
        keyboard_buttons = [
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{rid}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{rid}")
        ]
        
        # El botón de posponer solo se muestra si el aviso es de más de 10 minutos
        if minutos > 10:
            keyboard_buttons.insert(1, InlineKeyboardButton("⏰ +10 min", callback_data=f"posponer:10:{rid}"))

        reply_markup = InlineKeyboardMarkup([keyboard_buttons])
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=mensaje, parse_mode="Markdown", reply_markup=reply_markup
        )

def cancelar_avisos(rid: str):
    """
    Cancela todos los jobs (principal y previo) asociados a un ID de recordatorio.
    Utiliza un try-except genérico porque el error más común (JobLookupError)
    simplemente significa que el job ya no existía, lo cual no es un problema.
    """
    for job_id in [f"recordatorio_{rid}", f"aviso_{rid}"]:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

def cancelar_todos_los_avisos():
    """Función de emergencia o reseteo: elimina TODOS los jobs del scheduler."""
    if scheduler.running:
        scheduler.remove_all_jobs()
    print("🔥 Todos los avisos programados han sido eliminados.")
