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

from db import get_config, get_recordatorios, get_fijos_by_chat_id
from personalidad import get_text

# --- CONSTANTES ---
ITEMS_PER_PAGE = 10
DIAS_SEMANA = {"L": "mon", "M": "tue", "X": "wed", "J": "thu", "V": "fri", "S": "sat", "D": "sun"}
DIAS_SEMANA_ORDEN = ["L", "M", "X", "J", "V", "S", "D"]

# --- CONSTANTES PARA LOS PATRONES ---
ENTRE_SEMANA_SET = {"mon", "tue", "wed", "thu", "fri"}
FIN_DE_SEMANA_SET = {"sat", "sun"}

# --- Función de formateo para los dias del recordatorios enlistados ---
def formatear_dias_semana(dias_db_str: str) -> str:
    """
    Traduce la cadena de días de la base de datos a un formato legible,
    reconociendo patrones comunes como "Todos los días", "Entre semana", etc.
    """
    if not dias_db_str:
        return "Ninguno"
        
    dias_seleccionados = set(dias_db_str.split(','))
    
    # 1. Comprobar si son todos los días
    if len(dias_seleccionados) == 7:
        return "Todos los días"
        
    # 2. Comprobar si es "Entre semana"
    if dias_seleccionados == ENTRE_SEMANA_SET:
        return "Entre semana"
        
    # 3. Comprobar si es "Fines de semana"
    if dias_seleccionados == FIN_DE_SEMANA_SET:
        return "Fines de semana"
        
    # 4. Si no es ninguno de los anteriores, construir la lista normal
    letras_dias_ordenadas = [letra for letra in DIAS_SEMANA_ORDEN if DIAS_SEMANA[letra] in dias_seleccionados]
    
    if not letras_dias_ordenadas:
        return "Ninguno"
        
    return ", ".join(letras_dias_ordenadas)

# =============================================================================
# SECCIÓN 1: PARSEO Y PROCESAMIENTO DE TEXTO DE ENTRADA
# =============================================================================

def normalizar_texto(texto: str) -> str:
    """
    Elimina acentos y convierte a minúsculas para comparaciones robustas.
    Ej: "¡Sí, claro!" -> "si, claro!"
    """
    # NFC -> descompone caracteres como 'á' en 'a' + '´'
    # Luego filtramos para quedarnos solo con los caracteres base (no diacríticos)
    texto_sin_acentos = ''.join(
        c for c in unicodedata.normalize('NFD', texto)
        if unicodedata.category(c) != 'Mn'
    )
    return texto_sin_acentos.lower()

def normalizar_hora(texto: str) -> str:
    """Añade ':00' a las horas en punto para ayudar a dateparser (ej: "a las 11" -> "a las 11:00")."""
    patron = r'(a las|a la) (\d{1,2})(?![:\d])'
    return re.sub(patron, r'\1 \2:00', texto)

def limpiar_texto_sin_fecha(texto: str, texto_fecha: str) -> str:
    """Elimina la parte del texto que ha sido identificada como una fecha."""
    patron = re.escape(texto_fecha)
    resultado = re.search(patron, texto, re.IGNORECASE)
    if resultado:
        start, end = resultado.span()
        texto_limpio = texto[:start] + texto[end:]
        return re.sub(r'\s+', ' ', texto_limpio).strip()
    return texto

def parsear_recordatorio(texto_entrada: str, user_timezone: str = 'UTC') -> Tuple[Optional[str], Optional[datetime], Optional[str]]:
    """
    Parsea una cadena de texto para extraer un recordatorio y una fecha.
    """
    if "*" not in texto_entrada:
        return None, None, get_text("error_formato")
        
    parte_fecha, parte_texto = texto_entrada.split("*", 1)
    parte_fecha_original = parte_fecha.strip()  # Guardamos la original para limpiarla después

    try:
        user_tz_obj = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        user_tz_obj = pytz.utc

    now_in_user_tz = datetime.now(user_tz_obj)

    # --- LÓGICA INTELIGENTE PARA ENTRADAS DE SOLO HORA ---
    time_only_pattern = re.compile(r"^\s*(\d{1,2}:\d{2})\s*$")
    match = time_only_pattern.match(parte_fecha_original)
    
    if match:
        hora_str = match.group(1)
        try:
            # Parseamos la hora introducida por el usuario
            hora_usuario = datetime.strptime(hora_str, "%H:%M").time()
            
            # Comparamos con la hora actual en la zona horaria del usuario
            if hora_usuario > now_in_user_tz.time():
                parte_fecha_procesada = f"hoy a las {hora_str}"
            else:
                parte_fecha_procesada = f"mañana a las {hora_str}"
        except ValueError:
            # En caso de una hora inválida como "25:70", dejamos que dateparser falle después
            parte_fecha_procesada = parte_fecha_original
    else:
        # Si no es solo una hora, aplicamos la normalización habitual
        parte_fecha_procesada = normalizar_hora(parte_fecha_original)
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
    
    fechas = search_dates(parte_fecha_procesada, languages=['es'], settings=settings)
    
    if fechas:
        texto_fecha_encontrado, fecha_procesada = fechas[0]

        # Convertimos la fecha procesada a UTC para almacenarla consistentemente.
        fecha_aware = user_tz_obj.localize(fecha_procesada) if fecha_procesada.tzinfo is None else fecha_procesada
        fecha_utc = fecha_aware.astimezone(pytz.utc)

        # Nueva lógica de limpieza para adaptase a la nueva funcionalidad de parseo sin contexto en hora (13:30*Test)
        if match:
            # Si la entrada era solo una hora, el texto final es simplemente la parte del texto.
            texto_final = parte_texto.strip()
        else:
            # Si no, usamos el método de limpieza original.
            texto_final = (limpiar_texto_sin_fecha(parte_fecha_original, texto_fecha_encontrado) + " " + parte_texto.strip()).strip()
        
        # Capitalizamos solo el primer carácter, respetando mayúsculas de nombres propios.
        if texto_final:
            texto_formateado = texto_final[0].upper() + texto_final[1:]
        else:
            texto_formateado = ""

        return texto_formateado, fecha_utc, None
    else:
        return None, None, get_text("error_formato")

def parsear_tiempo_a_minutos(valor: str) -> Optional[int]:
    """Convierte cadenas de tiempo (ej: '2h', '1d', '30m') a minutos."""
    valor = valor.lower().strip()
    if valor == "0":
        return 0
    try:
        if valor.endswith("h"): return int(valor[:-1]) * 60
        elif valor.endswith("d"): return int(valor[:-1]) * 1440
        elif valor.endswith("m"): return int(valor[:-1])
    except (ValueError, TypeError):
        return None
    return None


# =============================================================================
# SECCIÓN 2: FORMATEO DE DATOS PARA PRESENTACIÓN
# =============================================================================

def formatear_fecha_para_mensaje(fecha_iso: Optional[str]) -> str:
    """Formatea una fecha en formato ISO para ser legible por el usuario."""
    if not fecha_iso:
        return "Sin fecha específica"
    fecha = datetime.fromisoformat(fecha_iso)
    # Si la hora es medianoche, se asume que es "todo el día" y no se muestra la hora.
    if fecha.hour == 0 and fecha.minute == 0 and fecha.second == 0:
        return fecha.strftime("%d %b %Y")
    else:
        return fecha.strftime("%d %b %Y, %H:%M")

def convertir_utc_a_local(fecha_utc: datetime, user_timezone_str: str) -> datetime:
    """Convierte un objeto datetime de UTC a la zona horaria local del usuario."""
    if not fecha_utc or not user_timezone_str:
        return fecha_utc
    try:
        user_timezone = pytz.timezone(user_timezone_str)
        return fecha_utc.astimezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        return fecha_utc # Devuelve UTC como fallback seguro.

def _formatear_linea_individual(chat_id: int, recordatorio: tuple, user_tz_global: str) -> str:
    """Formatea una única línea de la lista de recordatorios normales."""
    _, user_id, _, texto, fecha_utc, estado, aviso_previo, timezone_recordatorio = recordatorio

    lineas = []
    fecha_local = None

    if fecha_utc:
        tz_para_mostrar = timezone_recordatorio or user_tz_global
        fecha_local = convertir_utc_a_local(fecha_utc, tz_para_mostrar)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")
    else:
        fecha_str = "Sin fecha"
    
    prefijo = "✅" if estado == 1 else "⬜️"
    lineas.append(f"{prefijo} `#{user_id}` - {texto} ({fecha_str})")

    if estado == 0 and fecha_local and fecha_local > datetime.now(pytz.timezone(user_tz_global)) and aviso_previo and aviso_previo > 0:
        fecha_aviso_local = fecha_local - timedelta(minutes=aviso_previo)
        lineas.append(f"  └─ 🔔 Aviso a las: {fecha_aviso_local.strftime('%d %b, %H:%M')}")
        
    return "\n".join(lineas)

def construir_mensaje_lista_completa(chat_id: int, recordatorios: List) -> str:
    """
    Toma una lista de recordatorios y la convierte en un único bloque de texto.
    Cada recordatorio se formatea individualmente.
    """
    if not recordatorios:
        # La función que llama a esta debe manejar los títulos.
        # Esta solo devuelve el mensaje de "lista vacía" si no hay nada que formatear.
        return get_text("lista_vacia")

    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    # Usa una "list comprehension" para aplicar el formateo a cada recordatorio de la lista.
    lineas = [_formatear_linea_individual(chat_id, r, user_tz) for r in recordatorios]
    return "\n".join(lineas)


# =============================================================================
# SECCIÓN 3: COMPONENTES DE UI REUTILIZABLES
# =============================================================================

async def enviar_lista_interactiva(
    update: Update, context: ContextTypes.DEFAULT_TYPE, context_key: str,
    titulos: dict, page: int = 1, filtro: str = "futuro",
    mostrar_boton_cancelar: bool = False
):
    """
    Función universal para generar y enviar una lista interactiva paginada.
    """
    from datetime import datetime
    chat_id = update.effective_chat.id

    recordatorios_pagina, total_items = get_recordatorios(chat_id, filtro=filtro, page=page, items_per_page=ITEMS_PER_PAGE)

    # --- MENSAJES PARA LISTAS VACÍAS ---
    if total_items == 0:
        if filtro == "hechos":
            mensaje = "✅ No tienes ningún recordatorio marcado como 'Hecho'."
        elif filtro == "pendientes":
            mensaje = "📭 ¿No tienes nada pendiente? ¡Increíble!"
        elif filtro == "pasado":
            mensaje = "🗂️ No tienes recordatorios PASADOS."
        else: # filtro "futuro"
            mensaje = get_text("lista_vacia")
    else:
        total_pages = ceil(total_items / ITEMS_PER_PAGE)
        titulo = titulos.get(filtro, "📜  **RECORDATORIOS**  📜")
        if total_pages > 1:
            titulo += f" (Pág. {page}/{total_pages})"
        titulo += "\n\n"
        cuerpo_lista = construir_mensaje_lista_completa(chat_id, recordatorios_pagina)
        mensaje = titulo + cuerpo_lista
    
    # --- CONSTRUCCIÓN DEL TECLADO DINÁMICO ---
    keyboard_rows = []
    cancel_flag = "1" if mostrar_boton_cancelar else "0"
    callback_sufijo_base = f":{context_key}:{cancel_flag}"

    # --- Fila 1: Navegación Principal (Futuro/Pasado & Hechos/Pendientes) ---
    # AHORA SE AÑADE SIEMPRE, NO SOLO PARA el contexto "lista"
    fila_navegacion = []
    
    if filtro == "pasado":
        fila_navegacion.append(InlineKeyboardButton("📜 Próximos", callback_data=f"list_pivot:futuro{callback_sufijo_base}"))
    else:
        fila_navegacion.append(InlineKeyboardButton("🗂️ Pasados", callback_data=f"list_pivot:pasado{callback_sufijo_base}"))

    if filtro == "hechos":
        fila_navegacion.append(InlineKeyboardButton("⬜️ Pendientes", callback_data=f"list_pivot:pendientes{callback_sufijo_base}"))
    else:
        fila_navegacion.append(InlineKeyboardButton("✅ Hechos", callback_data=f"list_pivot:hechos{callback_sufijo_base}"))
    
    keyboard_rows.append(fila_navegacion)

    # --- Fila 2: Paginación (<< y >>) ---
    if total_items > ITEMS_PER_PAGE:
        paginacion_row = []
        if page > 1:
            paginacion_row.append(InlineKeyboardButton("<<", callback_data=f"list_page:{page - 1}:{filtro}{callback_sufijo_base}"))
        else:
            paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        
        if page < (total_pages if 'total_pages' in locals() else 0):
            paginacion_row.append(InlineKeyboardButton(">>", callback_data=f"list_page:{page + 1}:{filtro}{callback_sufijo_base}"))
        else:
            paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        keyboard_rows.append(paginacion_row)

    # --- Fila 3: Acciones (Limpiar, Cancelar) ---
    acciones_row = []
    # El botón "Limpiar" solo tiene sentido en el contexto de /lista
    if context_key == "lista":
        if filtro == "pasado":
            acciones_row.append(InlineKeyboardButton("🧹 Limpiar Pasados", callback_data="limpiar:pasados_ask"))
        elif filtro == "hechos":
            acciones_row.append(InlineKeyboardButton("🧹 Limpiar Hechos", callback_data="limpiar:hechos_ask"))
            
    if mostrar_boton_cancelar:
        # El botón de cancelar ahora se alinea a la derecha si no hay botón de limpiar
        if not acciones_row:
            acciones_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        acciones_row.append(InlineKeyboardButton("❌ Cancelar", callback_data="list_cancel"))
        
    if acciones_row:
        keyboard_rows.append(acciones_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")

# Para lista de recordatorios fijos
async def enviar_lista_fijos(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 1):
    """
    Genera y envía una lista simple y paginada de los recordatorios fijos.
    """
    chat_id = update.effective_chat.id
    fijos = get_fijos_by_chat_id(chat_id)

    if not fijos:
        mensaje = "❌ No tienes ningún recordatorio fijo configurado."
        reply_markup = None
    else:
        # --- Paginación manual en Python ---
        total_items = len(fijos)
        total_pages = ceil(total_items / ITEMS_PER_PAGE)
        start_index = (page - 1) * ITEMS_PER_PAGE
        end_index = start_index + ITEMS_PER_PAGE
        fijos_pagina = fijos[start_index:end_index]

        titulo = "📌  **RECORDATORIOS FIJOS**  📌"
        if total_pages > 1:
            titulo += f" (Pág. {page}/{total_pages})"
        
        # --- Construcción de la lista ---
        mensaje_lista = []
        for fijo_id, texto, hora, dias in fijos_pagina:
            dias_str = formatear_dias_semana(dias)
            mensaje_lista.append(f"{texto} (a las {hora.strftime('%H:%M')})")
            mensaje_lista.append(f"  └─ 📍 {dias_str}")
        
        mensaje = titulo + "\n\n" + "\n".join(mensaje_lista)

        # --- Construcción del teclado de paginación ---
        keyboard_rows = []
        if total_pages > 1:
            paginacion_row = []
            if page > 1:
                paginacion_row.append(InlineKeyboardButton("<<", callback_data=f"fijo_list_page:{page - 1}"))
            else:
                paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
            
            if page < total_pages:
                paginacion_row.append(InlineKeyboardButton(">>", callback_data=f"fijo_list_page:{page + 1}"))
            else:
                paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
            keyboard_rows.append(paginacion_row)
        reply_markup = InlineKeyboardMarkup(keyboard_rows)

    # --- Envío del mensaje ---
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=mensaje, reply_markup=reply_markup, parse_mode="Markdown")

# =============================================================================
# SECCIÓN 4: GESTIÓN DE CONVERSACIONES
# =============================================================================

async def cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para el COMANDO /cancelar."""
    if context.user_data:
        context.user_data.clear()
    await update.message.reply_text(text=get_text("cancelar"), reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END

async def cancelar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Función de fallback para el BOTÓN [X] de cancelar."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(text=get_text("cancelar"))
    if context.user_data:
        context.user_data.clear()
    return ConversationHandler.END

async def comando_inesperado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fallback para comandos inesperados durante una conversación."""
    await update.message.reply_text(get_text("error_interrupcion"))