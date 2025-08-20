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

# Estados de la conversación (no cambian)
ELEGIR_NIVEL = range(1)

async def configuracion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Inicia la conversación para cambiar la configuración del modo seguro del usuario.
    """
    chat_id = update.effective_chat.id # <-- CAMBIO: Obtenemos el chat_id del usuario
    
    # <-- CAMBIO: Leemos la configuración actual de ESTE usuario para mostrarla
    modo_seguro_actual = get_config(chat_id, "modo_seguro") or "0" # Por defecto es 0 si no existe
    
    mensaje = (
        f"⚙️ *Configuración del Modo Seguro*\n\n"
        f"El modo seguro te pide confirmación antes de borrar o cambiar el estado de un recordatorio.\n\n"
        f"Tu nivel actual es: *{modo_seguro_actual}*\n\n"
        "Elige un nuevo nivel (0-3):\n"
        "  `0` → 🔓 Sin confirmaciones.\n"
        "  `1` → 🗑 Confirmar solo al *borrar*.\n"
        "  `2` → 🔄 Confirmar solo al *cambiar estado*.\n"
        "  `3` → 🔒 Confirmar ambos."
    )
    
    await update.message.reply_text(mensaje, parse_mode="Markdown")
    return ELEGIR_NIVEL

async def recibir_nivel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe el nuevo nivel de modo seguro y lo guarda para el usuario específico.
    """
    nivel_str = update.message.text.strip()
    
    if nivel_str in ("0", "1", "2", "3"):
        chat_id = update.effective_chat.id # <-- CAMBIO: Obtenemos el chat_id del usuario
        
        # <-- CAMBIO: Guardamos la configuración asociada a ESTE chat_id
        set_config(chat_id, "modo_seguro", nivel_str)
        
        await update.message.reply_text(f"✅ Modo seguro establecido en: *{nivel_str}*", parse_mode="Markdown")
        return ConversationHandler.END
    else:
        await update.message.reply_text("⚠️ Nivel no válido. Elige un número del 0 al 3.")
        return ELEGIR_NIVEL

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancela la operación de configuración."""
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

# El ConversationHandler no cambia
configuracion_handler = ConversationHandler(
    entry_points=[CommandHandler("configuracion", configuracion_cmd)],
    states={
        ELEGIR_NIVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_nivel)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)