# handlers/settings.py
"""
Módulo para el comando /ajustes.

Gestiona una conversación compleja con múltiples ramas para permitir al usuario
configurar el Modo Seguro, la Zona Horaria y las preferencias del Resumen Diario.
"""

import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton
from telegram.ext import ContextTypes, ConversationHandler, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from timezonefinderL import TimezoneFinder
from geopy.geocoders import Nominatim

from db import get_config, set_config, get_connection
from personality import get_text, TEXTS
from utils import cancel_conversation, unexpected_command, normalize_text
from daily_brief import schedule_daily_brief, cancel_daily_brief

# --- DEFINICIÓN DE ESTADOS DE LA CONVERSACIÓN ---
# Usar un enum o constantes nombradas hace el código más legible que range().
(
    MAIN_MENU, SAFE_MODE_MENU, TIMEZONE_MENU,
    AWAITING_LOCATION, AWAITING_CITY,
    CONFIRM_CITY, CONFIRM_TZ_UPDATE,
    DAILY_BRIEF_MENU, AWAITING_BRIEF_TIME,
) = range(9)



# =============================================================================
# SECCIÓN 1: PUNTO DE ENTRADA Y MENÚ PRINCIPAL
# =============================================================================

def _build_main_menu() -> tuple[str, InlineKeyboardMarkup]:
    """Crea el texto y el teclado para el menú principal de ajustes."""
    keyboard = [[
        InlineKeyboardButton("🛡️", callback_data="set_safe_mode"),
        InlineKeyboardButton("🌍", callback_data="set_timezone"),
        InlineKeyboardButton("🗓️", callback_data="set_daily_brief"),
        InlineKeyboardButton("❌", callback_data="settings_cancel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    text_menu = (
        "⚙️ Elige una opción:\n\n"
        "🛡️ Modo Seguro | 🌍 Zona Horaria\n"
        "🗓️ Resumen Diario | ❌ Cerrar"
    )
    
    return text_menu, reply_markup

async def settings_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación de /ajustes y muestra el menú principal."""
    # Obtenemos el texto y el teclado desde nuestra función centralizada.
    text_menu, reply_markup = _build_main_menu()
    
    await update.message.reply_text(text=text_menu, reply_markup=reply_markup)
    
    return MAIN_MENU

async def back_to_main_settings_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback para los botones 'Volver'. Edita el mensaje del submenú para mostrar
    el menú principal de nuevo, reutilizando el constructor de menú.
    """
    query = update.callback_query
    await query.answer()
    
    # Obtenemos el texto y el teclado desde nuestra función centralizada.
    text_menu, reply_markup = _build_main_menu()
    
    # Editamos el mensaje actual para mostrar el menú.
    await query.edit_message_text(text=text_menu, reply_markup=reply_markup)
    
    # Devolvemos el estado correcto al ConversationHandler.
    return MAIN_MENU

async def cancel_settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback para el botón [X]. Edita el mensaje a una confirmación y termina."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=get_text("cancelar"))
    if context.user_data: context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 2: RAMA DE "MODO SEGURO"
# =============================================================================

async def safe_mode_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el submenú para configurar el Modo Seguro."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    current_safe_mode = get_config(chat_id, "safe_mode") or "0"
    
    keyboard = [
        [InlineKeyboardButton("🔓 Nivel 0 (Sin confirmaciones)", callback_data="safe_level:0")],
        [InlineKeyboardButton("🗑️ Nivel 1 (Confirmar borrado)", callback_data="safe_level:1")],
        [InlineKeyboardButton("🔄 Nivel 2 (Confirmar cambio)", callback_data="safe_level:2")],
        [InlineKeyboardButton("🔒 Nivel 3 (Confirmar ambos)", callback_data="safe_level:3")],
        [InlineKeyboardButton("<< Volver", callback_data="settings_back_to_menu")]
    ]
    
    question_text = get_text("ajustes_pide_nivel", level=current_safe_mode)
    final_message = f"🛡️ *Modo Seguro*\n\n{question_text}"
    await query.edit_message_text(text=final_message, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return SAFE_MODE_MENU

async def receive_level_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nivel de Modo Seguro seleccionado y finaliza la conversación."""
    query = update.callback_query
    await query.answer()
    
    level_str = query.data.split(":")[1]
    set_config(update.effective_chat.id, "safe_mode", level_str)
    
    level_description = TEXTS["niveles_modo_seguro"].get(level_str, "Desconocido")
    confirmation_message = get_text("ajustes_confirmados", level=level_str, description=level_description)
    
    await query.edit_message_text(text=confirmation_message, parse_mode="Markdown")
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 3: RAMA DE "ZONA HORARIA"
# =============================================================================

async def timezone_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú para ELEGIR el método de configuración de la zona horaria."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    current_tz = get_config(chat_id, "user_timezone") or "aún sin configurar"
    
    # Creamos los botones Inline para elegir el método
    keyboard = [
        [InlineKeyboardButton("🪄 Automático (con ubicación)", callback_data="tz_auto")],
        [InlineKeyboardButton("✍️ Manual (escribir ciudad)", callback_data="tz_manual")],
        [InlineKeyboardButton("<< Volver al menú principal", callback_data="settings_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    question_text = get_text("timezone_pide_metodo", current_timezone=current_tz)
    await query.edit_message_text(text=question_text, reply_markup=reply_markup, parse_mode="Markdown")
    
    return TIMEZONE_MENU 

async def tz_auto_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    return AWAITING_LOCATION

async def tz_manual_method(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prepara al bot para recibir texto."""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(text=get_text("timezone_pide_ciudad"))
    return AWAITING_CITY

async def receive_ubi(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja EXCLUSIVAMENTE la recepción de una ubicación."""
    chat_id = update.effective_chat.id
    lat = update.message.location.latitude
    lon = update.message.location.longitude
    tf = TimezoneFinder()
    user_timezone = tf.timezone_at(lng=lon, lat=lat)

    if user_timezone:
        return await _save_and_prompt_tz_update(update, context, user_timezone)
    
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

async def receive_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Maneja EXCLUSIVAMENTE la recepción de un texto (ciudad)."""
    city = update.message.text

    # Enviamos el mensaje de "Buscando..." inmediatamente.
    loading_message = await update.message.reply_text(
        get_text("timezone_buscando", city=city), 
        parse_mode="Markdown"
    )

    try:
        geolocator = Nominatim(user_agent="la_recordadora_bot")
        location = geolocator.geocode(city, language='es', timeout=10) # como geopy puede fallar, damos margen de 10s
        
        # Una vez que geopy responde (rápido o lento), borramos el mensaje de "Buscando...".
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )

        if location:
            tf = TimezoneFinder()
            user_timezone_found = tf.timezone_at(lng=location.longitude, lat=location.latitude)
            context.user_data["timezone_a_confirmar"] = user_timezone_found
            
            question_text = get_text("timezone_pregunta_confirmacion", city=location.address, timezone=user_timezone_found)
            await update.message.reply_text(question_text, parse_mode="Markdown")
            return CONFIRM_CITY
        else:
            await update.message.reply_text(get_text("timezone_no_encontrada"))
            return AWAITING_CITY
    except Exception as e:
        print(f"Error con geopy: {e}")

        # --- BORRAMOS EL MENSAJE DE CARGA (también en caso de error) ---
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=loading_message.message_id
        )
        
        await update.message.reply_text(get_text("error_geopy"))
        return AWAITING_CITY

async def error_ask_ubication(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario escribe texto cuando se esperaba la ubicación."""
    await update.message.reply_text(get_text("error_esperaba_ubicacion"))
    return AWAITING_LOCATION

async def error_ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa si el usuario envía ubicación cuando se esperaba texto."""
    await update.message.reply_text(get_text("error_esperaba_ciudad"), reply_markup=ReplyKeyboardRemove())
    return AWAITING_CITY 

async def confirm_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la respuesta del usuario para la zona horaria y la valida de forma robusta."""
    
    process_input = normalize_text(update.message.text.strip())

    if process_input.startswith("si"):
        user_timezone = context.user_data.get("timezone_a_confirmar")
        if user_timezone:
            return await _save_and_prompt_tz_update(update, context, user_timezone)
            
    elif process_input.startswith("no"):
        await update.message.reply_text(get_text("timezone_reintentar"))
        return AWAITING_CITY
        
    else:
        # Si no es ni 'si' ni 'no', le pedimos que lo aclare.
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `si` o `no`. Venga, otra vez.")
        return CONFIRM_CITY
        
    # Si algo falla (ej. se pierde el user_data), cancelamos
    return await cancel_conversation(update, context)

async def _save_and_prompt_tz_update(update: Update, context: ContextTypes.DEFAULT_TYPE, new_tz: str):
    """Función ayudante: Guarda la nueva TZ y pregunta si se actualizan los recordatorios antiguos."""
    chat_id = update.effective_chat.id
    set_config(chat_id, "user_timezone", new_tz)
    context.user_data["new_tz"] = new_tz
    
    keyboard = [
        [InlineKeyboardButton("Sí, actualízalos a la nueva zona horaria", callback_data="tz_update_yes")],
        [InlineKeyboardButton("No, déjalos con su hora original", callback_data="tz_update_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ ¡Perfecto! Tu nueva zona horaria es *{new_tz}*.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text="He visto que puedes tener recordatorios creados en otras zonas horarias. ¿Qué hacemos con ellos?",
        reply_markup=reply_markup
    )
    return CONFIRM_TZ_UPDATE

async def process_tz_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa cuando el usuario responde SÍ o NO a la actualización."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    
    if query.data == "tz_update_yes":
        new_tz = context.user_data.get("new_tz")
        with get_connection() as conn:
            # CAMBIO: Se reemplaza '?' por '%s' para compatibilidad con PostgreSQL.
            conn.cursor().execute("UPDATE reminders SET timezone = %s WHERE chat_id = %s", (new_tz, chat_id))
        await query.edit_message_text("✅ ¡Entendido! He actualizado todos tus recordatorios a tu nueva zona horaria.")
    else: # tz_update_no
        await query.edit_message_text("👍 De acuerdo. Tus recordatorios antiguos conservarán la zona horaria con la que fueron creados.")
        
    # --- ¡LÓGICA DE EVENTOS! ---
    # Reprogramamos el resumen con la nueva TZ (si está activado)
    if get_config(chat_id, "daily_brief_activated") == '1':
        hour = get_config(chat_id, "daily_brief_hour") or "08:00"
        new_tz = context.user_data.get("new_tz", "UTC")
        schedule_daily_brief(chat_id, hour, new_tz)

    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 4: RAMA DE "RESUMEN DIARIO"
# =============================================================================

async def menu_daily_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú de configuración del resumen diario."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    # Obtenemos la configuración actual del usuario, con valores por defecto
    is_enabled = get_config(chat_id, "daily_brief_activated") == '1'
    time_str = get_config(chat_id, "daily_brief_hour") or "08:00"

    # Preparamos los textos para el mensaje
    status_str = "✅ Activado" if is_enabled else "❌ Desactivado"
    toggle_button_text = "❌ Desactivar" if is_enabled else "✅ Activar"
    
    # Creamos los botones
    keyboard = [
        [InlineKeyboardButton(f"{toggle_button_text}", callback_data="daily_brief_toggle")],
        [InlineKeyboardButton("🕑 Cambiar hora", callback_data="daily_brief_change_time")],
        [InlineKeyboardButton("<< Volver", callback_data="settings_back_to_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    message = get_text("ajustes_resumen_menu", status=status_str, hour=time_str)
    await query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
    return DAILY_BRIEF_MENU

async def toggle_daily_brief(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Activa o desactiva el resumen diario."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    current_activated = get_config(chat_id, "daily_brief_activated") == '1'
    new_state = '0' if current_activated else '1'
    set_config(chat_id, "daily_brief_activated", new_state)

    # --- ¡LÓGICA DE EVENTOS! ---
    if new_state == '1':
        # Si se activa, leemos la hora y la TZ y programamos el job
        hour = get_config(chat_id, "daily_brief_hour") or "08:00"
        tz = get_config(chat_id, "user_timezone") or "UTC"
        schedule_daily_brief(chat_id, hour, tz)
    else:
        # Si se desactiva, cancelamos el job
        cancel_daily_brief(chat_id)

    return await menu_daily_brief(update, context)

async def ask_daily_brief_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario que ESCRIBA la hora."""
    query = update.callback_query
    await query.answer()
    
    # Eliminamos el teclado de botones para que pueda escribir
    await query.edit_message_text(
        text="👵 ¿A qué hora del día quieres que te envíe el resumen?\n\n"
             "Escríbela en formato `HH:MM` (ej: `08:30` o `22:15`)."
    )
    return AWAITING_BRIEF_TIME

async def save_daily_brief_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida la hora escrita por el usuario."""
    chat_id = update.effective_chat.id
    written_time = update.message.text.strip()

    # Usamos una expresión regular para validar el formato HH:MM
    if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", written_time):
        await update.message.reply_text("❗ ¡Formato incorrecto, criatura! Usa `HH:MM`, por ejemplo `09:00`.")
        return AWAITING_BRIEF_TIME # Mantenemos al usuario en este paso

    # Si el formato es correcto, guardamos y reprogramamos
    set_config(chat_id, "daily_brief_hour", written_time)
    
    if get_config(chat_id, "daily_brief_activated") == '1':
        tz = get_config(chat_id, "user_timezone") or "UTC"
        schedule_daily_brief(chat_id, written_time, tz)
    
    # Enviamos un mensaje de confirmación y terminamos la conversación
    await update.message.reply_text(f"✅ ¡Entendido! He programado tu resumen diario para las *{written_time}*.", parse_mode="Markdown")
    
    # Limpiamos los datos y finalizamos
    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# CONVERSATION HANDLER
# =============================================================================

settings_handler = ConversationHandler(
    entry_points=[CommandHandler(["ajustes", "settings", "sett", "config"], settings_cmd)],
    states={
        MAIN_MENU: [
            CallbackQueryHandler(safe_mode_menu, pattern="^set_safe_mode$"),
            CallbackQueryHandler(timezone_menu, pattern="^set_timezone$"),
            CallbackQueryHandler(menu_daily_brief, pattern="^set_daily_brief$"),
            CallbackQueryHandler(cancel_settings_callback, pattern="^settings_cancel$"),
        ],
        SAFE_MODE_MENU: [
            CallbackQueryHandler(receive_level_callback, pattern=r"^safe_level:\d$"),
            CallbackQueryHandler(back_to_main_settings_menu, pattern="^settings_back_to_menu$"),
        ],
        TIMEZONE_MENU: [
            CallbackQueryHandler(tz_auto_method, pattern="^tz_auto$"),
            CallbackQueryHandler(tz_manual_method, pattern="^tz_manual$"),
            CallbackQueryHandler(back_to_main_settings_menu, pattern="^settings_back_to_menu$"),
        ],
        AWAITING_LOCATION: [
            MessageHandler(filters.LOCATION, receive_ubi),
            MessageHandler(filters.TEXT & ~filters.COMMAND, error_ask_ubication) 
        ],
        AWAITING_CITY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, receive_city),
            MessageHandler(filters.LOCATION, error_ask_city)
        ],
        CONFIRM_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_city)],
        CONFIRM_TZ_UPDATE: [CallbackQueryHandler(process_tz_update, pattern=r"^tz_update_")],
        DAILY_BRIEF_MENU: [
            CallbackQueryHandler(toggle_daily_brief, pattern="^daily_brief_toggle$"),
            CallbackQueryHandler(ask_daily_brief_time, pattern="^daily_brief_change_time$"),
            CallbackQueryHandler(back_to_main_settings_menu, pattern="^settings_back_to_menu$"),
        ],
        AWAITING_BRIEF_TIME: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, save_daily_brief_time),
        ],
    },
    fallbacks=[
        CommandHandler("cancelar", cancel_conversation),
        MessageHandler(filters.COMMAND, unexpected_command)
    ],
)