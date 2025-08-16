from telegram import Update
from telegram.ext import ContextTypes
from db import get_connection
from utils import formatear_fecha_para_mensaje


async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Determinar filtro por argumento
    filtro = None
    if context.args:
        arg = context.args[0].lower()
        if arg in ("pendientes", "pendiente"):
            filtro = 0
        elif arg in ("hechos", "hecho"):
            filtro = 1
        else:
            await update.message.reply_text("⚠️ Uso: /lista [pendientes|hechos]")
            return

    # Construir consulta SQL según filtro
    with get_connection() as conn:
        cursor = conn.cursor()
        if filtro is None:
            cursor.execute("SELECT id, texto, fecha_hora, estado FROM recordatorios ORDER BY fecha_hora")
        else:
            cursor.execute(
                "SELECT id, texto, fecha_hora, estado FROM recordatorios WHERE estado = ? ORDER BY fecha_hora",
                (filtro,)
            )
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios para este filtro.")
        return

    # Encabezado dinámico
    if filtro is None:
        titulo = "📋 Lista de todos los recordatorios:"
    elif filtro == 0:
        titulo = "Lista de recordatorios pendientes:"
    else:
        titulo = "Lista de recordatorios hechos:"

    mensaje = [f"*{titulo}*"]
    for rid, texto, fecha_iso, estado in recordatorios:
        fecha_str = formatear_fecha_para_mensaje(fecha_iso)
        estado_str = "✅ Hecho" if estado == 1 else "🕒 Pendiente"
        mensaje.append(f"`{rid}` - {texto} ({fecha_str}) [{estado_str}]")

    await update.message.reply_text("\n".join(mensaje), parse_mode="Markdown")
