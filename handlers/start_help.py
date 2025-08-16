from telegram import Update
from telegram.ext import ContextTypes

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
        "   ➡️ `/lista pendientes` – Solo los pendientes.\n"
        "   ➡️ `/lista hechos` – Solo los completados.\n"
        "📌 */recordar* – Añadir un nuevo recordatorio.\n"
        "📌 */borrar* – Borrar uno o varios recordatorios por ID.\n"
        "📌 */cambiar* – Cambiar el estado (pendiente ↔ hecho) de uno o varios recordatorios por ID.\n"
        "📌 */configuracion* – Cambiar el *modo seguro*:\n"
        "   0 → 🔓 Sin confirmaciones.\n"
        "   1 → 🗑 Confirmar solo BORRAR.\n"
        "   2 → 🔄 Confirmar solo CAMBIAR ESTADO.\n"
        "   3 → 🔒 Confirmar ambos.\n"
        "📌 */cancelar* – Cancela la acción en curso.\n",
        parse_mode="Markdown"
    )
