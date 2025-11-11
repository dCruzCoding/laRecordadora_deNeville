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

# Importaciones módulos locales
import bot_state # Módulo de estado global para acceder a la instancia de la app
from personalidad import get_text
from db import get_connection
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

async def programar_avisos(chat_id: int, rid: str, user_id: int, texto: str, fecha: datetime, aviso_previo_min: int, es_pospuesto: bool = False) -> bool:
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
    
    if not es_pospuesto:
        print(f"✅ Recordatorio programado: '{rid}' para las {fecha.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")

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
            if es_pospuesto:
                print(f"🔔 Aviso previo REPROGRAMADO: '{rid}' para {tiempo_str} antes, a las {aviso_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
            else:
                print(f"  🔔└─ Aviso previo: {tiempo_str} antes, a las {aviso_time.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")
            aviso_previo_programado = True
        else:
            print(f"  ❌└─ Aviso previo para '{rid}' omitido porque su hora ya ha pasado.")
            # La variable de retorno se queda en False, como debe ser.
    
    return aviso_previo_programado

async def enviar_recordatorio(chat_id: int, user_id: int, texto: str, rid: str):
    """Función ejecutada por el scheduler para enviar la notificación principal."""
    if bot_state.telegram_app:
        # --- CAMBIO: Limpiamos el aviso_previo al llegar la hora final ---
        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE recordatorios SET aviso_previo = 0 WHERE id = %s", (rid,))

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
    Cancela los jobs asociados a un ID de recordatorio.
    Puede manejar IDs de recordatorios normales ("123") y fijos ("fijo_123").
    """
    job_ids_a_buscar = []

    # Si el ID ya empieza con "fijo_", es un recordatorio fijo y solo hay un job.
    if rid.startswith("fijo_"):
        job_ids_a_buscar.append(rid)
    else:
        # Si no, es un recordatorio normal. Buscamos sus dos posibles jobs.
        job_ids_a_buscar.append(f"recordatorio_{rid}")
        job_ids_a_buscar.append(f"aviso_{rid}")

    for job_id in job_ids_a_buscar:
        try:
            # Comprobamos si el job existe antes de intentar borrarlo
            if scheduler.get_job(job_id):
                scheduler.remove_job(job_id)
                print(f"🗑️  Job del scheduler cancelado: {job_id}")
        except Exception as e:
            # Este print es útil para depurar si algo sale mal
            print(f"⚠️ Error al intentar cancelar el job {job_id}: {e}")

def cancelar_todos_los_avisos():
    """Función de emergencia o reseteo: elimina TODOS los jobs del scheduler."""
    if scheduler.running:
        scheduler.remove_all_jobs()
    print("🔥 Todos los avisos programados han sido eliminados.")


# =============================================================================
# GESTIÓN DE RECORDATORIOS FIJOS (RECURRENTES)
# =============================================================================

def programar_recordatorio_fijo_diario(chat_id: int, fijo_id: int, texto: str, hora: int, minuto: int, timezone: str, dias_semana_str: str):
    """
    Programa un job recurrente (cron) que se ejecuta todos los días a una hora específica.
    """
    job_id = f"fijo_{fijo_id}"
    scheduler.add_job(
        enviar_recordatorio_fijo,
        trigger='cron',
        hour=hora,
        minute=minuto,
        day_of_week=dias_semana_str,
        timezone=timezone,
        id=job_id,
        args=[chat_id, texto],
        replace_existing=True
    )
    print(f"🗓️   Recordatorio fijo DIARIO programado: job_id='{job_id}' para las {hora}:{minuto:02d} ({dias_semana_str}) en {timezone}")

async def enviar_recordatorio_fijo(chat_id: int, texto: str):
    """
    Función simple ejecutada por el scheduler para enviar la notificación de un recordatorio fijo.
    """
    if bot_state.telegram_app:
        mensaje = f"⏰ ¡Recordatorio diario!\n\n- _{texto}_"
        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=mensaje, parse_mode="Markdown"
        )