from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from db import get_connection, get_config
from utils import cancelar_conversacion, formatear_fecha_para_mensaje, comando_inesperado, enviar_lista_interactiva
from avisos import cancelar_avisos
from handlers.lista import TITULOS
from personalidad import get_text

ELEGIR_ID, CONFIRMAR = range(2)

async def borrar_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Punto de entrada para /borrar."""
    if context.args:
        return await _procesar_ids(update, context, context.args)
    
    # --- ¡LÓGICA DE LISTA REEMPLAZADA! ---
    # Simplemente llamamos a la función universal con nuestro contexto
    await enviar_lista_interactiva(
        update, context, context_key="borrar", titulos=TITULOS["borrar"]
    )
    
    # Le decimos al ConversationHandler que ahora espere el ID del usuario
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
    Función centralizada. Ahora busca los detalles de los recordatorios
    y los muestra en la pregunta de confirmación.
    """
    chat_id = update.effective_chat.id
    recordatorios_a_borrar_info = []
    
    # --- ¡NUEVA LÓGICA DE BÚSQUEDA! ---
    with get_connection() as conn:
        cursor = conn.cursor()
        for user_id_str in ids:
            try:
                user_id = int(user_id_str.replace("#", ""))
                cursor.execute(
                    "SELECT user_id, texto, fecha_hora FROM recordatorios WHERE user_id = ? AND chat_id = ?",
                    (user_id, chat_id)
                )
                row = cursor.fetchone()
                if row:
                    recordatorios_a_borrar_info.append(row)
            except (ValueError, TypeError):
                pass

    if not recordatorios_a_borrar_info:
        await update.message.reply_text(get_text("error_no_id"))
        return ConversationHandler.END

    # Guardamos tanto los IDs como la información detallada para usarla después
    context.user_data["ids_a_borrar"] = [str(r[0]) for r in recordatorios_a_borrar_info]
    context.user_data["info_a_borrar"] = recordatorios_a_borrar_info
    
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (1, 3):
        # --- MENSAJE DE CONFIRMACIÓN MEJORADO ---
        mensaje_lista = []
        for user_id, texto, fecha_iso in recordatorios_a_borrar_info:
            fecha_str = formatear_fecha_para_mensaje(fecha_iso)
            mensaje_lista.append(f"  - `#{user_id}`: _{texto}_ ({fecha_str})")
            
        mensaje_confirmacion = (
            f"👵 ¡Quieto ahí! Vas a borrar permanentemente lo siguiente:\n\n"
            f"{'\n'.join(mensaje_lista)}\n\n"
            "¿Estás completamente seguro? Escribe `SI` para confirmar."
        )
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRMAR
    
    return await ejecutar_borrado(update, context)


async def confirmar_borrado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Se activa después de que el usuario escribe 'SI'."""
    if update.message.text.strip().upper() == "SI":
        return await ejecutar_borrado(update, context)
    
    return await cancelar_conversacion(update, context)
    

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
        info_borrada = context.user_data.get("info_a_borrar", [])
        
        if len(info_borrada) == 1:
            recordatorio = info_borrada[0]
            mensaje_exito = f"🗑️ ¡Listo! El recordatorio `#{recordatorio[0]}` ('_{recordatorio[1]}_') ha sido borrado."
        else:
            nombres_borrados = [f"`#{r[0]}`" for r in info_borrada]
            mensaje_exito = f"🗑️ ¡Hecho! Los recordatorios {', '.join(nombres_borrados)} han sido borrados."
            
        await update.message.reply_text(mensaje_exito, parse_mode="Markdown")
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
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) # <-- Maneja las interrupciones
    ],
)