from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from db import get_config, set_config

ELEGIR_MODO = range(1)

async def configuracion_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra la configuración actual y pide un nuevo valor."""
    modo_seguro = int(get_config("modo_seguro") or 0)
    texto_modo = (
        "0 → 🔓 Sin confirmaciones.\n"
        "1 → 🗑 Confirmar solo BORRAR.\n"
        "2 → 🔄 Confirmar solo CAMBIAR ESTADO.\n"
        "3 → 🔒 Confirmar ambos."
    )

    await update.message.reply_text(
        f"*⚙️ Configuración de Modo Seguro*\n\n"
        f"Valor actual: `{modo_seguro}`\n\n"
        f"{texto_modo}\n\n"
        f"✏️ Escribe el nuevo valor (0, 1, 2 o 3) o /cancelar para salir.",
        parse_mode="Markdown"
    )
    return ELEGIR_MODO

async def recibir_modo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    valor = update.message.text.strip()
    if valor not in ("0", "1", "2", "3"):
        await update.message.reply_text("⚠️ Valor inválido. Debe ser 0, 1, 2 o 3.")
        return ELEGIR_MODO

    set_config("modo_seguro", valor)
    await update.message.reply_text(f"✅ Modo seguro actualizado a {valor}.")
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Configuración cancelada.")
    return ConversationHandler.END

configuracion_handler = ConversationHandler(
    entry_points=[CommandHandler("configuracion", configuracion_cmd)],
    states={
        ELEGIR_MODO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_modo)],
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
