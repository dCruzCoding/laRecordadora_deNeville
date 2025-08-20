from telegram import Update
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters
)
from db import resetear_base_de_datos
from avisos import cancelar_todos_los_avisos
from config import OWNER_ID  # <-- CAMBIO: Importamos tu ID de dueño

# Estado para la conversación de reseteo (no cambia)
CONFIRMACION_RESET = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Función de bienvenida, sin cambios."""
    await update.message.reply_text(
        "👵 ¡Ay criatura! Soy *La Recordadora*, tu abuela digital.\n"
        "Dime qué no quieres olvidar y yo te lo recordaré.\n\n"
        "Usa /ayuda para ver lo que puedo hacer.",
        parse_mode="Markdown"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la ayuda. El mensaje es dinámico dependiendo del usuario."""
    chat_id = update.effective_chat.id # <-- Obtenemos el ID del usuario
    
    # --- LÓGICA DINÁMICA ---
    
    # Empezamos con la parte del mensaje que es común para todos
    mensaje_ayuda_base = (
        "*📖 Ayuda de La Recordadora*\n\n"
        "Estos son los comandos disponibles:\n\n"
        "📌 /start – Mensaje de bienvenida.\n"
        "📌 /ayuda – Muestra este mensaje de ayuda.\n"
        "📌 /lista – Lista todos tus recordatorios.\n"
        "   ➡️ `/lista pendientes | hechos | pasados`\n"
        "📌 /recordar – Añadir un nuevo recordatorio.\n"
        "📌 /borrar – Borrar uno o varios de tus recordatorios.\n"
        "📌 /cambiar – Cambiar el estado de uno de tus recordatorios.\n"
        "📌 /configuracion – Cambiar tu *modo seguro*.\n"
        "📌 /cancelar – Cancela la acción en curso.\n"
    )
    
    # Si el usuario es el dueño, añadimos el comando de administrador
    if chat_id == OWNER_ID:
        mensaje_ayuda_final = mensaje_ayuda_base + "\n⚠️ /reset – BORRA TODOS los recordatorios (solo el creador).\n"
    else:
        mensaje_ayuda_final = mensaje_ayuda_base

    await update.message.reply_text(mensaje_ayuda_final, parse_mode="Markdown")

# --- COMANDO /RESET MODIFICADO ---

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia el proceso de reseteo, pidiendo confirmación.
    ¡Ahora solo funciona si el usuario es el dueño del bot!
    """
    # Mantenemos la comprobación de seguridad del reset por si acaso
    if update.effective_chat.id != OWNER_ID:
        await update.message.reply_text("⛔ Lo siento, este es un comando de mantenimiento y solo puede ser usado por mi creador.")
        return ConversationHandler.END

    # Si el ID es correcto, la función continúa como antes
    await update.message.reply_text(
        "🔥🔥🔥 *¡ATENCIÓN!* 🔥🔥🔥\n\n"
        "Estás a punto de borrar *TODOS* los recordatorios de la base de datos. "
        "Esta acción es *IRREVERSIBLE*.\n\n"
        "Para confirmar, escribe la palabra: `CONFIRMAR`",
        parse_mode="Markdown"
    )
    return CONFIRMACION_RESET

async def confirmar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verifica la confirmación y ejecuta el reseteo. Sin cambios."""
    if update.message.text.strip() == "CONFIRMAR":
        resetear_base_de_datos()
        cancelar_todos_los_avisos()
        await update.message.reply_text("✅ ¡Hecho! Todos los recordatorios han sido eliminados.")
    else:
        await update.message.reply_text("❌ Operación cancelada. Los recordatorios están a salvo.")
    
    return ConversationHandler.END

async def cancelar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para cancelar la operación. Sin cambios."""
    await update.message.reply_text("❌ Reseteo cancelado.")
    return ConversationHandler.END

# ConversationHandler 
reset_handler = ConversationHandler(
    entry_points=[CommandHandler("reset", reset_cmd)],
    states={
        CONFIRMACION_RESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_reset)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar_reset)],
)