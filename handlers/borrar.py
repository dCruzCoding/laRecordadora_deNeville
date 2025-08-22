# handlers/borrar.py

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from db import get_connection, get_config, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje, manejar_cancelacion
from avisos import cancelar_avisos
from config import ESTADOS
from personalidad import get_text

ELEGIR_ID, CONFIRMAR = range(2)

async def borrar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /borrar."""
    actualizar_recordatorios_pasados()

    if context.args:
        # Modo rápido: el usuario ya proveyó los IDs.
        # Pasamos a la función de procesamiento.
        return await _procesar_ids(update, context, context.args)
    
    # Modo interactivo: mostramos la lista.
    chat_id = update.effective_chat.id
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo FROM recordatorios WHERE chat_id = ? ORDER BY estado, user_id", 
            (chat_id,)
        )
        recordatorios = cursor.fetchall()

    if not recordatorios:
        await update.message.reply_text("📭 No tienes recordatorios para borrar.")
        return ConversationHandler.END

    pendientes = [r for r in recordatorios if r[5] == 0]
    hechos = [r for r in recordatorios if r[5] == 1]
    pasados = [r for r in recordatorios if r[5] == 2]

    secciones_mensaje = []
    if pendientes:
        secciones_mensaje.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(pendientes)}")
    if pasados:
        secciones_mensaje.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(pasados)}")
    if hechos:
        secciones_mensaje.append(f"*{ESTADOS[1]}:*\n{formatear_lista_para_mensaje(hechos)}")

    mensaje_final = "*BORRAR 🗑 :*\n\n" + "\n\n".join(secciones_mensaje)
    mensaje_final += "\n\n✏️ Escribe el/los ID que quieras borrar (separados por espacio y sin #) o /cancelar si quieres salir:"
    
    await update.message.reply_text(mensaje_final, parse_mode="Markdown")
    return ELEGIR_ID

async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe los IDs después de que el usuario vea la lista."""
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text(get_text("error_no_id"))
        return ELEGIR_ID
    
    # Pasamos a la misma función de procesamiento.
    return await _procesar_ids(update, context, ids)

async def _procesar_ids(update: Update, context: ContextTypes.DEFAULT_TYPE, ids: list):
    """
    Función centralizada. Guarda los IDs y decide si pedir confirmación
    basándose en el modo_seguro.
    """
    chat_id = update.effective_chat.id
    context.user_data["ids_a_borrar"] = ids
    
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (1, 3):
        mensaje_confirmacion = get_text("pregunta_confirmar_borrado", count=len(ids))
        await update.message.reply_text(mensaje_confirmacion)
        return CONFIRMAR
    
    # Si no se necesita confirmación, ejecutamos el borrado directamente.
    return await ejecutar_borrado(update, context)

async def confirmar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se activa después de que el usuario escribe 'SI'."""
    if update.message.text.strip().upper() == "SI":
        return await ejecutar_borrado(update, context)
    else:
        # 1. Enviamos un mensaje de cancelación con la personalidad del bot
        await update.message.reply_text(get_text("cancelar"))
        
        # 2. Limpiamos los datos de la conversación
        if context.user_data:
            context.user_data.clear()
        
        return ConversationHandler.END
    

async def ejecutar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lógica final de borrado."""
    chat_id = update.effective_chat.id
    ids_a_borrar = context.user_data.get("ids_a_borrar", [])
    borrados_msg_list = []
    
    with get_connection() as conn:
        cursor = conn.cursor()
        for user_id_str in ids_a_borrar:
            try:
                user_id = int(user_id_str.replace("#", ""))
                cursor.execute("SELECT id FROM recordatorios WHERE user_id = ? AND chat_id = ?", (user_id, chat_id))
                row = cursor.fetchone()
                
                if row:
                    recordatorio_id_global = row[0]
                    cursor.execute("DELETE FROM recordatorios WHERE id = ?", (recordatorio_id_global,))
                    if cursor.rowcount > 0:
                        borrados_msg_list.append(f"#{user_id}")
                        cancelar_avisos(str(recordatorio_id_global))
            except (ValueError, TypeError):
                pass
        conn.commit()
    
    if borrados_msg_list:
        mensaje_exito = get_text("confirmacion_borrado", ids=', '.join(borrados_msg_list)) 
        await update.message.reply_text(mensaje_exito)
    else:
        await update.message.reply_text(get_text("error_no_id")) 
    
    context.user_data.clear()
    return ConversationHandler.END

# El ConversationHandler apunta a la función de cancelar centralizada
borrar_handler = ConversationHandler(
    entry_points=[CommandHandler("borrar", borrar_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_borrado)]
    },
    fallbacks=[
        CommandHandler("cancelar", manejar_cancelacion)
    ]
)