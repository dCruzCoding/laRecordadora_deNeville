# handlers/ajustes.py
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
from personalidad import get_text, TEXTOS
from utils import cancelar_conversacion, comando_inesperado, normalizar_texto
from avisos_resumen_diario import programar_resumen_diario_usuario, cancelar_resumen_diario_usuario

# --- DEFINICIÓN DE ESTADOS DE LA CONVERSACIÓN ---
# Usar un enum o constantes nombradas hace el código más legible que range().
(
    MENU_PRINCIPAL, MODO_SEGURO_MENU, ZONA_HORARIA_MENU,
    ZONA_HORARIA_PIDE_UBICACION, ZONA_HORARIA_PIDE_CIUDAD,
    ZONA_HORARIA_CONFIRMAR_CIUDAD, CONFIRMAR_ACTUALIZACION_TZ,
    RESUMEN_DIARIO_MENU, RESUMEN_DIARIO_PIDE_HORA,
) = range(9)



# =============================================================================
# SECCIÓN 1: PUNTO DE ENTRADA Y MENÚ PRINCIPAL
# =============================================================================

def _build_main_menu() -> tuple[str, InlineKeyboardMarkup]:
    """Crea el texto y el teclado para el menú principal de ajustes."""
    keyboard = [[
        InlineKeyboardButton("🛡️", callback_data="set_modo_seguro"),
        InlineKeyboardButton("🌍", callback_data="set_zona_horaria"),
        InlineKeyboardButton("🗓️", callback_data="set_resumen_diario"),
        InlineKeyboardButton("❌", callback_data="ajustes_cancel")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    texto_menu = (
        "⚙️ Elige una opción:\n\n"
        "🛡️ Modo Seguro | 🌍 Zona Horaria\n"
        "🗓️ Resumen Diario | ❌ Cerrar"
    )
    
    return texto_menu, reply_markup

async def ajustes_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Inicia la conversación de /ajustes y muestra el menú principal."""
    # Obtenemos el texto y el teclado desde nuestra función centralizada.
    texto_menu, reply_markup = _build_main_menu()
    
    await update.message.reply_text(text=texto_menu, reply_markup=reply_markup)
    
    return MENU_PRINCIPAL

async def volver_menu_principal_ajustes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback para los botones 'Volver'. Edita el mensaje del submenú para mostrar
    el menú principal de nuevo, reutilizando el constructor de menú.
    """
    query = update.callback_query
    await query.answer()
    
    # Obtenemos el texto y el teclado desde nuestra función centralizada.
    texto_menu, reply_markup = _build_main_menu()
    
    # Editamos el mensaje actual para mostrar el menú.
    await query.edit_message_text(text=texto_menu, reply_markup=reply_markup)
    
    # Devolvemos el estado correcto al ConversationHandler.
    return MENU_PRINCIPAL


### Otra version de volver_menu_principal_ajustes que no borra el mensaje, sino que edita.

# async def volver_menu_principal_ajustes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
#     """Callback genérico para los botones 'Volver'. Vuelve al menú principal de /ajustes."""
#     query = update.callback_query
#     await query.answer()
    
#     # Creamos un menú "falso" para reutilizar la función de entrada
#     class FakeUpdate:
#         def __init__(self, message): self.message = message
            
#     # Editamos el mensaje actual para mostrar el menú principal de nuevo
#     await query.edit_message_text(text="⚙️ ¿Qué quieres modificar?")
#     await ajustes_cmd(FakeUpdate(query.message), context) # Llama a ajustes_cmd para que ponga los botones
#     return MENU_PRINCIPAL


async def cancelar_ajustes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Callback para el botón [X]. Edita el mensaje a una confirmación y termina."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=get_text("cancelar"))
    if context.user_data: context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 2: RAMA DE "MODO SEGURO"
# =============================================================================

async def menu_modo_seguro(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el submenú para configurar el Modo Seguro."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    modo_seguro_actual = get_config(chat_id, "modo_seguro") or "0"
    
    keyboard = [
        [InlineKeyboardButton("🔓 Nivel 0 (Sin confirmaciones)", callback_data="nivel_seguro:0")],
        [InlineKeyboardButton("🗑️ Nivel 1 (Confirmar borrado)", callback_data="nivel_seguro:1")],
        [InlineKeyboardButton("🔄 Nivel 2 (Confirmar cambio)", callback_data="nivel_seguro:2")],
        [InlineKeyboardButton("🔒 Nivel 3 (Confirmar ambos)", callback_data="nivel_seguro:3")],
        [InlineKeyboardButton("<< Volver", callback_data="ajustes_volver_menu")]
    ]
    
    mensaje_pregunta = get_text("ajustes_pide_nivel", nivel=modo_seguro_actual)
    mensaje_final = f"🛡️ *Modo Seguro*\n\n{mensaje_pregunta}"
    await query.edit_message_text(text=mensaje_final, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))
    return MODO_SEGURO_MENU

async def recibir_nivel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda el nivel de Modo Seguro seleccionado y finaliza la conversación."""
    query = update.callback_query
    await query.answer()
    
    nivel_str = query.data.split(":")[1]
    set_config(update.effective_chat.id, "modo_seguro", nivel_str)
    
    descripcion_nivel = TEXTOS["niveles_modo_seguro"].get(nivel_str, "Desconocido")
    mensaje_confirmacion = get_text("ajustes_confirmados", nivel=nivel_str, descripcion=descripcion_nivel)
    
    await query.edit_message_text(text=mensaje_confirmacion, parse_mode="Markdown")
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 3: RAMA DE "ZONA HORARIA"
# =============================================================================

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
        [InlineKeyboardButton("<< Volver al menú principal", callback_data="ajustes_volver_menu")]
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
        return await _guardar_y_preguntar_actualizacion_tz(update, context, user_timezone)
    
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

    # Enviamos el mensaje de "Buscando..." inmediatamente.
    mensaje_carga = await update.message.reply_text(
        get_text("timezone_buscando", ciudad=ciudad), 
        parse_mode="Markdown"
    )

    try:
        geolocator = Nominatim(user_agent="la_recordadora_bot")
        location = geolocator.geocode(ciudad, language='es', timeout=10) # como geopy puede fallar, damos margen de 10s
        
        # Una vez que geopy responde (rápido o lento), borramos el mensaje de "Buscando...".
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=mensaje_carga.message_id
        )

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

        # --- BORRAMOS EL MENSAJE DE CARGA (también en caso de error) ---
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=mensaje_carga.message_id
        )
        
        await update.message.reply_text(get_text("error_geopy"))
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
    """Recibe la respuesta del usuario para la zona horaria y la valida de forma robusta."""
    
    # --- ¡LÓGICA DE VALIDACIÓN MEJORADA! ---
    respuesta_normalizada = normalizar_texto(update.message.text.strip())

    if respuesta_normalizada.startswith("si"):
        user_timezone = context.user_data.get("timezone_a_confirmar")
        if user_timezone:
            return await _guardar_y_preguntar_actualizacion_tz(update, context, user_timezone)
            
    elif respuesta_normalizada.startswith("no"):
        await update.message.reply_text(get_text("timezone_reintentar"))
        return ZONA_HORARIA_PIDE_CIUDAD
        
    else:
        # Si no es ni 'si' ni 'no', le pedimos que lo aclare.
        await update.message.reply_text("👵 ¡Criatura! Solo entiendo `si` o `no`. Venga, otra vez.")
        return ZONA_HORARIA_CONFIRMAR_CIUDAD
        
    # Si algo falla (ej. se pierde el user_data), cancelamos
    return await cancelar_conversacion(update, context)

async def _guardar_y_preguntar_actualizacion_tz(update: Update, context: ContextTypes.DEFAULT_TYPE, nueva_tz: str):
    """Función ayudante: Guarda la nueva TZ y pregunta si se actualizan los recordatorios antiguos."""
    chat_id = update.effective_chat.id
    set_config(chat_id, "user_timezone", nueva_tz)
    context.user_data["nueva_tz"] = nueva_tz
    
    keyboard = [
        [InlineKeyboardButton("Sí, actualízalos a la nueva zona horaria", callback_data="tz_update_yes")],
        [InlineKeyboardButton("No, déjalos con su hora original", callback_data="tz_update_no")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=chat_id,
        text=f"✅ ¡Perfecto! Tu nueva zona horaria es *{nueva_tz}*.",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text="He visto que puedes tener recordatorios creados en otras zonas horarias. ¿Qué hacemos con ellos?",
        reply_markup=reply_markup
    )
    return CONFIRMAR_ACTUALIZACION_TZ

async def procesar_actualizacion_tz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Se activa cuando el usuario responde SÍ o NO a la actualización."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id
    
    if query.data == "tz_update_yes":
        nueva_tz = context.user_data.get("nueva_tz")
        with get_connection() as conn:
            conn.execute("UPDATE recordatorios SET timezone = ? WHERE chat_id = ?", (nueva_tz, chat_id))
            conn.commit()
        await query.edit_message_text("✅ ¡Entendido! He actualizado todos tus recordatorios a tu nueva zona horaria.")
    else: # tz_update_no
        await query.edit_message_text("👍 De acuerdo. Tus recordatorios antiguos conservarán la zona horaria con la que fueron creados.")
    
    # --- ¡LÓGICA DE EVENTOS! ---
    # Reprogramamos el resumen con la nueva TZ (si está activado)
    if get_config(chat_id, "resumen_diario_activado") == '1':
        hora = get_config(chat_id, "resumen_diario_hora") or "08:00"
        nueva_tz = context.user_data.get("nueva_tz", "UTC")
        programar_resumen_diario_usuario(chat_id, hora, nueva_tz)

    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# SECCIÓN 4: RAMA DE "RESUMEN DIARIO"
# =============================================================================

async def menu_resumen_diario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Muestra el menú de configuración del resumen diario."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    # Obtenemos la configuración actual del usuario, con valores por defecto
    activado = get_config(chat_id, "resumen_diario_activado") == '1'
    hora = get_config(chat_id, "resumen_diario_hora") or "08:00"

    # Preparamos los textos para el mensaje
    estado_str = "✅ Activado" if activado else "❌ Desactivado"
    texto_boton_toggle = "❌ Desactivar" if activado else "✅ Activar"
    
    # Creamos los botones
    keyboard = [
        [InlineKeyboardButton(f"{texto_boton_toggle}", callback_data="resumen_toggle")],
        [InlineKeyboardButton("🕑 Cambiar hora", callback_data="resumen_change_time")],
        [InlineKeyboardButton("<< Volver", callback_data="ajustes_volver_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    mensaje = get_text("ajustes_resumen_menu", estado=estado_str, hora=hora)
    await query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")
    return RESUMEN_DIARIO_MENU

async def toggle_resumen_diario(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Activa o desactiva el resumen diario."""
    query = update.callback_query
    await query.answer()
    chat_id = update.effective_chat.id

    activado_actual = get_config(chat_id, "resumen_diario_activado") == '1'
    nuevo_estado = '0' if activado_actual else '1'
    set_config(chat_id, "resumen_diario_activado", nuevo_estado)

    # --- ¡LÓGICA DE EVENTOS! ---
    if nuevo_estado == '1':
        # Si se activa, leemos la hora y la TZ y programamos el job
        hora = get_config(chat_id, "resumen_diario_hora") or "08:00"
        tz = get_config(chat_id, "user_timezone") or "UTC"
        programar_resumen_diario_usuario(chat_id, hora, tz)
    else:
        # Si se desactiva, cancelamos el job
        cancelar_resumen_diario_usuario(chat_id)

    return await menu_resumen_diario(update, context)

async def pedir_hora_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Pide al usuario que ESCRIBA la hora."""
    query = update.callback_query
    await query.answer()
    
    # Eliminamos el teclado de botones para que pueda escribir
    await query.edit_message_text(
        text="👵 ¿A qué hora del día quieres que te envíe el resumen?\n\n"
             "Escríbela en formato `HH:MM` (ej: `08:30` o `22:15`)."
    )
    return RESUMEN_DIARIO_PIDE_HORA

async def guardar_hora_resumen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe y valida la hora escrita por el usuario."""
    chat_id = update.effective_chat.id
    hora_escrita = update.message.text.strip()

    # Usamos una expresión regular para validar el formato HH:MM
    if not re.fullmatch(r"([01]\d|2[0-3]):([0-5]\d)", hora_escrita):
        await update.message.reply_text("❗ ¡Formato incorrecto, criatura! Usa `HH:MM`, por ejemplo `09:00`.")
        return RESUMEN_DIARIO_PIDE_HORA # Mantenemos al usuario en este paso

    # Si el formato es correcto, guardamos y reprogramamos
    set_config(chat_id, "resumen_diario_hora", hora_escrita)
    
    if get_config(chat_id, "resumen_diario_activado") == '1':
        tz = get_config(chat_id, "user_timezone") or "UTC"
        programar_resumen_diario_usuario(chat_id, hora_escrita, tz)
    
    # Enviamos un mensaje de confirmación y terminamos la conversación
    await update.message.reply_text(f"✅ ¡Entendido! He programado tu resumen diario para las *{hora_escrita}*.", parse_mode="Markdown")
    
    # Limpiamos los datos y finalizamos
    context.user_data.clear()
    return ConversationHandler.END



# =============================================================================
# CONVERSATION HANDLER
# =============================================================================

ajustes_handler = ConversationHandler(
    entry_points=[CommandHandler("ajustes", ajustes_cmd)],
    states={
        MENU_PRINCIPAL: [
            CallbackQueryHandler(menu_modo_seguro, pattern="^set_modo_seguro$"),
            CallbackQueryHandler(menu_zona_horaria, pattern="^set_zona_horaria$"),
            CallbackQueryHandler(menu_resumen_diario, pattern="^set_resumen_diario$"),
            CallbackQueryHandler(cancelar_ajustes_callback, pattern="^ajustes_cancel$"),
        ],
        MODO_SEGURO_MENU: [
            CallbackQueryHandler(recibir_nivel_callback, pattern=r"^nivel_seguro:\d$"),
            CallbackQueryHandler(volver_menu_principal_ajustes, pattern="^ajustes_volver_menu$"),
        ],
        ZONA_HORARIA_MENU: [
            CallbackQueryHandler(tz_metodo_automatico, pattern="^tz_auto$"),
            CallbackQueryHandler(tz_metodo_manual, pattern="^tz_manual$"),
            CallbackQueryHandler(volver_menu_principal_ajustes, pattern="^ajustes_volver_menu$"),
        ],
        ZONA_HORARIA_PIDE_UBICACION: [
            MessageHandler(filters.LOCATION, recibir_ubicacion),
            MessageHandler(filters.TEXT & ~filters.COMMAND, error_pide_ubicacion) 
        ],
        ZONA_HORARIA_PIDE_CIUDAD: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ciudad),
            MessageHandler(filters.LOCATION, error_pide_ciudad)
        ],
        ZONA_HORARIA_CONFIRMAR_CIUDAD: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_ciudad)],
        CONFIRMAR_ACTUALIZACION_TZ: [CallbackQueryHandler(procesar_actualizacion_tz, pattern=r"^tz_update_")],
        RESUMEN_DIARIO_MENU: [
            CallbackQueryHandler(toggle_resumen_diario, pattern="^resumen_toggle$"),
            CallbackQueryHandler(pedir_hora_resumen, pattern="^resumen_change_time$"),
            CallbackQueryHandler(volver_menu_principal_ajustes, pattern="^ajustes_volver_menu$"),
        ],
        RESUMEN_DIARIO_PIDE_HORA: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, guardar_hora_resumen),
        ],
    },
    fallbacks=[
        CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado)
    ],
)