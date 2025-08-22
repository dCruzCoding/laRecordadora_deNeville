from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
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
from personalidad import get_text, TEXTOS
from timezonefinderL import TimezoneFinder
from geopy.geocoders import Nominatim
from utils import manejar_cancelacion

# Estados para la nueva conversación de bienvenida
PIDE_MODO_SEGURO, PIDE_ZONA_HORARIA = range(2)

# --- COMANDO /INFO ---
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra de nuevo la guía de uso de La Recordadora."""
    await update.message.reply_text(get_text("onboarding_informacion"), parse_mode="Markdown")


# --- NUEVA CONVERSACIÓN /START ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia la conversación de bienvenida si es la primera vez."""
    chat_id = update.effective_chat.id
    onboarding_completo = get_config(chat_id, "onboarding_completo")

    if onboarding_completo:
        await update.message.reply_text(get_text("start"))
        return ConversationHandler.END

    # --- INICIO DEL ONBOARDING ---
    # 1. Presentación de Augusta
    await update.message.reply_text(get_text("onboarding_presentacion"), parse_mode="Markdown")
    
    # 2. Guía de uso (la misma que en /informacion)
    await update.message.reply_text(get_text("onboarding_informacion"), parse_mode="Markdown")

    # 3. Pedimos la primera configuración: Modo Seguro
    mensaje_modo_seguro = get_text("onboarding_pide_modo_seguro", nivel='0')
    await update.message.reply_text(mensaje_modo_seguro, parse_mode="Markdown")
    return PIDE_MODO_SEGURO

async def recibir_modo_seguro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe el modo seguro y pide la zona horaria."""
    nivel_str = update.message.text.strip()
    chat_id = update.effective_chat.id
    
    if nivel_str in ("0", "1", "2", "3"):
        set_config(chat_id, "modo_seguro", nivel_str)

        descripcion_nivel = TEXTOS["niveles_modo_seguro"].get(nivel_str, "Desconocido")

        mensaje_confirmacion = get_text(
            "configuracion_confirmada", 
            nivel=nivel_str, 
            descripcion=descripcion_nivel
        )
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")


        # 4. Pedimos la segunda configuración: Zona Horaria
        location_keyboard = [[KeyboardButton("📍 Detectar mi Zona Horaria Automáticamente", request_location=True)]]
        reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True, one_time_keyboard=True)
        await update.message.reply_text(get_text("onboarding_pide_zona_horaria"), reply_markup=reply_markup)
        return PIDE_ZONA_HORARIA
    else:
        await update.message.reply_text(get_text("error_modo_invalido"))
        return PIDE_MODO_SEGURO

async def recibir_zona_horaria_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la zona horaria, la guarda y finaliza el onboarding."""
    chat_id = update.effective_chat.id
    user_timezone = None
    
    # Reutilizamos la misma lógica que el comando /timezone

    if update.message.location:
        # Método automático (ubicación)
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        tf = TimezoneFinder()
        user_timezone = tf.timezone_at(lng=lon, lat=lat)

    elif update.message.text:
        # Método manual (texto)
        try:
            geolocator = Nominatim(user_agent="la_recordadora_bot")
            location = geolocator.geocode(update.message.text)
            if location:
                tf = TimezoneFinder()
                user_timezone = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            else:
                await update.message.reply_text("🤔 Hmph, no encuentro esa ciudad. ¿Estás seguro de que la has escrito bien? Inténtalo de nuevo.")
                return PIDE_ZONA_HORARIA
        except Exception as e:
            print(f"Error con geopy: {e}")
            await update.message.reply_text("👵 ¡Ay, criatura! Ha habido un problema con mis mapas mágicos. Inténtalo de nuevo con otra ciudad.")
            return PIDE_ZONA_HORARIA


    if user_timezone:
        set_config(chat_id, "user_timezone", user_timezone)
        set_config(chat_id, "onboarding_completo", "1")
        
        mensaje_final = get_text("onboarding_finalizado", timezone=user_timezone)
        await update.message.reply_text(
            mensaje_final,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    
    # Si algo falló, le volvemos a preguntar
    await update.message.reply_text("🤔 Hmph, algo ha fallado. Inténtalo de nuevo, por favor.")
    return PIDE_ZONA_HORARIA

# Handler para la conversación de bienvenida
start_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        PIDE_MODO_SEGURO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_modo_seguro)],
        PIDE_ZONA_HORARIA: [MessageHandler(filters.LOCATION | filters.TEXT & ~filters.COMMAND, recibir_zona_horaria_onboarding)]
    },
    fallbacks=[
        CommandHandler("cancelar", manejar_cancelacion)
    ]
)

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