from telegram import (
    Update,
    KeyboardButton, 
    ReplyKeyboardMarkup, 
    ReplyKeyboardRemove, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup
)
from telegram.ext import (
    ContextTypes, 
    ConversationHandler, 
    CommandHandler, 
    MessageHandler, 
    filters,
    CallbackQueryHandler
)
from db import get_config, set_config
from personalidad import get_text, TEXTOS
from timezonefinderL import TimezoneFinder
from geopy.geocoders import Nominatim
from utils import cancelar_conversacion, comando_inesperado
from avisos_resumen_diario import programar_resumen_diario_usuario

# Estados para la nueva conversación de bienvenida
ONBOARDING_ELIGE_MODO_SEGURO, \
ONBOARDING_PIDE_METODO_TZ, \
ONBOARDING_PIDE_UBICACION, \
ONBOARDING_PIDE_CIUDAD, \
ONBOARDING_CONFIRMAR_CIUDAD = range(5)

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
    keyboard = [
        [InlineKeyboardButton("🔓 Nivel 0 (Sin confirmaciones)", callback_data="onboarding_nivel_seguro:0")],
        [InlineKeyboardButton("🗑️ Nivel 1 (Confirmar borrado)", callback_data="onboarding_nivel_seguro:1")],
        [InlineKeyboardButton("🔄 Nivel 2 (Confirmar cambio)", callback_data="onboarding_nivel_seguro:2")],
        [InlineKeyboardButton("🔒 Nivel 3 (Confirmar ambos)", callback_data="onboarding_nivel_seguro:3")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(mensaje_modo_seguro, parse_mode="Markdown", reply_markup=reply_markup)
    return ONBOARDING_ELIGE_MODO_SEGURO

async def recibir_modo_seguro_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recibe la pulsación del botón del modo seguro durante el onboarding."""
    query = update.callback_query
    await query.answer()

    # El callback_data será "onboarding_nivel_seguro:X"
    nivel_str = query.data.split(":")[1]
    chat_id = update.effective_chat.id
    
    set_config(chat_id, "modo_seguro", nivel_str)
    
    descripcion_nivel = TEXTOS["niveles_modo_seguro"].get(nivel_str, "Desconocido")
    mensaje_confirmacion = get_text(
        "ajustes_confirmados", 
        nivel=nivel_str, 
        descripcion=descripcion_nivel
    )
    
    # Editamos el mensaje original para mostrar la confirmación y quitar los botones
    await query.edit_message_text(text=mensaje_confirmacion, parse_mode="Markdown")


    # AHORA, en lugar de pedir la ubicación directamente, mostramos el menú de elección
    tz_actual = get_config(update.effective_chat.id, "user_timezone") or "aún sin configurar"
    
    keyboard = [
        [InlineKeyboardButton("🪄 Automático (con ubicación)", callback_data="onboarding_tz_auto")],
        [InlineKeyboardButton("✍️ Manual (escribir ciudad)", callback_data="onboarding_tz_manual")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    texto_pregunta = get_text("onboarding_pide_zona_horaria")
    
    # Enviamos un nuevo mensaje para el siguiente paso
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=texto_pregunta,
        reply_markup=reply_markup,
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
    """
    Maneja la recepción de una ubicación durante el onboarding.
    Si tiene éxito, guarda todo y finaliza la conversación.
    """
    chat_id = update.effective_chat.id
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    tf = TimezoneFinder()
    user_timezone = tf.timezone_at(lng=lon, lat=lat)

    if user_timezone:
        # Éxito: Guardamos la zona horaria y marcamos el onboarding como completo
        set_config(chat_id, "resumen_diario_activado", "1")
        set_config(chat_id, "resumen_diario_hora", "08:00")

        # --- ¡LÓGICA DE EVENTOS! ---
        # Programamos el primer job para el nuevo usuario
        programar_resumen_diario_usuario(chat_id, "08:00", user_timezone)
        
        mensaje_final = get_text("onboarding_finalizado", timezone=user_timezone)
        
        await update.message.reply_text(
            mensaje_final,
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove() # Limpiamos el teclado de ubicación
        )
        return ConversationHandler.END
    else:
        # Fallo (muy raro): No se encontró zona horaria
        await update.message.reply_text(
            "👵 ¡Vaya! Por alguna razón no he podido determinar tu zona horaria desde esa ubicación. Inténtalo de nuevo manualmente desde /ajustes.",
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
    """Recibe el SÍ/NO del usuario para la zona horaria durante el onboarding."""
    chat_id = update.effective_chat.id
    respuesta = update.message.text.strip().upper()

    if respuesta == "SI":
        user_timezone = context.user_data.get("onboarding_tz_a_confirmar")
        if user_timezone:
            # Éxito: Guardamos todo y finalizamos el onboarding
            set_config(chat_id, "user_timezone", user_timezone)
            set_config(chat_id, "onboarding_completo", "1")
            set_config(chat_id, "resumen_diario_activado", "1")
            set_config(chat_id, "resumen_diario_hora", "08:00")

            # --- ¡LÓGICA DE EVENTOS! ---
            # Programamos el primer job para el nuevo usuario
            programar_resumen_diario_usuario(chat_id, "08:00", user_timezone)
            
            mensaje_final = get_text("onboarding_finalizado", timezone=user_timezone)
            await update.message.reply_text(
                mensaje_final,
                parse_mode="Markdown"
            )
            context.user_data.clear()
            return ConversationHandler.END
            
    elif respuesta == "NO":
        await update.message.reply_text(get_text("timezone_reintentar"))
        # Devolvemos al usuario al paso de escribir la ciudad
        return ONBOARDING_PIDE_CIUDAD
    else:
        # El usuario no ha escrito ni SI ni NO
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `Si` o `No`. Venga, otra vez.")
        # Mantenemos la conversación en el mismo estado, esperando la respuesta correcta
        return ONBOARDING_CONFIRMAR_CIUDAD
    
async def error_pide_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario escribe texto cuando se esperaba la ubicación."""
    await update.message.reply_text(get_text("error_esperaba_ubicacion"))
    return ONBOARDING_PIDE_UBICACION

async def error_pide_ciudad(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario envía ubicación cuando se esperaba texto."""
    await update.message.reply_text(get_text("error_esperaba_ciudad"), reply_markup=ReplyKeyboardRemove())
    return ONBOARDING_PIDE_CIUDAD


# Handler para la conversación de bienvenida
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
        MessageHandler(filters.COMMAND, comando_inesperado) # <-- Maneja las interrupciones
    ]
)


################################################################################