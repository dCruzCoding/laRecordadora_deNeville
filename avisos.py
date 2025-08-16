from datetime import timedelta
from telegram.ext import ContextTypes

async def programar_avisos(context: ContextTypes.DEFAULT_TYPE, chat_id, rid, texto, fecha, aviso_previo_min):
    """Programa el aviso previo y el aviso principal."""
    if fecha:
        # Aviso principal
        context.job_queue.run_once(
            enviar_recordatorio,
            fecha,
            name=f"recordatorio_{rid}",
            data={"chat_id": chat_id, "id": rid, "texto": texto},
        )
        # Aviso previo
        if aviso_previo_min > 0:
            aviso_time = fecha - timedelta(minutes=aviso_previo_min)
            if aviso_time > context.application.timeouts["current_time"]():
                context.job_queue.run_once(
                    enviar_aviso_previo,
                    aviso_time,
                    name=f"aviso_{rid}",
                    data={"chat_id": chat_id, "id": rid, "texto": texto, "minutos": aviso_previo_min},
                )

async def enviar_recordatorio(context: ContextTypes.DEFAULT_TYPE):
    """Envía el recordatorio principal."""
    data = context.job.data
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⏰ *¡Es la hora!* `{data['id']}` - {data['texto']}",
        parse_mode="Markdown"
    )

async def enviar_aviso_previo(context: ContextTypes.DEFAULT_TYPE):
    """Envía el aviso previo."""
    data = context.job.data
    horas = data["minutos"] // 60
    mins = data["minutos"] % 60
    tiempo_str = f"{horas}h" if mins == 0 else f"{horas}h {mins}m" if horas > 0 else f"{mins}m"
    await context.bot.send_message(
        chat_id=data["chat_id"],
        text=f"⚠️ *Aviso previo* ({tiempo_str} antes): `{data['id']}` - {data['texto']}",
        parse_mode="Markdown"
    )

def cancelar_avisos(context: ContextTypes.DEFAULT_TYPE, rid):
    """Cancela cualquier job asociado a un recordatorio."""
    for job_name in (f"recordatorio_{rid}", f"aviso_{rid}"):
        jobs = context.job_queue.get_jobs_by_name(job_name)
        for job in jobs:
            job.schedule_removal()
