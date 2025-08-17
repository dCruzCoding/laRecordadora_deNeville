from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from db import get_connection, get_config, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje
from avisos import cancelar_avisos
from config import ESTADOS

ELEGIR_ID, CONFIRMAR = range(2)

async def borrar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para /borrar.
    Maneja tanto el borrado directo con argumentos como el modo conversacional.
    """
    actualizar_recordatorios_pasados()

    if context.args:
        # CASO 1: El usuario proveyó IDs (ej: /borrar AG01 AG02)
        ids = context.args
        context.user_data["ids_a_borrar"] = ids
        
        modo_seguro = int(get_config("modo_seguro") or 0)
        if modo_seguro in (1, 3):
            # Modo seguro activado: pedimos confirmación y pasamos al estado CONFIRMAR
            await update.message.reply_text(
                f"⚠️ Vas a borrar {len(ids)} recordatorio(s). Escribe 'SI' para confirmar o cualquier otra cosa para cancelar."
            )
            return CONFIRMAR
        else:
            # Modo seguro desactivado: ejecutamos directamente y terminamos la conversación
            return await ejecutar_borrado(update, ids)
    else:
        # CASO 2: El usuario no proveyó IDs (ej: /borrar)
        # Mostramos la lista y pasamos al estado ELEGIR_ID para que el usuario responda.
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, texto, fecha_hora, estado, aviso_previo FROM recordatorios ORDER BY CASE WHEN fecha_hora IS NULL THEN 1 ELSE 0 END, fecha_hora")
            recordatorios = cursor.fetchall()

        if not recordatorios:
            await update.message.reply_text("📭 No tienes recordatorios guardados.")
            return ConversationHandler.END

        pendientes = [r for r in recordatorios if r[3] == 0]
        hechos = [r for r in recordatorios if r[3] == 1]
        pasados = [r for r in recordatorios if r[3] == 2]

        secciones_mensaje = []
        if pendientes:
            secciones_mensaje.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(pendientes)}")
        if pasados:
            secciones_mensaje.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(pasados)}")
        if hechos:
            secciones_mensaje.append(f"*{ESTADOS[1]}:*\n{formatear_lista_para_mensaje(hechos)}")

        mensaje_final = "*BORRAR 🗑 :*\n\n" + "\n\n".join(secciones_mensaje)
        mensaje_final += "\n\n✏️ Escribe el/los ID que quieras borrar (separados por espacio) o /cancelar si quieres salir:"
        
        await update.message.reply_text(mensaje_final, parse_mode="Markdown")
        return ELEGIR_ID


async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text("⚠️ No escribiste ningún ID.")
        return ELEGIR_ID

    context.user_data["ids_a_borrar"] = ids
    modo_seguro = int(get_config("modo_seguro") or 0)
    if modo_seguro in (1, 3):
        await update.message.reply_text(
            f"⚠️ Vas a borrar {len(ids)} recordatorio(s). Escribe 'SI' para confirmar o cualquier otra cosa para cancelar."
        )
        return CONFIRMAR
    return await ejecutar_borrado(update, ids)

async def confirmar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "SI":
        ids = context.user_data.get("ids_a_borrar", [])
        return await ejecutar_borrado(update, ids)
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ejecutar_borrado(update: Update, ids):
    with get_connection() as conn:
        cursor = conn.cursor()
        borrados = []
        for rid in ids:
            cursor.execute("DELETE FROM recordatorios WHERE id = ?", (rid,))
            if cursor.rowcount > 0:
                borrados.append(rid)
        conn.commit()
    if borrados:
        await update.message.reply_text(f"🗑 Borrados: {', '.join(borrados)}")
        for rid in borrados:
            cancelar_avisos(rid)
    else:
        await update.message.reply_text("⚠️ No se encontró ningún ID válido.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

borrar_handler = ConversationHandler(
    entry_points=[CommandHandler("borrar", borrar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_borrado)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
