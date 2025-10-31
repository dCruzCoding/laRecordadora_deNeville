# handlers/recordar_fijo.py
import re
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters

# Importaciones de nuestros módulos
from db import get_config, add_recordatorio_fijo
from avisos import programar_recordatorio_fijo_diario # Crearemos esta función en el siguiente paso
from utils import cancelar_conversacion, comando_inesperado
from personalidad import get_text

# --- Definición de Estados ---
PEDIR_DATOS = range(1)

async def recordar_fijo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada para la conversación de /recordar fijo."""
    await update.message.reply_text(
        "👵 Vas a fijar un recordatorio que se repetirá todos los días.\n\n"
        "Por favor, dime la hora y el texto con el formato `HH:MM * Texto del recordatorio`.\n\n"
        "Ejemplo: `08:30 * Tomar la poción multijugos`"
    )
    return PEDIR_DATOS

async def recibir_datos_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Procesa la entrada del usuario, guarda y programa el recordatorio fijo."""
    chat_id = update.effective_chat.id
    entrada = update.message.text

    # Usamos regex para separar la hora del texto
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)

    if not match:
        await update.message.reply_text("❗ ¡Formato incorrecto! Recuerda usar `HH:MM * Texto`.")
        return PEDIR_DATOS # Mantenemos al usuario en el mismo paso

    hora_str, texto = match.groups()

    # Validamos que la hora sea un formato válido
    try:
        # Esto es solo para validar, no guardamos el objeto datetime
        from datetime import datetime
        datetime.strptime(hora_str, "%H:%M")
    except ValueError:
        await update.message.reply_text(f"❗ La hora '{hora_str}' no es válida. ¡Inténtalo de nuevo!")
        return PEDIR_DATOS

    user_tz = get_config(chat_id, "user_timezone") or "UTC"

    # 1. Guardar en la nueva tabla de la base de datos
    fijo_id = add_recordatorio_fijo(chat_id, texto, hora_str, user_tz)

    # 2. Programar el job recurrente en el scheduler
    hora, minuto = map(int, hora_str.split(':'))
    programar_recordatorio_fijo_diario(chat_id, fijo_id, texto, hora, minuto, user_tz)

    await update.message.reply_text(
        f"✅ ¡Entendido! He fijado un recordatorio diario para las *{hora_str}* con el texto: _{texto}_",
        parse_mode="Markdown"
    )

    return ConversationHandler.END

# --- Construcción del ConversationHandler ---
recordar_fijo_handler = ConversationHandler(
    entry_points=[CommandHandler("recordar_fijo", recordar_fijo_cmd)],
    states={
        PEDIR_DATOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_datos_fijos)]
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
    # Nombramos el handler para evitar colisiones con otros si usas persistencia
    name="recordar_fijo_conv",
    persistent=False
)