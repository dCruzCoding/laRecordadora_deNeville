from telegram import Update
from telegram.ext import ContextTypes
from db import get_connection, actualizar_recordatorios_pasados
from utils import formatear_fecha_para_mensaje, formatear_lista_para_mensaje
from datetime import datetime, timedelta
from config import ESTADOS  # Importamos los estados desde config

def _build_list_string(reminders: list, show_aviso_info: bool = False) -> str:
    """Función ayudante para formatear una lista de recordatorios en un string."""
    lines = []
    for rid, texto, fecha_iso, _, aviso_previo in reminders:
        fecha_str = formatear_fecha_para_mensaje(fecha_iso)
        
        # Línea principal, ahora sin el estado
        entry = f"`{rid}` - {texto} ({fecha_str})"
        
        # La información del aviso se añade si se especifica
        if show_aviso_info:
            if fecha_iso and aviso_previo and aviso_previo > 0:
                fecha_recordatorio = datetime.fromisoformat(fecha_iso)
                fecha_aviso = fecha_recordatorio - timedelta(minutes=aviso_previo)
                aviso_info_str = f"🔔 Aviso a las: {fecha_aviso.strftime('%d %b, %H:%M')}"
            else:
                aviso_info_str = "🔕 Sin aviso programado"
            entry += f"\n  └─ {aviso_info_str}"
        lines.append(entry)
    return "\n".join(lines)

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actualizar_recordatorios_pasados()

    filtro = None
    if context.args:
        arg = context.args[0].lower()
        if arg in ("pendientes", "pendiente"): filtro = 0
        elif arg in ("hechos", "hecho"): filtro = 1
        elif arg in ("pasados", "pasado"): filtro = 2
        else:
            await update.message.reply_text("⚠️ Uso: /lista [pendientes|hechos|pasados]")
            return

    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT id, texto, fecha_hora, estado, aviso_previo FROM recordatorios"
        params = []
        if filtro is not None:
            query += " WHERE estado = ?"
            params.append(filtro)
        # Ordenamos por estado primero, y luego por fecha
        query += " ORDER BY estado, CASE WHEN fecha_hora IS NULL THEN 1 ELSE 0 END, fecha_hora"
        cursor.execute(query, params)
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios para este filtro.")
        return

    # --- NUEVA LÓGICA DE CONSTRUCCIÓN DEL MENSAJE ---

    # 1. Separamos los recordatorios en listas por categoría
    pendientes = [r for r in recordatorios if r[3] == 0]
    hechos = [r for r in recordatorios if r[3] == 1]
    pasados = [r for r in recordatorios if r[3] == 2]

    # 2. Construimos las secciones del mensaje solo para las listas que no están vacías
    secciones_mensaje = []
    if pendientes:
        titulo = f"*{ESTADOS[0]}:*"
        # 2. Usamos la nueva función centralizada
        items = formatear_lista_para_mensaje(pendientes, mostrar_info_aviso=True)
        secciones_mensaje.append(f"{titulo}\n{items}")
        
    if pasados:
        titulo = f"*{ESTADOS[2]}:*"
        items = formatear_lista_para_mensaje(pasados)
        secciones_mensaje.append(f"{titulo}\n{items}")

    if hechos:
        titulo = f"*{ESTADOS[1]}:*"
        items = formatear_lista_para_mensaje(hechos)
        secciones_mensaje.append(f"{titulo}\n{items}")

    mensaje_final = "\n\n".join(secciones_mensaje)

    if not mensaje_final:
        await update.message.reply_text("📭 No se encontraron recordatorios.")
        return

    await update.message.reply_text(mensaje_final, parse_mode="Markdown")
