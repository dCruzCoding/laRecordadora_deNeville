from datetime import datetime, timedelta
import pytz
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from telegram.ext import Application
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from personalidad import get_text
# from handlers.resumen_diario import enviar_resumen_para_usuario
from datetime import datetime
import bot_state

# --- Variable Global ---
# # Guardará la instancia de la aplicación de PTB para poder usar el bot
# telegram_app: Application = None

# --- Configuración del Scheduler ---
scheduler = AsyncIOScheduler(
    jobstores={
        'default': SQLAlchemyJobStore(url='sqlite:///jobs.sqlite')
    },
    timezone=pytz.utc
)

async def iniciar_scheduler(app: Application):
    """Guarda la instancia de la app, arranca el scheduler y programa el resumen diario."""
    bot_state.telegram_app = app
    if not scheduler.running:
        scheduler.start()
        print("⏰ Scheduler iniciado.")

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
        args=[chat_id, user_id, texto, rid],
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
                args=[chat_id, user_id, texto, aviso_previo_min, rid],
                misfire_grace_time=60,
                replace_existing=True
            )

            # Lógica para formatear el tiempo del aviso previo para el print
            horas = aviso_previo_min // 60
            mins = aviso_previo_min % 60
            tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
            
            # Imprimimos la confirmación del aviso previo
            print(f"  🔔└─ Aviso previo: {tiempo_str} antes, a las {aviso_time.strftime('%Y-%m-%d %H:%M:%S')}")

async def enviar_recordatorio(chat_id: int, user_id: int, texto: str, rid: str):
    """Envía el recordatorio principal, AHORA CON BOTONES DINÁMICOS."""
    if bot_state.telegram_app:
        mensaje = get_text("aviso_principal", id=user_id, texto=texto)
        
        # --- LÓGICA DE BOTONES DINÁMICOS ---
        # Por defecto, solo mostramos OK y Hecho
        keyboard_buttons = [
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{rid}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{rid}")
        ]
        
        # El botón de posponer ya no tiene sentido en el recordatorio principal,
        # ya que este se actualizará. Lo dejamos solo en el aviso previo.

        keyboard = [keyboard_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await bot_state.telegram_appbot.send_message(
            chat_id=chat_id, text=mensaje, parse_mode="Markdown", reply_markup=reply_markup
        )

async def enviar_aviso_previo(chat_id: int, user_id: int, texto: str, minutos: int, rid: str):
    """Envía el aviso previo, AHORA CON BOTONES DINÁMICOS."""
    if bot_state.telegram_app:
        horas = minutos // 60
        mins = minutos % 60
        tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
        mensaje = get_text("aviso_previo", tiempo=tiempo_str, id=user_id, texto=texto)

        # --- LÓGICA DE BOTONES DINÁMICOS ---
        keyboard_buttons = [
            InlineKeyboardButton("👌 OK", callback_data=f"ok:{rid}"),
            InlineKeyboardButton("✅ Hecho", callback_data=f"mark_done:{rid}")
        ]
        
        # REGLA 1: Solo mostramos el botón de posponer si el aviso es de MÁS de 10 minutos.
        if minutos > 10:
            # Insertamos el botón de posponer en el medio.
            keyboard_buttons.insert(1, InlineKeyboardButton("⏰ +10 min", callback_data=f"posponer:10:{rid}"))

        keyboard = [keyboard_buttons]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await bot_state.telegram_app.bot.send_message(
            chat_id=chat_id, text=mensaje, parse_mode="Markdown", reply_markup=reply_markup
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

def programar_resumen_diario_usuario(chat_id: int, hora_str: str, tz_str: str):
    """
    Programa (o reprograma) el job del resumen diario para un usuario.
    """
    # Importación local para evitar el problema de carga circular
    from handlers.resumen_diario import enviar_resumen_para_usuario
    
    try:
        hora, minuto = map(int, hora_str.split(':'))
        scheduler.add_job(
            enviar_resumen_para_usuario,
            trigger='cron',
            hour=hora,
            minute=minuto,
            timezone=tz_str, # ¡Usamos la zona horaria del usuario!
            id=f'resumen_diario_{chat_id}',
            args=[chat_id],
            replace_existing=True # Si ya existe un job con ese ID, lo reemplaza
        )
        print(f"🗓️ Resumen diario (re)programado para el usuario {chat_id} a las {hora_str} ({tz_str})")
    except Exception as e:
        print(f"🚨 Error al programar el resumen para {chat_id}: {e}")

def cancelar_resumen_diario_usuario(chat_id: int):
    """
    Cancela el job del resumen diario para un usuario.
    """
    job_id = f'resumen_diario_{chat_id}'
    try:
        if scheduler.get_job(job_id):
            scheduler.remove_job(job_id)
            print(f"🗓️ Resumen diario cancelado para el usuario {chat_id}")
    except Exception as e:
        print(f"🚨 Error al cancelar el resumen para {chat_id}: {e}")