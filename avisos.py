from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from telegram.ext import Application
from personalidad import get_text

# --- Variable Global ---
# Guardará la instancia de la aplicación de PTB para poder usar el bot
telegram_app: Application = None

# --- Configuración del Scheduler ---
scheduler = AsyncIOScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
    },
    timezone=pytz.utc
)

async def iniciar_scheduler(app: Application):
    """Guarda la instancia de la app de Telegram y arranca el scheduler."""
    global telegram_app
    telegram_app = app
    if not scheduler.running:
        scheduler.start()

def detener_scheduler():
    """Detiene el scheduler de forma segura."""
    if scheduler.running:
        scheduler.shutdown()

async def programar_avisos(chat_id: int, rid: str, user_id: int, texto: str, fecha: datetime, aviso_previo_min: int):
    """Programa los avisos usando fechas "aware" (conscientes de la zona horaria)."""
    if not fecha:
        return

    # Aviso principal
    scheduler.add_job(
        enviar_recordatorio,
        'date',
        run_date=fecha,
        id=f"recordatorio_{rid}",
        args=[chat_id, user_id, texto],
        misfire_grace_time=60,
        replace_existing=True
    )

    # Imprimimos la confirmación del aviso principal
    print(f"✅ Recordatorio programado: '{rid}' para las {fecha.strftime('%Y-%m-%d %H:%M:%S')}")

    # Aviso previo
    if aviso_previo_min > 0:
        aviso_time = fecha - timedelta(minutes=aviso_previo_min)
        # Comparamos con la hora actual con zona horaria
        if aviso_time > datetime.now(tz=scheduler.timezone):
            scheduler.add_job(
                enviar_aviso_previo,
                'date',
                run_date=aviso_time,
                id=f"aviso_{rid}",
                args=[chat_id, user_id, texto, aviso_previo_min],
                misfire_grace_time=60,
                replace_existing=True
            )

            # Lógica para formatear el tiempo del aviso previo para el print
            horas = aviso_previo_min // 60
            mins = aviso_previo_min % 60
            tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            
            # Imprimimos la confirmación del aviso previo
            print(f"  🔔└─ Aviso previo: {tiempo_str} antes, a las {aviso_time.strftime('%Y-%m-%d %H:%M:%S')}")

async def enviar_recordatorio(chat_id: int, user_id: int, texto: str):
    """Usa la variable global 'telegram_app' para enviar el mensaje."""
    if telegram_app:
        mensaje = get_text("aviso_principal", id=user_id, texto=texto)
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode="Markdown"
        )

async def enviar_aviso_previo(chat_id: int, user_id: int, texto: str, minutos: int):
    """Usa la variable global 'telegram_app' para enviar el aviso previo."""
    if telegram_app:
        horas = minutos // 60
        mins = minutos % 60
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        
        mensaje = get_text("aviso_previo", tiempo=tiempo_str, id=user_id, texto=texto)
        await telegram_app.bot.send_message(
            chat_id=chat_id,
            text=mensaje,
            parse_mode="Markdown"
        )

def cancelar_avisos(rid: str):
    """Cancela los jobs asociados a un recordatorio."""
    for job_id in [f"recordatorio_{rid}", f"aviso_{rid}"]:
        try:
            scheduler.remove_job(job_id)
        except Exception:
            pass

def cancelar_todos_los_avisos():
    """Elimina TODOS los jobs programados del scheduler."""
    if scheduler.running:
        scheduler.remove_all_jobs()
    print("🔥 Todos los avisos programados han sido eliminados.")