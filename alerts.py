# alerts.py
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

# Importaciones módulos locales
import bot_state # Módulo de estado global para acceder a la instancia de la app
from personality import get_text
from db import update_reminder_pre_alert, get_pinned_by_chat_id
from config import SUPABASE_DB_URL


# --- CONFIGURACIÓN DEL SCHEDULER ---

# CONSTRUIMOS LA URL ESPECIAL PARA EL SCHEDULER
# SQLAlchemy necesita este parámetro para funcionar bien con PgBouncer (el pooler de Supabase)
# y evitar que las conexiones se cierren inesperadamente.
SCHEDULER_DB_URL = f"{SUPABASE_DB_URL}?options=-c%20pool_pre_ping=true"

# Todas las fechas se manejan internamente en UTC para evitar ambigüedades.
scheduler = AsyncIOScheduler(
    jobstores={'default': SQLAlchemyJobStore(url=SUPABASE_DB_URL)},
    timezone=pytz.utc
)



# =============================================================================
# FUNCIONES DE CONTROL PRINCIPAL DEL SCHEDULER
# =============================================================================

async def start_scheduler(app: Application):
    """
    Punto de entrada del scheduler. Se llama una vez al iniciar el bot.
    Guarda la instancia de la aplicación en el estado global y arranca el scheduler.
    """
    bot_state.telegram_app = app
    if not scheduler.running:
        scheduler.start()
        print("⏰ Scheduler iniciado.")

def stop_scheduler():
    """Detiene el scheduler de forma segura al apagar el bot."""
    if scheduler.running:
        scheduler.shutdown()



# =============================================================================
# GESTIÓN DE RECORDATORIOS INDIVIDUALES
# =============================================================================

async def schedule_alerts(chat_id: int, reminder_id: str, user_id: int, text: str, datetime: datetime, pre_alert: int, is_snooze: bool = False) -> bool:
    """
    Programa el aviso principal y, si corresponde, el aviso previo para un recordatorio.
    """

    pre_alert_scheduled = False  # Inicializamos la variable de retorno para evitar errores.
    if not datetime:
        return pre_alert_scheduled

    # 1. Programar el aviso principal (a la hora del recordatorio)
    scheduler.add_job(
        send_reminder, 'date', run_date=datetime, id=f"reminder_{reminder_id}",
        args=[chat_id, user_id, text, reminder_id], misfire_grace_time=60, replace_existing=True
    )
    
    if not is_snooze:
        print(f"✅ Recordatorio programado: '{reminder_id}' para las {datetime.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")

    # 2. Programar el aviso previo (si aplica y es en el futuro)
    if pre_alert > 0:
        alert_time = datetime - timedelta(minutes=pre_alert)
        if alert_time > datetime.now(pytz.utc):
            scheduler.add_job(
                send_pre_alert, 'date', run_date=alert_time, id=f"pre_alert_{reminder_id}",
                args=[chat_id, user_id, text, pre_alert, reminder_id],
                misfire_grace_time=60, replace_existing=True
            )
            hours, mins = divmod(pre_alert, 60)
            time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            if is_snooze:
                print(f"🔔 Aviso previo REPROGRAMADO: '{reminder_id}' para {time_str} antes, a las {alert_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
            else:
                print(f"  🔔└─ Aviso previo: {time_str} antes, a las {alert_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
            pre_alert_scheduled = True
        else:
            print(f"  ❌└─ Aviso previo para '{reminder_id}' omitido porque su hora ya ha pasado.")
            # La variable de retorno se queda en False, como debe ser.
    
    return pre_alert_scheduled

async def send_reminder(chat_id: int, user_id: int, text: str, reminder_id: str):
    """Función ejecutada por el scheduler para enviar la notificación principal."""
    if bot_state.telegram_app:
        update_reminder_pre_alert(chat_id, int(reminder_id), 0)

        message = get_text("aviso_principal", id=user_id, text=text)
        keyboard = [[
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{reminder_id}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{reminder_id}")
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown", reply_markup=reply_markup
        )

async def send_pre_alert(chat_id: int, user_id: int, text: str, minutes: int, reminder_id: str):
    """Función ejecutada por el scheduler para enviar el aviso previo."""
    if bot_state.telegram_app:
        hours, mins = divmod(minutes, 60)
        time_str = f"{hours}h" if mins == 0 else f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
        message = get_text("aviso_previo", time=time_str, id=user_id, text=text)
        
        keyboard_buttons = [
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{reminder_id}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{reminder_id}")
        ]
        
        # El botón de posponer solo se muestra si el aviso es de más de 10 minutos
        if minutes > 10:
            keyboard_buttons.insert(1, InlineKeyboardButton("⏰ +10 min", callback_data=f"snooze:10:{reminder_id}")) 

        reply_markup = InlineKeyboardMarkup([keyboard_buttons])
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown", reply_markup=reply_markup
        )

def cancel_alerts(reminder_id: str):
    """
    Cancela los jobs asociados a un ID de recordatorio.
    Puede manejar IDs de recordatorios normales ("123") y fijos ("fijo_123").
    """
    jobs_ids_to_find = []

    # Si el ID ya empieza con "fijo_", es un recordatorio fijo y solo hay un job.
    if reminder_id.startswith("fijo_"):
        jobs_ids_to_find.append(reminder_id)
    else:
        # Si no, es un recordatorio normal. Buscamos sus dos posibles jobs.
        jobs_ids_to_find.append(f"reminder_{reminder_id}")
        jobs_ids_to_find.append(f"alert_{reminder_id}")
    for job_id in jobs_ids_to_find:
        try:
            # Comprobamos si el job existe antes de intentar borrarlo
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                print(f"🗑️  Job del scheduler cancelado: {job_id}")
        except Exception as e:
            # Este print es útil para depurar si algo sale mal
            print(f"⚠️ Error al intentar cancelar el job {job_id}: {e}")

def cancel_all_alerts():
    """Función de emergencia o reseteo: elimina TODOS los jobs del scheduler."""
    if scheduler.running:
        scheduler.remove_all_jobs()
    print("🔥 Todos los avisos programados han sido eliminados.")


# =============================================================================
# GESTIÓN DE RECORDATORIOS FIJOS (RECURRENTES)
# =============================================================================

def reschedule_all_pinned_for_chat(chat_id: int):
    """
    Obtiene TODOS los recordatorios fijos de un usuario desde la DB, limpia los antiguos
    del scheduler y programa los nuevos. Es la única fuente de verdad para la programación.
    """
    print(f"🔄 Resincronizando todos los recordatorios fijos para el chat_id: {chat_id}...")
    
    # 1. Obtenemos las reglas de programación actualizadas desde la base de datos.
    all_pinned = get_pinned_by_chat_id(chat_id)

    # 2. Limpiamos todos los jobs FIJOS existentes para este usuario.
    #    Esto previene "jobs fantasma" si algo se borró manualmente o hubo un error.
    for job in scheduler.get_jobs():
        if job.id.startswith(f'pinned_') and job.args[0] == chat_id:
            try:
                scheduler.remove_job(job.id)
                print(f"🗑️  Limpiando job fijo antiguo: {job.id}")
            except Exception as e:
                print(f"⚠️  Error al limpiar job antiguo {job.id}: {e}")

    # 3. Iteramos y programamos cada recordatorio fijo con la información fresca de la DB.
    for pinned_id, text, local_time, timezone, week_days in all_pinned:
        
        job_id = f"pinned_{pinned_id}"
        try:
            scheduler.add_job(
                send_pinned_reminder,
                trigger='cron',
                hour=local_time.hour,
                minute=local_time.minute,
                day_of_week=week_days,
                timezone=timezone,
                id=job_id,
                args=[chat_id, text],
                replace_existing=True # 'replace_existing' es una buena salvaguarda
            )
            print(f"🗓️   Recordatorio fijo programado: '{job_id}' para las {local_time.hour}:{local_time.minute:02d} ({week_days}) en {timezone}")
        except Exception as e:
            print(f"Error al programar el recordatorio fijo {job_id}: {e}")

async def send_pinned_reminder(chat_id: int, text: str):
    """
    Función simple ejecutada por el scheduler para enviar la notificación de un recordatorio fijo.
    """
    if bot_state.telegram_app:
        message = f"⏰ ¡Recordatorio diario!\n\n- _{text}_"
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=message, parse_mode="Markdown"
        )