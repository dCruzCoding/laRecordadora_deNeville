# utils.py
"""
Módulo de Utilidades Generales.

Este archivo contiene funciones de ayuda transversales que son utilizadas por
múltiples handlers para realizar tareas comunes, como:
- Parseo de texto de entrada (fechas, tiempos).
- Formateo de datos para la presentación al usuario.
- Lógica reutilizable de la interfaz de usuario (ej: listas interactivas).
- Funciones genéricas para la gestión de conversaciones.
"""

import re
from math import ceil
from datetime import datetime, timedelta
from typing import Tuple, List, Optional
import unicodedata

import pytz
from dateparser.search import search_dates
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from db import get_config, get_reminders, get_pinned_by_chat_id
from personality import get_text

# --- CONSTANTES ---
ITEMS_PER_PAGE = 10
WEEK_DAYS_MAP = {"L": "mon", "M": "tue", "X": "wed", "J": "thu", "V": "fri", "S": "sat", "D": "sun"}
WEEK_DAYS_ORDER = ["L", "M", "X", "J", "V", "S", "D"]

# --- CONSTANTES PARA LOS PATRONES ---
WEEKDAYS_SET = {"mon", "tue", "wed", "thu", "fri"}
WEEKEND_SET = {"sat", "sun"}

# --- Función de formateo para los dias del recordatorios enlistados ---
def format_week_days(week_days_db_str: str) -> str:
    """
    Traduce la cadena de días de la base de datos a un formato legible,
    reconociendo patrones comunes como "Todos los días", "Entre semana", etc.
    """
    if not week_days_db_str:
        return "Ninguno"
        
    selected_days = set(week_days_db_str.split(','))
    
    # 1. Comprobar si son todos los días
    if len(selected_days) == 7:
        return "Todos los días"
        
    # 2. Comprobar si es "Entre semana"
    if selected_days == WEEKDAYS_SET:
        return "Entre semana"
        
    # 3. Comprobar si es "Fines de semana"
    if selected_days == WEEKEND_SET:
        return "Fines de semana"
        
    # 4. Si no es ninguno de los anteriores, construir la lista normal
    ordered_day_letters = [letter for letter in WEEK_DAYS_ORDER if WEEK_DAYS_MAP[letter] in selected_days]
    
    if not ordered_day_letters:
        return "Ninguno"
        
    return ", ".join(ordered_day_letters)

# =============================================================================
# SECCIÓN 1: PARSEO Y PROCESAMIENTO DE TEXTO DE ENTRADA
# =============================================================================

def normalize_text(text: str) -> str:
    """
    Elimina acentos y convierte a minúsculas para comparaciones robustas.
    Ej: "¡Sí, claro!" -> "si, claro!"
    """
    # NFC -> descompone caracteres como 'á' en 'a' + '´'
    # Luego filtramos para quedarnos solo con los caracteres base (no diacríticos)
    text_without_accents = ''.join(
        c for c in unicodedata.normalize('NFD', text)
        if unicodedata.category(c) != 'Mn'
    )
    return text_without_accents.lower()

def normalize_hour(text: str) -> str:
    """Añade ':00' a las horas en punto para ayudar a dateparser (ej: "a las 11" -> "a las 11:00")."""
    pattern = r'(a las|a la) (\d{1,2})(?![:\d])'
    return re.sub(pattern, r'\1 \2:00', text)

def remove_date_from_text(text: str, date_text: str) -> str:
    """Elimina la parte del texto que ha sido identificada como una fecha."""
    pattern = re.escape(date_text)
    result = re.search(pattern, text, re.IGNORECASE)
    if result:
        start, end = result.span()
        clean_text = text[:start] + text[end:]
        return re.sub(r'\s+', ' ', clean_text).strip()
    return text

def parse_reminder(input_text: str, user_timezone: str = 'UTC') -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
    """
    Parsea una cadena de texto para extraer un recordatorio y una fecha.
    """
    if "*" not in input_text:
        return None, None, get_text("error_formato")
        
    date_part, text_part = input_text.split("*", 1)
    original_date_part = date_part.strip()  # Guardamos la original para limpiarla después

    try:
        user_tz_obj = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        user_tz_obj = pytz.utc

    now_in_user_tz = datetime.now(user_tz_obj)

    # --- LÓGICA INTELIGENTE PARA ENTRADAS DE SOLO HORA ---
    time_only_pattern = re.compile(r"^\s*(\d{1,2}:\d{2})\s*$")
    match = time_only_pattern.match(original_date_part)
    
    if match:
        time_str = match.group(1)
        try:
            # Parseamos la hora introducida por el usuario
            user_time = datetime.strptime(time_str, "%H:%M").time()
            
            # Comparamos con la hora actual en la zona horaria del usuario
            if user_time > now_in_user_tz.time():
                processed_date_part = f"hoy a las {time_str}"
            else:
                processed_date_part = f"mañana a las {time_str}"
        except ValueError:
            # En caso de una hora inválida como "25:70", dejamos que dateparser falle después
            processed_date_part = original_date_part
    else:
        # Si no es solo una hora, aplicamos la normalización habitual
        processed_date_part = normalize_hour(original_date_part)
    # -----------------------------------------------------------
    
    # Configuramos dateparser para que entienda el contexto del usuario.
    settings = {
        # 'future': prefiere fechas futuras (ej: "sábado" será el próximo sábado, no el pasado).
        'PREFER_DATES_FROM': 'future',
        # 'TIMEZONE': le dice a dateparser en qué zona horaria está pensando el usuario.
        'TIMEZONE': user_timezone,
        # 'RELATIVE_BASE': la fecha de referencia para términos como "mañana" o "en 2 horas".
        'RELATIVE_BASE': now_in_user_tz,
        # RETURN... True: Obliga a dateparser a devolver un objeto 'aware' en la TZ del usuario.
        'RETURN_AS_TIMEZONE_AWARE': True
    }
    
    dates = search_dates(processed_date_part, languages=['es'], settings=settings)
    
    if dates:
        found_date_text, processed_date = dates[0]
        # Convertimos la fecha procesada a UTC para almacenarla consistentemente.
        aware_datetime = user_tz_obj.localize(processed_date) if processed_date.tzinfo is None else processed_date
        utc_datetime = aware_datetime.astimezone(pytz.utc)

        # Nueva lógica de limpieza para adaptase a la nueva funcionalidad de parseo sin contexto en hora (13:30*Test)
        if match:
            # Si la entrada era solo una hora, el texto final es simplemente la parte del texto.
            final_text = text_part.strip()
        else:
            # Si no, usamos el método de limpieza original.
            final_text = (remove_date_from_text(original_date_part, found_date_text) + " " + text_part.strip()).strip()
        
        # Capitalizamos solo el primer carácter, respetando mayúsculas de nombres propios.
        if final_text:
            formatted_text = final_text[0].upper() + final_text[1:]
        else:
            formatted_text = ""

        return formatted_text, utc_datetime, None
    else:
        return None, None, get_text("error_formato")

def parse_time_to_minutes(value: str) -> Optional[int]:
    """Convierte cadenas de tiempo (ej: '2h', '1d', '30m') a minutos."""
    value = value.lower().strip()
    if value == "0":
        return 0
    try:
        if value.endswith("h"): return int(value[:-1]) * 60
        elif value.endswith("d"): return int(value[:-1]) * 1440
        elif value.endswith("m"): return int(value[:-1])
    except (ValueError, TypeError):
        return None
    return None


# =============================================================================
# SECCIÓN 2: FORMATEO DE DATOS PARA PRESENTACIÓN
# =============================================================================

def format_date_for_message(iso_date: Optional[str]) -> str:
    """Formatea una fecha en formato ISO para ser legible por el usuario."""
    if not iso_date:
        return "Sin fecha específica"
    date = datetime.fromisoformat(iso_date)
    # Si la hora es medianoche, se asume que es "todo el día" y no se muestra la hora.
    if date.hour == 0 and date.minute == 0 and date.second == 0:
        return date.strftime("%d %b %Y")
    else:
        return date.strftime("%d %b %Y, %H:%M")

def convert_utc_to_local(utc_datetime: datetime, user_timezone_str: str) -> datetime:
    """Convierte un objeto datetime de UTC a la zona horaria local del usuario."""
    if not utc_datetime or not user_timezone_str:
        return utc_datetime
    try:
        user_timezone = pytz.timezone(user_timezone_str)
        return utc_datetime.astimezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        return utc_datetime # Devuelve UTC como fallback seguro.

def _format_individual_line(chat_id: int, reminder: tuple, user_tz_global: str) -> str:
    """Formatea una única línea de la lista de recordatorios normales."""
    _, user_id, _, text, utc_date, status, prior_notice, reminder_timezone = reminder
    lines = []
    local_date = None
    
    if utc_date:
        display_timezone = reminder_timezone or user_tz_global
        local_date = convert_utc_to_local(utc_date, display_timezone)
        date_str = local_date.strftime("%d %b, %H:%M")
    else:
        date_str = "Sin fecha"
    
    prefix = "✅" if status == 1 else "⬜️"
    lines.append(f"{prefix} `#{user_id}` - {text} ({date_str})")

    if status == 0 and local_date and local_date > datetime.now(pytz.timezone(user_tz_global)) and prior_notice and prior_notice > 0:
        local_notice_date = local_date - timedelta(minutes=prior_notice)
        lines.append(f"  └─ 🔔 Aviso a las: {local_notice_date.strftime('%d %b, %H:%M')}")
        
    return "\n".join(lines)

def build_full_list_message(chat_id: int, reminders: List) -> str:
    """
    Toma una lista de recordatorios y la convierte en un único bloque de texto.
    Cada recordatorio se formatea individualmente.
    """
    if not reminders:
        # La función que llama a esta debe manejar los títulos.
        # Esta solo devuelve el mensaje de "lista vacía" si no hay nada que formatear.
        return get_text("lista_vacia")

    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    # Usa una "list comprehension" para aplicar el formateo a cada recordatorio de la lista.
    lines = [_format_individual_line(chat_id, r, user_tz) for r in reminders]
    return "\n".join(lines)


# =============================================================================
# SECCIÓN 3: COMPONENTES DE UI REUTILIZABLES
# =============================================================================

async def send_interactive_list(
    update: Update, context: ContextTypes.DEFAULT_TYPE, context_key: str,
    titles: dict, page: int = 1, filter_type: str = "future",
    show_cancel_button: bool = False
):
    """
    Función universal para generar y enviar una lista interactiva paginada.
    """
    from datetime import datetime
    chat_id = update.effective_chat.id

    reminders_page, total_items = get_reminders(chat_id, filter_type=filter_type, page=page, items_per_page=ITEMS_PER_PAGE)

    # --- MENSAJES PARA LISTAS VACÍAS ---
    if total_items == 0:
        if filter_type    == "done":
            message = "✅ No tienes ningún recordatorio marcado como 'Hecho'."
        elif filter_type == "pending":
            message = "📭 ¿No tienes nada pendiente? ¡Increíble!"
        elif filter_type == "past":
            message = "🗂️ No tienes recordatorios PASADOS."
        else: # filtro "futuro"
            message = get_text("lista_vacia")
    else:
        total_pages = ceil(total_items / ITEMS_PER_PAGE)
        title = titles.get(filter_type, "📜  **RECORDATORIOS**  📜")
        if total_pages > 1:
            title += f" (Pág. {page}/{total_pages})"
        title += "\n\n"
        list_body = build_full_list_message(chat_id, reminders_page)
        message = title + list_body
    
    # --- CONSTRUCCIÓN DEL TECLADO DINÁMICO ---
    keyboard_rows = []
    cancel_flag = "1" if show_cancel_button else "0"
    callback_suffix_base = f":{context_key}:{cancel_flag}"

    # --- Fila 1: Navegación Principal (Futuro/Pasado & Hechos/Pendientes) ---
    # AHORA SE AÑADE SIEMPRE, NO SOLO PARA el contexto "lista"
    navigation_row = []
    
    if filter_type == "past":
        navigation_row.append(InlineKeyboardButton("📜 Próximos", callback_data=f"list_pivot:future{callback_suffix_base}"))
    else:
        navigation_row.append(InlineKeyboardButton("🗂️ Pasados", callback_data=f"list_pivot:past{callback_suffix_base}"))

    if filter_type == "done":
        navigation_row.append(InlineKeyboardButton("⬜️ Pendientes", callback_data=f"list_pivot:pending{callback_suffix_base}"))
    else:
        navigation_row.append(InlineKeyboardButton("✅ Hechos", callback_data=f"list_pivot:done{callback_suffix_base}"))
    
    keyboard_rows.append(navigation_row)
    # --- Fila 2: Paginación (<< y >>) ---
    if total_items > ITEMS_PER_PAGE:
        pagination_row = []
        if page > 1:
            pagination_row.append(InlineKeyboardButton("<<", callback_data=f"list_page:{page - 1}:{filter_type}{callback_suffix_base}"))
        else:
            pagination_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        
        if page < (total_pages if 'total_pages' in locals() else 0):
            pagination_row.append(InlineKeyboardButton(">>", callback_data=f"list_page:{page + 1}:{filter_type}{callback_suffix_base}"))
        else:
            pagination_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        keyboard_rows.append(pagination_row)

    # --- Fila 3: Acciones (Limpiar, Cancelar) ---
    actions_row = []
    # El botón "Limpiar" solo tiene sentido en el contexto de /lista
    if context_key == "list":
        if filter_type == "past":
            actions_row.append(InlineKeyboardButton("🧹 Limpiar Pasados", callback_data="clean:past"))
        elif filter_type == "done":
            actions_row.append(InlineKeyboardButton("🧹 Limpiar Hechos", callback_data="clean:done"))
            
    if show_cancel_button:
        # El botón de cancelar ahora se alinea a la derecha si no hay botón de limpiar
        if not actions_row:
            actions_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        actions_row.append(InlineKeyboardButton("❌ Cancelar", callback_data="list_cancel"))
        
    if actions_row:
        keyboard_rows.append(actions_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")

# Para lista de recordatorios fijos
async def send_pinned_list(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """
    Genera y envía una lista simple y paginada de los recordatorios fijos.
    """
    chat_id = update.effective_chat.id
    pinned = get_pinned_by_chat_id(chat_id)

    if not pinned:
        message = "❌ No tienes ningún recordatorio fijo configurado."
        reply_markup = None
    else:
        # --- Paginación manual en Python ---
        total_items = len(pinned)
        total_pages = ceil(total_items / ITEMS_PER_PAGE)
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        pinned_page = pinned[start_index:end_index]
        title = "📌  **RECORDATORIOS FIJOS**  📌"
        if total_pages > 1:
            title += f" (Pág. {page}/{total_pages})"
        
        # --- Construcción de la lista ---
        message_list = []
        for pinned_id, text, time, days in pinned_page:
            days_str = format_week_days(days)
            message_list.append(f"{text} (a las {time.strftime('%H:%M')})")
            message_list.append(f"  └─ 📍 {days_str}")
        
        message = title + "\n\n" + "\n".join(message_list)

        # --- Construcción del teclado de paginación ---
        keyboard_rows = []
        if total_pages > 1:
            pagination_row = []
            if page > 1:
                pagination_row.append(InlineKeyboardButton("<<", callback_data=f"pinned_list_page:{page - 1}"))
            else:
                pagination_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
            
            if page < total_pages:
                pagination_row.append(InlineKeyboardButton(">>", callback_data=f"pinned_list_page:{page + 1}"))
            else:
                pagination_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
            keyboard_rows.append(pagination_row)
        reply_markup = InlineKeyboardMarkup(keyboard_rows)

    # --- Envío del mensaje ---
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")

# =============================================================================
# SECCIÓN 4: GESTIÓN DE CONVERSACIONES
# =============================================================================

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para el COMANDO /cancelar."""
    if context.user_data:
        context.user_data.clear()
    await update.message.reply_text(text=get_text("cancelar"), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para el BOTÓN [X] de cancelar."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=get_text("cancelar"))
    if context.user_data:
        context.user_data.clear()
    return ConversationHandler.END

async def unexpected_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback para comandos inesperados durante una conversación."""
    await update.message.reply_text(get_text("error_interrupcion"))