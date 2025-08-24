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
from config import OWNER_ID  
from personalidad import get_text
from utils import manejar_cancelacion


async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la ayuda. El mensaje es dinámico dependiendo del usuario."""
    chat_id = update.effective_chat.id   # Obtenemos ID del user
    mensaje = get_text("ayuda_base")
    if chat_id == OWNER_ID:
        mensaje += get_text("ayuda_admin")
    await update.message.reply_text(mensaje, parse_mode="Markdown")

# Estado para la conversación de reseteo 
CONFIRMACION_RESET = range(1)

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia el proceso de reseteo, pidiendo confirmación.
    ¡Ahora solo funciona si el usuario es el dueño del bot!
    """
    if update.effective_chat.id != OWNER_ID:
        await update.message.reply_text(get_text("reset_denegado"))
        return ConversationHandler.END

    await update.message.reply_text(get_text("reset_aviso"), parse_mode="Markdown")
    return CONFIRMACION_RESET

async def confirmar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text.strip() == "CONFIRMAR":
        resetear_base_de_datos()
        cancelar_todos_los_avisos()
        await update.message.reply_text(get_text("reset_confirmado"))
    else:
        await update.message.reply_text(get_text("reset_cancelado"))
    
    return ConversationHandler.END

# ConversationHandler
reset_handler = ConversationHandler(
    entry_points=[CommandHandler("reset", reset_cmd)],
    states={
        CONFIRMACION_RESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_reset)]
    },
    fallbacks=[
        CommandHandler("cancelar", manejar_cancelacion)
    ]
)