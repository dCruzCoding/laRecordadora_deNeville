from telegram import Update
from telegram.ext import ContextTypes
from db import get_connection
from utils import construir_mensaje_lista_completa
from personalidad import get_text

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        query = "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone FROM recordatorios WHERE chat_id = ?"
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

    # Llama a la función universal de clasificación
    mensaje_final = construir_mensaje_lista_completa(chat_id, recordatorios, "📜 **Lista de Recordatorios** 📜\n")
    
    await update.message.reply_text(mensaje_final, parse_mode="Markdown")