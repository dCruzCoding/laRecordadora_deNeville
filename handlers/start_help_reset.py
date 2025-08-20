from telegram import Update
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters
)
from db import resetear_base_de_datos, get_config, set_config
from avisos import cancelar_todos_los_avisos
from config import OWNER_ID  
from personalidad import get_text
from utils import cancelar_conversacion

# Estado para la conversación de reseteo (no cambia)
CONFIRMACION_RESET = range(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Da la bienvenida al usuario. Muestra un mensaje largo la primera vez
    y mensajes cortos y aleatorios las veces siguientes.
    """
    chat_id = update.effective_chat.id
    
    # Comprobamos en la DB si el usuario ya ha iniciado el bot antes
    usuario_ya_iniciado = get_config(chat_id, "usuario_iniciado")

    if not usuario_ya_iniciado:
        # Es la primera vez que este usuario inicia el bot
        mensaje = get_text("start_inicio")
        # Marcamos en la DB que el usuario ya ha recibido la bienvenida
        set_config(chat_id, "usuario_iniciado", "1")
    else:
        # El usuario ya es un viejo conocido, le damos un saludo aleatorio
        mensaje = get_text("start")
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la ayuda. El mensaje es dinámico dependiendo del usuario."""
    chat_id = update.effective_chat.id   # Obtenemos ID del user
    mensaje = get_text("ayuda_base")
    if chat_id == OWNER_ID:
        mensaje += get_text("ayuda_admin")
    await update.message.reply_text(mensaje, parse_mode="Markdown")


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
    fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
)