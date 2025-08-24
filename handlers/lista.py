from telegram import Update
from telegram.ext import ContextTypes
from db import get_connection, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje
from datetime import datetime, timedelta
from config import ESTADOS  # Importamos los estados desde config
from personalidad import get_text

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    actualizar_recordatorios_pasados()
    chat_id = update.effective_chat.id

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
        query = "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo FROM recordatorios WHERE chat_id = ?"
        params = [chat_id]
        if filtro is not None:
            query += " AND estado = ?"
            params.append(filtro)
        query += " ORDER BY estado, user_id"
        cursor.execute(query, tuple(params))
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text(get_text("lista_vacia"))
        return

    pendientes = [r for r in recordatorios if r[5] == 0]
    hechos = [r for r in recordatorios if r[5] == 1]
    pasados = [r for r in recordatorios if r[5] == 2]

    secciones_mensaje = []
    if pendientes:
        titulo = f"*{ESTADOS[0]}:*"
        # Usamos la nueva función centralizada
        items = formatear_lista_para_mensaje(chat_id, pendientes, mostrar_info_aviso=True)
        secciones_mensaje.append(f"{titulo}\n{items}")
        
    if pasados:
        titulo = f"*{ESTADOS[2]}:*"
        items = formatear_lista_para_mensaje(chat_id, pasados)
        secciones_mensaje.append(f"{titulo}\n{items}")

    if hechos:
        titulo = f"*{ESTADOS[1]}:*"
        items = formatear_lista_para_mensaje(chat_id, hechos)
        secciones_mensaje.append(f"{titulo}\n{items}")
        
    mensaje_final = "\n\n".join(secciones_mensaje)

    if pendientes:
        mensaje_final += "\n\n---\n_Venga, a trabajar. ¡Que no se diga que los Longbottom son unos vagos!_"

    await update.message.reply_text(mensaje_final, parse_mode="Markdown")