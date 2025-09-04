# handlers/help_reset.py
"""
Módulo para los comandos de ayuda (/ayuda) y de reseteo (/reset).

Contiene dos funcionalidades distintas:
- /ayuda: Un comando informativo simple y accesible para todos los usuarios.
- /reset: Un comando administrativo peligroso, protegido para ser usado
          únicamente por el propietario del bot (OWNER_ID).
"""

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

from db import resetear_base_de_datos
from avisos import cancelar_todos_los_avisos
from config import OWNER_ID  
from personalidad import get_text
from utils import cancelar_conversacion, comando_inesperado

# --- ESTADO PARA LA CONVERSACIÓN DE RESETEO ---
CONFIRMACION_RESET = 0 # Usar 0 es más explícito que range(1) para un solo estado


# =============================================================================
# COMANDO /ayuda
# =============================================================================

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Muestra la lista de comandos. El mensaje es dinámico: los usuarios
    normales ven los comandos básicos, mientras que el propietario del bot
    ve también los comandos de administrador.
    """
    chat_id = update.effective_chat.id
    mensaje = get_text("ayuda_base")
    # Se añade la sección de administrador solo si el ID del usuario coincide con el del propietario.
    if chat_id == OWNER_ID:
        mensaje += get_text("ayuda_admin")
    await update.message.reply_text(mensaje, parse_mode="Markdown")


# =============================================================================
# CONVERSACIÓN DE /reset
# =============================================================================

async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada para la conversación de reseteo.
    Verifica si el usuario es el propietario antes de continuar.
    """
    # --- ¡Mecanismo de seguridad CRÍTICO! ---
    # Se comprueba que el ID del usuario que ejecuta el comando es el OWNER_ID definido en config.py.
    if update.effective_chat.id != OWNER_ID:
        await update.message.reply_text(get_text("reset_denegado"))
        # Si no es el propietario, la conversación termina inmediatamente.
        return ConversationHandler.END

    # Si es el propietario, se pide la confirmación.
    await update.message.reply_text(get_text("reset_aviso"), parse_mode="Markdown")
    return CONFIRMACION_RESET


async def confirmar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Segundo paso de la conversación. Espera la palabra 'CONFIRMAR'.
    Si la recibe, ejecuta el reseteo. Si no, cancela.
    """
    # --- Validación robusta (insensible a mayúsculas/minúsculas) ---
    if update.message.text.strip().upper() == "CONFIRMAR":
        # Ejecuta las dos acciones de reseteo: vaciar la DB y limpiar el scheduler.
        resetear_base_de_datos()
        cancelar_todos_los_avisos()
        await update.message.reply_text(get_text("reset_confirmado"))
    else:
        # Si el usuario escribe cualquier otra cosa, se asume que ha cancelado.
        await update.message.reply_text(get_text("reset_cancelado"))
    
    # La conversación termina en ambos casos.
    return ConversationHandler.END


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
reset_handler = ConversationHandler(
    entry_points=[CommandHandler("reset", reset_cmd)],
    states={
        CONFIRMACION_RESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_reset)]
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)