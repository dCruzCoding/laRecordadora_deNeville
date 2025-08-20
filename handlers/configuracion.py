from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
# Ahora necesitamos get_config para mostrar el estado actual
from db import get_config, set_config
from utils import cancelar_conversacion
from personalidad import get_text

# Estados de la conversación (no cambian)
ELEGIR_NIVEL = range(1)

async def configuracion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia la conversación para cambiar la configuración del modo seguro del usuario.
    """
    chat_id = update.effective_chat.id # <-- CAMBIO: Obtenemos el chat_id del usuario
    
    # <-- CAMBIO: Leemos la configuración actual de ESTE usuario para mostrarla
    modo_seguro_actual = get_config(chat_id, "modo_seguro") or "0" # Por defecto es 0 si no existe
    
    mensaje_base = get_text("configuracion_pide_nivel", nivel=modo_seguro_actual)

    descripcion_niveles = (
        "\n\nElige un nuevo nivel (0-3):\n"
        "  `0` → 🔓 Sin confirmaciones. ¡A lo loco!\n"
        "  `1` → 🗑 Confirmar solo al *borrar*.\n"
        "  `2` → 🔄 Confirmar solo al *cambiar estado*.\n"
        "  `3` → 🔒 Confirmar ambos. Para los que se lo piensan dos veces."
    )

    await update.message.reply_text(mensaje_base + descripcion_niveles, parse_mode="Markdown")
    return ELEGIR_NIVEL

async def recibir_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe el nuevo nivel de modo seguro y lo guarda para el usuario específico.
    """
    nivel_str = update.message.text.strip()
    
    if nivel_str in ("0", "1", "2", "3"):
        chat_id = update.effective_chat.id # <-- Obtenemos el chat_id del usuario
        
        # Guardamos la configuración asociada a ESTE chat_id
        set_config(chat_id, "modo_seguro", nivel_str)
        
        mensaje_confirmacion = get_text("configuracion_confirmada", nivel=nivel_str) # <-- CAMBIO
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")

        return ConversationHandler.END
    else:
        await update.message.reply_text("⚠️ ¡Ese número no vale, criatura! Elige uno del 0 al 3.")
        return ELEGIR_NIVEL

# ConversationHandler
configuracion_handler = ConversationHandler(
    entry_points=[CommandHandler("configuracion", configuracion_cmd)],
    states={
        ELEGIR_NIVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nivel)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar_conversacion)],
)