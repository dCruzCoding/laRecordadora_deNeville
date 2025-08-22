from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, 
    KeyboardButton
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
# Ahora necesitamos get_config para mostrar el estado actual
from db import get_config, set_config
from personalidad import get_text, TEXTOS
from timezonefinderL import TimezoneFinder
from geopy.geocoders import Nominatim
from utils import manejar_cancelacion

# Estados de la nueva conversación unificada
MENU_PRINCIPAL, \
MODO_SEGURO_MENU, \
ZONA_HORARIA_MENU, \
ZONA_HORARIA_PIDE_UBICACION, \
ZONA_HORARIA_PIDE_CIUDAD, \
ZONA_HORARIA_CONFIRMAR_CIUDAD = range(6)

# --- INICIO Y MENÚ PRINCIPAL ---
async def ajustes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú principal de ajustes."""
    keyboard = [
        [InlineKeyboardButton("🛡️ Modo Seguro", callback_data="set_modo_seguro")],
        [InlineKeyboardButton("🌍 Zona Horaria", callback_data="set_zona_horaria")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("⚙️ ¿Qué quieres modificar?", reply_markup=reply_markup)
    return MENU_PRINCIPAL

# --- Rama 1: Flujo del Modo Seguro ---
async def menu_modo_seguro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra los niveles de modo seguro como botones inline."""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    modo_seguro_actual = get_config(chat_id, "modo_seguro") or "0"
    
    # Creamos un teclado de botones para los niveles
    keyboard = [
        [InlineKeyboardButton("🔓 Nivel 0 (Sin confirmaciones)", callback_data="nivel_seguro:0")],
        [InlineKeyboardButton("🗑️ Nivel 1 (Confirmar borrado)", callback_data="nivel_seguro:1")],
        [InlineKeyboardButton("🔄 Nivel 2 (Confirmar cambio)", callback_data="nivel_seguro:2")],
        [InlineKeyboardButton("🔒 Nivel 3 (Confirmar ambos)", callback_data="nivel_seguro:3")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    mensaje_pregunta = get_text("ajustes_pide_nivel", nivel=modo_seguro_actual)
    mensaje_final = "🛡️ Has seleccionado *Modo Seguro*. En este apartado podrás añadir o quitar mensajes de confirmación para las acciones de borrar y cambiar estado.\n\n" + mensaje_pregunta
    # Editamos el mensaje original para mostrar la pregunta Y los nuevos botones
    await query.edit_message_text(
        text=mensaje_final,
        parse_mode="Markdown",
        reply_markup=reply_markup
    )
    return MODO_SEGURO_MENU

async def recibir_nivel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la pulsación del botón del nivel de seguridad, lo guarda y confirma."""
    query = update.callback_query
    await query.answer()
    
    # El callback_data será "nivel_seguro:X"
    # Lo separamos para obtener solo el número
    nivel_str = query.data.split(":")[1]
    chat_id = update.effective_chat.id
    
    set_config(chat_id, "modo_seguro", nivel_str)
    
    # Preparamos el mensaje de confirmación con la descripción
    descripcion_nivel = TEXTOS["niveles_modo_seguro"].get(nivel_str, "Desconocido")
    mensaje_confirmacion = get_text(
        "ajustes_confirmados",
        nivel=nivel_str,
        descripcion=descripcion_nivel
    )
    
    # Editamos el mensaje original para mostrar la confirmación y quitar los botones
    await query.edit_message_text(text=mensaje_confirmacion, parse_mode="Markdown")
    return ConversationHandler.END

# --- Rama 2: Flujo de la Zona Horaria ---
async def menu_zona_horaria(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú para ELEGIR el método de configuración de la zona horaria."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    tz_actual = get_config(chat_id, "user_timezone") or "aún sin configurar"
    
    # Creamos los botones Inline para elegir el método
    keyboard = [
        [InlineKeyboardButton("🪄 Automático (con ubicación)", callback_data="tz_auto")],
        [InlineKeyboardButton("✍️ Manual (escribir ciudad)", callback_data="tz_manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    texto_pregunta = get_text("timezone_pide_metodo", timezone_actual=tz_actual)
    await query.edit_message_text(text=texto_pregunta, reply_markup=reply_markup, parse_mode="Markdown")
    
    return ZONA_HORARIA_MENU 

async def tz_metodo_automatico(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prepara al bot para recibir una ubicación."""
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
    return ZONA_HORARIA_PIDE_UBICACION

async def tz_metodo_manual(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prepara al bot para recibir texto."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(text=get_text("timezone_pide_ciudad"))
    return ZONA_HORARIA_PIDE_CIUDAD

async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja EXCLUSIVAMENTE la recepción de una ubicación."""
    chat_id = update.effective_chat.id
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    tf = TimezoneFinder()
    user_timezone = tf.timezone_at(lng=lon, lat=lat)

    if user_timezone:
        # Caso de éxito (sin cambios)
        set_config(chat_id, "user_timezone", user_timezone)
        mensaje_confirmacion = get_text("timezone_confirmada", timezone=user_timezone)
        await update.message.reply_text(
            mensaje_confirmacion, parse_mode="Markdown", reply_markup=ReplyKeyboardRemove()
        )
        # Terminamos la conversación con éxito
        return ConversationHandler.END
    else:

        # Caso de fallo: no se encontró zona horaria
        # 1. Enviamos un mensaje de error al usuario
        await update.message.reply_text(
            "👵 ¡Vaya! Por alguna razón no he podido determinar tu zona horaria desde esa ubicación. Inténtalo de nuevo manualmente desde /ajustes.",
            reply_markup=ReplyKeyboardRemove() # Limpiamos el teclado
        )
        
        # 2. Limpiamos cualquier dato temporal de la conversación
        if context.user_data:
            context.user_data.clear()
            
        # 3. Terminamos la conversación explícitamente
        return ConversationHandler.END

async def recibir_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja EXCLUSIVAMENTE la recepción de un texto (ciudad)."""
    ciudad = update.message.text
    try:
        geolocator = Nominatim(user_agent="la_recordadora_bot")
        location = geolocator.geocode(ciudad, language='es')
        if location:
            tf = TimezoneFinder()
            user_timezone_encontrada = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            context.user_data["timezone_a_confirmar"] = user_timezone_encontrada
            
            mensaje_pregunta = get_text("timezone_pregunta_confirmacion", ciudad=location.address, timezone=user_timezone_encontrada)
            await update.message.reply_text(mensaje_pregunta, parse_mode="Markdown")
            return ZONA_HORARIA_CONFIRMAR_CIUDAD
        else:
            await update.message.reply_text(get_text("timezone_no_encontrada"))
            return ZONA_HORARIA_PIDE_CIUDAD
    except Exception as e:
        print(f"Error con geopy: {e}")
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ZONA_HORARIA_PIDE_CIUDAD

async def error_pide_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario escribe texto cuando se esperaba la ubicación."""
    await update.message.reply_text(get_text("error_esperaba_ubicacion"))
    return ZONA_HORARIA_PIDE_UBICACION

async def error_pide_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario envía ubicación cuando se esperaba texto."""
    await update.message.reply_text(get_text("error_esperaba_ciudad"), reply_markup=ReplyKeyboardRemove())
    return ZONA_HORARIA_PIDE_CIUDAD 

async def confirmar_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe el SÍ/NO del usuario para la zona horaria."""
    chat_id = update.effective_chat.id
    respuesta = update.message.text.strip().upper()

    if respuesta == "SI":
        user_timezone = context.user_data.get("timezone_a_confirmar")
        if user_timezone:
            set_config(chat_id, "user_timezone", user_timezone)
            mensaje_confirmacion = get_text("timezone_confirmada", timezone=user_timezone)
            await update.message.reply_text(
                mensaje_confirmacion,
                parse_mode="Markdown",
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data.clear()
            return ConversationHandler.END
    elif respuesta == "NO":
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ZONA_HORARIA_PIDE_CIUDAD # <-- Lo devolvemos al paso de escribir la ciudad
    else:
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `SI` o `NO`. Venga, otra vez.")
        return ZONA_HORARIA_CONFIRMAR_CIUDAD # <-- Le volvemos a preguntar SÍ/NO



# --- Construcción del ConversationHandler Unificado ---
ajustes_handler = ConversationHandler(
    entry_points=[CommandHandler("ajustes", ajustes_cmd)],
    states={
        MENU_PRINCIPAL: [
            CallbackQueryHandler(menu_modo_seguro, pattern="^set_modo_seguro$"),
            CallbackQueryHandler(menu_zona_horaria, pattern="^set_zona_horaria$"),
        ],
        MODO_SEGURO_MENU: [
            CallbackQueryHandler(recibir_nivel_callback, pattern="^nivel_seguro:\d$")
        ],
        ZONA_HORARIA_MENU: [
            CallbackQueryHandler(tz_metodo_automatico, pattern="^tz_auto$"),
            CallbackQueryHandler(tz_metodo_manual, pattern="^tz_manual$"),
        ],
        ZONA_HORARIA_PIDE_UBICACION: [
            MessageHandler(filters.LOCATION, recibir_ubicacion),
            MessageHandler(filters.TEXT & ~filters.COMMAND, error_pide_ubicacion)
        ],
        ZONA_HORARIA_PIDE_CIUDAD: [ 
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ciudad),
            MessageHandler(filters.LOCATION, error_pide_ciudad)
        ],
        ZONA_HORARIA_CONFIRMAR_CIUDAD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_ciudad)
        ]},
    fallbacks=[CommandHandler("cancelar", manejar_cancelacion)]
)