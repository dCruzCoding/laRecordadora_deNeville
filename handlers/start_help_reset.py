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

# Estado para la conversación de reseteo
CONFIRMACION_RESET = range(1)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👵 ¡Ay criatura! Soy *La Recordadora*, tu abuela digital.\n"
        "Dime qué no quieres olvidar y yo te lo recordaré.\n\n"
        "Usa /ayuda para ver lo que puedo hacer.",
        parse_mode="Markdown"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "*📖 Ayuda de La Recordadora*\n\n"
        "Estos son los comandos disponibles:\n\n"
        "📌 */start* – Mensaje de bienvenida.\n"
        "📌 */ayuda* – Muestra este mensaje de ayuda.\n"
        "📌 */lista* – Lista todos los recordatorios.\n"
        "   ➡️ `/lista pendientes | hechos | pasados`\n"
        "📌 */recordar* – Añadir un nuevo recordatorio.\n"
        "📌 */borrar* – Borrar uno o varios recordatorios por ID.\n"
        "📌 */cambiar* – Cambiar el estado (pendiente ↔ hecho) de uno o varios recordatorios por ID.\n"
        "📌 */configuracion* – Cambiar el *modo seguro*:\n"
        "📌 */cancelar* – Cancela la acción en curso.\n"
        "⚠️ */reset* – BORRA TODOS los recordatorios.\n",
        parse_mode="Markdown"
    )


async def reset_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia el proceso de reseteo pidiendo confirmación."""
    await update.message.reply_text(
        "🔥🔥🔥 *¡ATENCIÓN!* 🔥🔥🔥\n\n"
        "Estás a punto de borrar *TODOS* los recordatorios de la base de datos. "
        "Esta acción es *IRREVERSIBLE*.\n\n"
        "Para confirmar, escribe la palabra: `CONFIRMAR`. "
        "O escribe /cancelar para salir.",
        parse_mode="Markdown"
    )
    return CONFIRMACION_RESET

async def confirmar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Verifica la confirmación y ejecuta el reseteo."""
    if update.message.text.strip() == "CONFIRMAR":
        # Ejecutamos las funciones de limpieza
        resetear_base_de_datos()
        cancelar_todos_los_avisos()
        
        await update.message.reply_text("*¡Hecho!* 🧹🧹🧹🧹🧹🧹🧹🧹🧹🧹🧹\n Todos tus recordatorios han sido eliminados.")
    else:
        await update.message.reply_text("❌ Operación cancelada. Tus recordatorios están a salvo.")
    
    return ConversationHandler.END

async def cancelar_reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para cancelar la operación."""
    await update.message.reply_text("❌ Reseteo cancelado.")
    return ConversationHandler.END

# Creamos el ConversationHandler para el comando /reset
reset_handler = ConversationHandler(
    entry_points=[CommandHandler("reset", reset_cmd)],
    states={
        CONFIRMACION_RESET: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_reset)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar_reset)],
)