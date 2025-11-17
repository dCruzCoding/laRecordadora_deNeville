# handlers/fijos.py
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, ConversationHandler, CommandHandler,
    MessageHandler, filters, CallbackQueryHandler
)

from db import (
    get_config, add_recordatorio_fijo, get_fijos_by_chat_id,
    update_fijo_by_id, delete_fijo_by_id, check_fijo_exists
)
from utils import (
    cancelar_callback, comando_inesperado, cancelar_conversacion,
    formatear_dias_semana, normalizar_texto, 
    DIAS_SEMANA, DIAS_SEMANA_ORDEN
)
from avisos import programar_recordatorio_fijo_diario, cancelar_avisos
from personalidad import get_text

# --- Definición de Estados ---
(
    MENU_FIJO,
    AÑADIR_PIDE_DATOS, AÑADIR_PIDE_DIAS,
    ELEGIR_ID_BORRAR_FIJO, CONFIRMAR_BORRADO_FIJO,
    ELEGIR_ID_EDITAR_FIJO, RECIBIR_NUEVOS_DATOS_FIJOS,
    EDITAR_PIDE_DIAS 
) = range(8)

# =============================================================================
# FUNCIONES DE AYUDA PARA EL TECLADO
# =============================================================================

def _build_days_keyboard(dias_seleccionados: set) -> InlineKeyboardMarkup:
    """Construye el teclado interactivo para seleccionar los días."""
    keyboard_rows = []
    row = []
    for dia_letra in DIAS_SEMANA_ORDEN:
        texto_boton = f"✅ {dia_letra}" if DIAS_SEMANA[dia_letra] in dias_seleccionados else dia_letra
        row.append(InlineKeyboardButton(texto_boton, callback_data=f"fijo_dia_{DIAS_SEMANA[dia_letra]}"))
    keyboard_rows.append(row)
    keyboard_rows.append([InlineKeyboardButton("🗓️ Todos los días", callback_data="fijo_dia_todos")])
    keyboard_rows.append([InlineKeyboardButton("✅ ¡Listo!", callback_data="fijo_dias_done")])
    return InlineKeyboardMarkup(keyboard_rows)

# =============================================================================
# FUNCIONES DE LA CONVERSACIÓN
# =============================================================================

async def fijo_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Punto de entrada. Muestra el menú de gestión de recordatorios fijos."""
    keyboard = [
        [InlineKeyboardButton("➕ Añadir", callback_data="fijo_add"),
         InlineKeyboardButton("✍️ Editar", callback_data="fijo_edit")],
        [InlineKeyboardButton("🗑️ Borrar", callback_data="fijo_delete"),
        InlineKeyboardButton("❌ Salir", callback_data="fijo_cancel")],
    ]
    await update.message.reply_text(
        "🔁 Gestión de Recordatorios Fijos\n\n¿Qué quieres hacer?",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return MENU_FIJO

# --- Ayudante para mostrar la lista de fijos ---
async def _mostrar_lista_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE, texto_introduccion: str):
    chat_id = update.effective_chat.id
    fijos = get_fijos_by_chat_id(chat_id)
    if not fijos:
        await context.bot.send_message(chat_id, "No tienes ningún recordatorio fijo configurado.")
        return False
    
    mensaje_lista = [texto_introduccion]
    for fijo_id, texto, hora, dias in fijos:   # Ahora 'dias' es una cadena como "mon,tue,fri"
        # Hacemos la conversión inversa para mostrar las letras
        dias_str = formatear_dias_semana(dias)
        mensaje_lista.append(f"`#{fijo_id}`: {texto} (a las {hora.strftime('%H:%M')})")
        mensaje_lista.append(f"    └─ 📍 {dias_str}")

    await context.bot.send_message(chat_id, "\n".join(mensaje_lista), parse_mode="Markdown")
    return True

# --- Flujo de Añadir (Ahora en 2 pasos) ---
async def fijo_pide_datos_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("➕ **Añadir Recordatorio Fijo**", parse_mode="Markdown")
    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="**Paso 1 de 2:** Escribe la nueva hora y texto con el formato `HH:MM * Texto`.",
        parse_mode="Markdown"
    )
    
    return AÑADIR_PIDE_DATOS

async def fijo_recibe_datos_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    entrada = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return AÑADIR_PIDE_DATOS
    
    context.user_data['fijo_add_hora'], context.user_data['fijo_add_texto'] = match.groups()
    context.user_data['dias_seleccionados'] = set(DIAS_SEMANA.values()) # Por defecto, todos los días

    context.user_data['fijo_context'] = 'add'  # Añadimos contexto para la función generalizada de selección de días
    
    keyboard = _build_days_keyboard(context.user_data['dias_seleccionados'])
    await update.message.reply_text(
        "📆 **Paso 2 de 2:** ¿Qué días quieres que se repita? (Por defecto, todos)",
        reply_markup=keyboard
    )
    return AÑADIR_PIDE_DIAS

async def fijo_recibe_dia_seleccion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    
    dia_cod = query.data.split('_')[-1] # ej: "fijo_dia_mon" -> "mon"
    dias_seleccionados = context.user_data.get('dias_seleccionados', set())

    if dia_cod == "todos":
        # Si ya están todos, los quitamos todos. Si no, los seleccionamos todos.
        if len(dias_seleccionados) == 7:
            dias_seleccionados.clear()
        else:
            dias_seleccionados = set(DIAS_SEMANA.values())
    else:
        if dia_cod in dias_seleccionados:
            dias_seleccionados.remove(dia_cod)
        else:
            dias_seleccionados.add(dia_cod)
            
    context.user_data['dias_seleccionados'] = dias_seleccionados
    
    keyboard = _build_days_keyboard(dias_seleccionados)
    await query.edit_message_text(
        text="**Paso 2 de 2:** ¿Qué días quieres que se repita?",
        reply_markup=keyboard
    )
    
    # Leemos el contexto que guardamos y devolvemos el estado correcto.
    if context.user_data.get('fijo_context') == 'edit':
        return EDITAR_PIDE_DIAS
    else: # Por defecto, o si es 'add'
        return AÑADIR_PIDE_DIAS

async def fijo_finaliza_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    dias_seleccionados = context.user_data.get('dias_seleccionados')
    if not dias_seleccionados:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="⚠️ Debes seleccionar al menos un día."
        )
        return AÑADIR_PIDE_DIAS

    hora_str = context.user_data['fijo_add_hora']
    texto = context.user_data['fijo_add_texto']
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    
    # Ordenamos los días para guardarlos consistentemente (mon,tue,wed...)
    dias_ordenados = sorted(list(dias_seleccionados), key=lambda d: list(DIAS_SEMANA.values()).index(d))
    dias_str_db = ",".join(dias_ordenados)

    fijo_id = add_recordatorio_fijo(chat_id, texto, hora_str, user_tz, dias_str_db)
    hora, minuto = map(int, hora_str.split(':'))
    
    programar_recordatorio_fijo_diario(chat_id, fijo_id, texto, hora, minuto, user_tz, dias_str_db)
    
    await query.edit_message_text(f"✅ ¡Añadido! Recordatorio fijo `#{fijo_id}` programado para los días seleccionados.")
    
    context.user_data.clear()
    return ConversationHandler.END

# --- Flujo de Borrar ---
async def fijo_pide_id_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("🗑️ **Borrar Recordatorio Fijo**", parse_mode="Markdown")
    if await _mostrar_lista_fijos(update, context, "Dime el ID del recordatorio fijo que quieres borrar:\n"):
        return ELEGIR_ID_BORRAR_FIJO
    return ConversationHandler.END

async def fijo_procesa_id_para_borrar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Recibe el ID a borrar, lo valida y, si el Modo Seguro está activo, pide confirmación.
    Si no, borra directamente.
    """
    chat_id = update.effective_chat.id
    try:
        fijo_id = int(update.message.text.strip().replace("#", ""))
    except ValueError:
        await update.message.reply_text("Por favor, introduce solo un número.")
        return ELEGIR_ID_BORRAR_FIJO

    # Validamos que el ID existe y pertenece al usuario
    fijos = get_fijos_by_chat_id(chat_id)
    recordatorio_a_borrar = next((f for f in fijos if f[0] == fijo_id), None)

    if not recordatorio_a_borrar:
        await update.message.reply_text(f"❌ No he encontrado un recordatorio fijo con el ID #{fijo_id}.")
        return ELEGIR_ID_BORRAR_FIJO

    # Guardamos el ID en el contexto para el siguiente paso
    context.user_data["fijo_id_a_borrar"] = fijo_id

    # --- LÓGICA DE MODO SEGURO ---
    modo_seguro = int(get_config(chat_id, "modo_seguro") or 0)
    if modo_seguro in (1, 3): # Niveles que requieren confirmación de borrado
        _, texto, hora, dias = recordatorio_a_borrar
        dias_str = formatear_dias_semana(dias) # Reutilizamos la función que ya tienes
        
        mensaje_confirmacion = (
            f"👵 ¡Quieto ahí! Vas a borrar permanentemente el recordatorio fijo:\n\n"
            f"  - `#{fijo_id}`: {texto} (a las {hora.strftime('%H:%M')}) [{dias_str}]\n\n"
            "¿Estás completamente seguro? Escribe `SI` para confirmar."
        )
        await update.message.reply_text(mensaje_confirmacion, parse_mode="Markdown")
        return CONFIRMAR_BORRADO_FIJO
    else:
        # Si no se requiere confirmación, borramos directamente
        return await _ejecutar_borrado_fijo_final(update, context)

async def fijo_confirma_y_borra(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la confirmación 'SI' y ejecuta el borrado."""
    respuesta = normalizar_texto(update.message.text)
    if respuesta.startswith("si"):
        return await _ejecutar_borrado_fijo_final(update, context)
    else:
        await update.message.reply_text(get_text("cancelar"))
        context.user_data.clear()
        return ConversationHandler.END

async def _ejecutar_borrado_fijo_final(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Lógica final que realiza el borrado en la DB y el scheduler."""
    fijo_id = context.user_data.get("fijo_id_a_borrar")
    if fijo_id is None: # Salvaguarda
        return ConversationHandler.END

    num_borrados = delete_fijo_by_id(fijo_id)
    if num_borrados > 0:
        cancelar_avisos(f"fijo_{fijo_id}")
        await update.message.reply_text(f"✅ Recordatorio fijo `#{fijo_id}` borrado permanentemente.")
    else:
        # Este mensaje no debería aparecer si la validación previa funcionó
        await update.message.reply_text(f"❌ No he encontrado un recordatorio fijo con el ID #{fijo_id}.")
        
    context.user_data.clear()
    return ConversationHandler.END

# --- Flujo de Editar ---
async def fijo_pide_id_editar(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✍️ **Editar Recordatorio Fijo**", parse_mode="Markdown")
    if await _mostrar_lista_fijos(update, context, "Dime el ID del recordatorio fijo a editar:\n"):
        return ELEGIR_ID_EDITAR_FIJO
    return ConversationHandler.END

async def fijo_pide_nuevos_datos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Valida el ID proporcionado por el usuario. Si es válido, pide los nuevos datos.
    """
    chat_id = update.effective_chat.id
    try:
        fijo_id = int(update.message.text.strip().replace("#", ""))
    except ValueError:
        await update.message.reply_text("Eso no es un número válido. Por favor, dime el ID del recordatorio que quieres editar:")
        return ELEGIR_ID_EDITAR_FIJO # Mantenemos al usuario en el paso de elegir ID

    if check_fijo_exists(fijo_id, chat_id):
        # El ID es válido y pertenece al usuario, procedemos.
        context.user_data["fijo_id_a_editar"] = fijo_id
        await update.message.reply_text(
            "Entendido. **Paso 1 de 2:** Escribe la nueva hora y texto con el formato `HH:MM * Texto`.",
            parse_mode="Markdown"
        )
        return RECIBIR_NUEVOS_DATOS_FIJOS
    else:
        # El ID no existe o no pertenece al usuario.
        await update.message.reply_text(f"❌ No he encontrado ningún recordatorio fijo con el ID #{fijo_id}. Prueba de nuevo.")
        return ELEGIR_ID_EDITAR_FIJO # Devolvemos al usuario al paso anterior

async def fijo_ejecuta_edicion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Recibe la nueva hora/texto y pasa al paso de selección de días."""
    entrada = update.message.text
    match = re.match(r"^\s*(\d{1,2}:\d{2})\s*\*\s*(.+)$", entrada, re.DOTALL)
    if not match:
        await update.message.reply_text("❗ Formato incorrecto. Usa `HH:MM * Texto`.")
        return RECIBIR_NUEVOS_DATOS_FIJOS
    
    # Guardamos los nuevos datos para el paso final
    context.user_data["fijo_edit_nueva_hora"], context.user_data["fijo_edit_nuevo_texto"] = match.groups()

    # ¡REUTILIZACIÓN! Usamos el mismo teclado de días que el flujo de "Añadir".
    # Inicializamos los días con "Todos seleccionados" como en el flujo de añadir,
    # el usuario puede ajustarlo desde ahí.
    dias_seleccionados = set(DIAS_SEMANA.values())
    context.user_data['dias_seleccionados'] = dias_seleccionados

    context.user_data['fijo_context'] = 'edit' # Añadimos contexto para la función generalizada de selección de días

    keyboard = _build_days_keyboard(dias_seleccionados)
    await update.message.reply_text(
        "📆 **Paso 2 de 2:** Hora y texto actualizados. Ahora, selecciona los días para este recordatorio:",
        reply_markup=keyboard
    )
    return EDITAR_PIDE_DIAS

async def fijo_finaliza_edit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Guarda todos los cambios del recordatorio fijo editado."""
    query = update.callback_query
    await query.answer()

    dias_seleccionados = context.user_data.get('dias_seleccionados')
    if not dias_seleccionados:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="⚠️ Debes seleccionar al menos un día.")
        return EDITAR_PIDE_DIAS

    # Recuperamos todos los datos guardados en el contexto
    fijo_id = context.user_data["fijo_id_a_editar"]
    nueva_hora = context.user_data["fijo_edit_nueva_hora"]
    nuevo_texto = context.user_data["fijo_edit_nuevo_texto"]
    chat_id = update.effective_chat.id
    user_tz = get_config(chat_id, "user_timezone") or "UTC"
    
    dias_ordenados = sorted(list(dias_seleccionados), key=lambda d: list(DIAS_SEMANA.values()).index(d))
    dias_str_db = ",".join(dias_ordenados)

    # ¡LA DIFERENCIA CLAVE! Llamamos a UPDATE en lugar de a ADD.
    update_fijo_by_id(fijo_id, nuevo_texto, nueva_hora, dias_str_db)
    
    # Reprogramamos el job con la información actualizada
    hora, minuto = map(int, nueva_hora.split(':'))
    programar_recordatorio_fijo_diario(chat_id, fijo_id, nuevo_texto, hora, minuto, user_tz, dias_str_db)
    
    await query.edit_message_text(f"✅ ¡Actualizado! El recordatorio fijo `#{fijo_id}` ha sido modificado.")
    
    context.user_data.clear()
    return ConversationHandler.END

# =============================================================================
# CONVERSATION HANDLER
# =============================================================================
fijo_handler = ConversationHandler(
    entry_points= [CommandHandler(['fijo', 'fijos', 'recurrente', 'recurrentes', 'pinned'], fijo_cmd)],
    states={
        MENU_FIJO: [
            CallbackQueryHandler(fijo_pide_datos_add, pattern="^fijo_add$"),
            CallbackQueryHandler(fijo_pide_id_editar, pattern="^fijo_edit$"),
            CallbackQueryHandler(fijo_pide_id_borrar, pattern="^fijo_delete$"),
            CallbackQueryHandler(cancelar_callback, pattern="^fijo_cancel$"),
        ],

        # --- Flujo de Añadir ---
        AÑADIR_PIDE_DATOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_recibe_datos_add)],
        AÑADIR_PIDE_DIAS: [
            CallbackQueryHandler(fijo_recibe_dia_seleccion, pattern="^fijo_dia_"),
            CallbackQueryHandler(fijo_finaliza_add, pattern="^fijo_dias_done$"),
        ],

        # --- Flujo de Borrar ---
        ELEGIR_ID_BORRAR_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_procesa_id_para_borrar)],
        CONFIRMAR_BORRADO_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_confirma_y_borra)],

        # --- Flujo de Editar ---
        ELEGIR_ID_EDITAR_FIJO: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_pide_nuevos_datos)],
        RECIBIR_NUEVOS_DATOS_FIJOS: [MessageHandler(filters.TEXT & ~filters.COMMAND, fijo_ejecuta_edicion)],
        EDITAR_PIDE_DIAS: [
            # ¡REUTILIZACIÓN! La función que maneja el clic en un día es la misma.
            CallbackQueryHandler(fijo_recibe_dia_seleccion, pattern="^fijo_dia_"),
            # Pero la función que finaliza es la específica de editar.
            CallbackQueryHandler(fijo_finaliza_edit, pattern="^fijo_dias_done$"),
        ],
    },
    fallbacks=[CommandHandler("cancelar", cancelar_conversacion),
        MessageHandler(filters.COMMAND, comando_inesperado) 
],
)