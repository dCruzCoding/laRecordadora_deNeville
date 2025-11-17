# handlers/start_onboarding.py
"""
Módulo para la bienvenida de nuevos usuarios (/start) y el comando /info.

Contiene un ConversationHandler que guía a los nuevos usuarios a través de
un proceso de onboarding, configurando sus preferencias iniciales (Modo Seguro,
Zona Horaria, Resumen Diario).
También proporciona el comando /info para que los usuarios recurrentes puedan
revisar las instrucciones de uso.
"""

from telegram import Update, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from timezonefinderL import TimezoneFinder
from geopy.geocoders import Nominatim

from db import get_config, set_config
from personality import get_text, TEXTS
from utils import cancel_conversation, unexpected_command, normalize_text
from daily_brief import schedule_daily_brief

# --- DEFINICIÓN DE ESTADOS ---
(
    ONBOARDING_SAFE_MODE, ONBOARDING_TZ_ASK_METHOD,
    ONBOARDING_TZ_ASK_LOCATION, ONBOARDING_TZ_ASK_CITY,
    ONBOARDING_CONFIRM_CITY
) = range(5)


# =============================================================================
# COMANDO INDEPENDIENTE /info
# =============================================================================

async def info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Muestra de nuevo la guía de uso de La Recordadora."""
    await update.message.reply_text(get_text("onboarding_informacion"), parse_mode="Markdown")


# =============================================================================
# LÓGICA DE LA CONVERSACIÓN DE ONBOARDING (/start)
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Punto de entrada de la conversación.
    Si es un usuario nuevo, inicia el onboarding. Si no, envía un saludo.
    """
    chat_id = update.effective_chat.id
    if get_config(chat_id, "onboarding_completo"):
        await update.message.reply_text(get_text("start"))
        return ConversationHandler.END

    # --- INICIO DEL FLUJO DE ONBOARDING ---
    await update.message.reply_text(get_text("onboarding_presentacion"), parse_mode="Markdown")
    await update.message.reply_text(get_text("onboarding_informacion"), parse_mode="Markdown")

    # Pedimos la primera configuración: Modo Seguro
    keyboard = [
        [InlineKeyboardButton("🔓 Nivel 0", callback_data="onboarding_safe_mode:0"),
         InlineKeyboardButton("🗑️ Nivel 1", callback_data="onboarding_safe_mode:1")],
        [InlineKeyboardButton("🔄 Nivel 2", callback_data="onboarding_safe_mode:2"),
         InlineKeyboardButton("🔒 Nivel 3", callback_data="onboarding_safe_mode:3")],
    ]
    await update.message.reply_text(
        get_text("onboarding_pide_modo_seguro", level='0 (por defecto)'),
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ONBOARDING_SAFE_MODE


async def onboarding_receive_safe_mode(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso 2: Guarda el Modo Seguro y pide el método para la Zona Horaria."""
    query = update.callback_query
    await query.answer()
    # --- OBTENEMOS EL CHAT ID CORRECTAMENTE ---
    chat_id = query.message.chat_id

    level_str = query.data.split(":")[1]
    set_config(chat_id, "modo_seguro", level_str)

    description_level = TEXTS["niveles_modo_seguro"].get(level_str, "Desconocido")
    await query.edit_message_text(
        get_text("ajustes_confirmados", level=level_str, description=description_level),
        parse_mode="Markdown"
    )

    keyboard = [
        [InlineKeyboardButton("🪄 Automático (con ubicación)", callback_data="onboarding_tz_auto")],
        [InlineKeyboardButton("✍️ Manual (escribir ciudad)", callback_data="onboarding_tz_manual")],
    ]
    await context.bot.send_message(
        chat_id=chat_id,
        text=get_text("onboarding_pide_zona_horaria"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ONBOARDING_TZ_ASK_METHOD

async def onboarding_tz_method_automatic(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prepara para recibir una ubicación durante el onboarding."""
    query = update.callback_query
    await query.answer()

    # Creamos el teclado de respuesta para pedir la ubicación
    location_keyboard = [[KeyboardButton("📍 Compartir mi Ubicación Actual", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(location_keyboard, resize_keyboard=True, one_time_keyboard=True)

    await query.edit_message_text(text=get_text("timezone_pide_ubicacion"))
    # Necesitamos enviar un nuevo mensaje para poder adjuntar el ReplyKeyboard
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="Pulsa el botón que ha aparecido abajo 👇",
        reply_markup=reply_markup
    )

    return ONBOARDING_TZ_ASK_LOCATION

async def onboarding_tz_method_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Se activa cuando el usuario elige el método manual durante el onboarding.
    Prepara al bot para recibir texto.
    """
    query = update.callback_query
    await query.answer()
    
    # Editamos el mensaje anterior (el que tenía los botones [Auto]/[Manual])
    # para que ahora contenga la instrucción de escribir.
    await query.edit_message_text(text=get_text("timezone_pide_ciudad"))
    
    # Le decimos al ConversationHandler que pase al estado de "esperar ciudad".
    return ONBOARDING_TZ_ASK_CITY

async def onboarding_receive_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso final (automático): Recibe la ubicación y finaliza el onboarding."""
    tf = TimezoneFinder()
    user_timezone = tf.timezone_at(lng=update.message.location.longitude, lat=update.message.location.latitude)

    if user_timezone:
        await _ending_onboarding(update, context, user_timezone)
    else:
        await update.message.reply_text(
            "👵 ¡Vaya! No he podido determinar tu zona horaria. Inténtalo manualmente desde /ajustes.",
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END


async def onboarding_receive_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Maneja la recepción de un texto (ciudad) durante el onboarding.
    Si encuentra la ciudad, pide confirmación.
    """
    ciudad = update.message.text
    try:
        geolocator = Nominatim(user_agent="la_recordadora_bot")
        location = geolocator.geocode(ciudad, language='es')
        
        if location:
            tf = TimezoneFinder()
            user_timezone_found = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            
            # Guardamos la zona horaria encontrada temporalmente para el siguiente paso
            context.user_data["onboarding_tz_to_confirm"] = user_timezone_found
            
            mensaje_pregunta = get_text(
                "timezone_pregunta_confirmacion", 
                ciudad=location.address, 
                timezone=user_timezone_found
            )
            await update.message.reply_text(mensaje_pregunta, parse_mode="Markdown")
            
            # Pasamos al estado de esperar la confirmación (SI/NO)
            return ONBOARDING_CONFIRM_CITY
        else:
            # La ciudad no se encontró
            await update.message.reply_text(get_text("timezone_no_encontrada"))
            # Le permitimos intentarlo de nuevo
            return ONBOARDING_TZ_ASK_CITY
            
    except Exception as e:
        print(f"Error con geopy: {e}")
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ONBOARDING_TZ_ASK_CITY

async def onboarding_confirm_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso final (manual): Recibe el SÍ/NO y finaliza el onboarding."""
    processed_input = normalize_text(update.message.text.strip())

    if processed_input.startswith("si"):
        user_timezone = context.user_data.get("onboarding_tz_to_confirm")
        if user_timezone:
            await _ending_onboarding(update, context, user_timezone)
            return ConversationHandler.END
            
    elif processed_input.startswith("no"):
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ONBOARDING_TZ_ASK_CITY
    
    else:
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `Si` o `No`. Venga, otra vez.")
        return ONBOARDING_CONFIRM_CITY
    
    # Fallback por si algo sale mal (ej: se pierde el user_data)
    return await cancel_conversation(update, context)
    
async def _ending_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, user_timezone: str):
    """
    Función auxiliar centralizada para guardar todas las configuraciones finales.
    """
    chat_id = update.effective_chat.id
    
    # 1. Guardar configuraciones en la base de datos
    set_config(chat_id, "user_timezone", user_timezone)
    set_config(chat_id, "onboarding_completo", "1")
    set_config(chat_id, "resumen_diario_activado", "1") # Activado por defecto
    set_config(chat_id, "resumen_diario_hora", "08:00") # A las 8:00 por defecto

    # 2. Programar el primer job de resumen diario para el nuevo usuario
    schedule_daily_brief(chat_id, "08:00", user_timezone)
    
    # 3. Enviar mensaje de confirmación y limpiar teclados.
    mensaje_final = get_text("onboarding_finalizado", timezone=user_timezone)
    await update.message.reply_text(
        mensaje_final, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()

async def error_ask_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario escribe texto cuando se esperaba la ubicación."""
    await update.message.reply_text(get_text("error_esperaba_ubicacion"))
    return ONBOARDING_TZ_ASK_LOCATION

async def error_ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario envía ubicación cuando se esperaba texto."""
    await update.message.reply_text(get_text("error_esperaba_ciudad"), reply_markup=ReplyKeyboardRemove())
    return ONBOARDING_TZ_ASK_CITY


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
start_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ONBOARDING_SAFE_MODE: [
            CallbackQueryHandler(onboarding_receive_safe_mode, pattern=r"^onboarding_safe_mode_level:\d$")
        ],
        ONBOARDING_TZ_ASK_METHOD: [
            CallbackQueryHandler(onboarding_tz_method_automatic, pattern="^onboarding_tz_auto$"),
            CallbackQueryHandler(onboarding_tz_method_manual, pattern="^onboarding_tz_manual$"),
        ],
        ONBOARDING_TZ_ASK_LOCATION: [
            MessageHandler(filters.LOCATION, onboarding_receive_location),
            MessageHandler(filters.TEXT & ~filters.COMMAND, error_ask_location)
        ],
        ONBOARDING_TZ_ASK_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_receive_city),
            MessageHandler(filters.LOCATION, error_ask_city)
        ],
        ONBOARDING_CONFIRM_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, onboarding_confirm_city)
        ]
    },
    fallbacks=[
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command) 
    ]
)
