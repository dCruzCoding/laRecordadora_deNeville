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
from personalidad import get_text, TEXTOS
from utils import cancelar_conversacion, comando_inesperado, normalizar_texto
from avisos_resumen_diario import programar_resumen_diario_usuario

# --- DEFINICIÓN DE ESTADOS ---
(
    ONBOARDING_ELIGE_MODO_SEGURO, ONBOARDING_PIDE_METODO_TZ,
    ONBOARDING_PIDE_UBICACION, ONBOARDING_PIDE_CIUDAD,
    ONBOARDING_CONFIRMAR_CIUDAD
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
        [InlineKeyboardButton("🔓 Nivel 0", callback_data="onboarding_nivel_seguro:0"),
         InlineKeyboardButton("🗑️ Nivel 1", callback_data="onboarding_nivel_seguro:1")],
        [InlineKeyboardButton("🔄 Nivel 2", callback_data="onboarding_nivel_seguro:2"),
         InlineKeyboardButton("🔒 Nivel 3", callback_data="onboarding_nivel_seguro:3")],
    ]
    await update.message.reply_text(
        get_text("onboarding_pide_modo_seguro", nivel='0 (por defecto)'),
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return ONBOARDING_ELIGE_MODO_SEGURO


async def recibir_modo_seguro_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso 2: Guarda el Modo Seguro y pide el método para la Zona Horaria."""
    query = update.callback_query
    await query.answer()

    nivel_str = query.data.split(":")[1]
    set_config(query.effective_chat.id, "modo_seguro", nivel_str)
    
    descripcion_nivel = TEXTOS["niveles_modo_seguro"].get(nivel_str, "Desconocido")
    await query.edit_message_text(
        get_text("ajustes_confirmados", nivel=nivel_str, descripcion=descripcion_nivel),
        parse_mode="Markdown"
    )

    keyboard = [
        [InlineKeyboardButton("🪄 Automático (con ubicación)", callback_data="onboarding_tz_auto")],
        [InlineKeyboardButton("✍️ Manual (escribir ciudad)", callback_data="onboarding_tz_manual")],
    ]
    await context.bot.send_message(
        chat_id=query.effective_chat.id,
        text=get_text("onboarding_pide_zona_horaria"),
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    return ONBOARDING_PIDE_METODO_TZ

async def onboarding_tz_metodo_automatico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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

    return ONBOARDING_PIDE_UBICACION

async def onboarding_tz_metodo_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    return ONBOARDING_PIDE_CIUDAD

async def recibir_ubicacion_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso final (automático): Recibe la ubicación y finaliza el onboarding."""
    tf = TimezoneFinder()
    user_timezone = tf.timezone_at(lng=update.message.location.longitude, lat=update.message.location.latitude)

    if user_timezone:
        await _finalizar_onboarding(update, context, user_timezone)
    else:
        await update.message.reply_text(
            "👵 ¡Vaya! No he podido determinar tu zona horaria. Inténtalo manualmente desde /ajustes.",
            reply_markup=ReplyKeyboardRemove()
        )
    return ConversationHandler.END


async def recibir_ciudad_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            user_timezone_encontrada = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            
            # Guardamos la zona horaria encontrada temporalmente para el siguiente paso
            context.user_data["onboarding_tz_a_confirmar"] = user_timezone_encontrada
            
            mensaje_pregunta = get_text(
                "timezone_pregunta_confirmacion", 
                ciudad=location.address, 
                timezone=user_timezone_encontrada
            )
            await update.message.reply_text(mensaje_pregunta, parse_mode="Markdown")
            
            # Pasamos al estado de esperar la confirmación (SI/NO)
            return ONBOARDING_CONFIRMAR_CIUDAD
        else:
            # La ciudad no se encontró
            await update.message.reply_text(get_text("timezone_no_encontrada"))
            # Le permitimos intentarlo de nuevo
            return ONBOARDING_PIDE_CIUDAD
            
    except Exception as e:
        print(f"Error con geopy: {e}")
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ONBOARDING_PIDE_CIUDAD

async def confirmar_ciudad_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Paso final (manual): Recibe el SÍ/NO y finaliza el onboarding."""
    respuesta_normalizada = normalizar_texto(update.message.text.strip())

    if respuesta_normalizada.startswith("si"):
        user_timezone = context.user_data.get("onboarding_tz_a_confirmar")
        if user_timezone:
            await _finalizar_onboarding(update, context, user_timezone)
            return ConversationHandler.END
            
    elif respuesta_normalizada.startswith("no"):
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ONBOARDING_PIDE_CIUDAD
    
    else:
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `Si` o `No`. Venga, otra vez.")
        return ONBOARDING_CONFIRMAR_CIUDAD
    
    # Fallback por si algo sale mal (ej: se pierde el user_data)
    return await cancelar_conversacion(update, context)
    
async def _finalizar_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE, user_timezone: str):
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
    programar_resumen_diario_usuario(chat_id, "08:00", user_timezone)
    
    # 3. Enviar mensaje de confirmación y limpiar teclados.
    mensaje_final = get_text("onboarding_finalizado", timezone=user_timezone)
    await update.message.reply_text(
        mensaje_final, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
    )
    context.user_data.clear()

async def error_pide_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario escribe texto cuando se esperaba la ubicación."""
    await update.message.reply_text(get_text("error_esperaba_ubicacion"))
    return ONBOARDING_PIDE_UBICACION

async def error_pide_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario envía ubicación cuando se esperaba texto."""
    await update.message.reply_text(get_text("error_esperaba_ciudad"), reply_markup=ReplyKeyboardRemove())
    return ONBOARDING_PIDE_CIUDAD


# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
start_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        ONBOARDING_ELIGE_MODO_SEGURO: [
            CallbackQueryHandler(recibir_modo_seguro_onboarding, pattern=r"^onboarding_nivel_seguro:\d$")
        ],
        ONBOARDING_PIDE_METODO_TZ: [
            CallbackQueryHandler(onboarding_tz_metodo_automatico, pattern="^onboarding_tz_auto$"),
            CallbackQueryHandler(onboarding_tz_metodo_manual, pattern="^onboarding_tz_manual$"),
        ],
        ONBOARDING_PIDE_UBICACION: [
            MessageHandler(filters.LOCATION, recibir_ubicacion_onboarding),
            MessageHandler(filters.TEXT & ~filters.COMMAND, error_pide_ubicacion)
        ],
        ONBOARDING_PIDE_CIUDAD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ciudad_onboarding),
            MessageHandler(filters.LOCATION, error_pide_ciudad)
        ],
        ONBOARDING_CONFIRMAR_CIUDAD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_ciudad_onboarding)
        ]
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) 
    ]
)
