from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
import asyncio

scheduler = BackgroundScheduler()
scheduler.start()

async def enviar_mensaje(bot, chat_id, texto):
    await bot.send_message(chat_id=chat_id, text=texto)

def programar_avisos(bot, chat_id, fecha_evento: datetime, recordatorio_id: str, modo_tester=False):
    """
    Programa avisos para un evento:
    - 24h antes
    - 1h antes
    - 1min antes (solo si modo_tester=True)
    Cada job se identifica con el recordatorio_id + sufijo
    """
    ahora = datetime.now()
    loop = asyncio.get_event_loop()

    avisos = [
        (fecha_evento - timedelta(hours=24), "⏰ Recordatorio: ¡tu evento es en 24 horas!"),
        (fecha_evento - timedelta(hours=1), "⏰ Recordatorio: ¡tu evento es en 1 hora!"),
    ]

    if modo_tester:
        avisos.append((fecha_evento - timedelta(minutes=1), "⏰ Recordatorio TEST: ¡tu evento es en 1 minuto!"))

    for i, (momento, mensaje) in enumerate(avisos, start=1):
        if momento > ahora:
            job_id = f"{recordatorio_id}_{i}"
            scheduler.add_job(
                lambda m=mensaje: asyncio.run_coroutine_threadsafe(
                    enviar_mensaje(bot, chat_id, m),
                    loop
                ),
                'date',
                run_date=momento,
                id=job_id,
                replace_existing=True  # si existía, lo reemplaza
            )

def cancelar_avisos(recordatorio_id: str):
    """Cancela todos los avisos de un recordatorio usando su ID"""
    for job in list(scheduler.get_jobs()):
        if job.id.startswith(recordatorio_id):
            scheduler.remove_job(job.id)
