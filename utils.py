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

from db import get_config, get_recordatorios
from personalidad import get_text

# --- CONSTANTES ---
ITEMS_PER_PAGE = 10  # Nº de recordatorios a mostrar por página en las listas interactivas.


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
    
    Returns:
        Una tupla con (texto_formateado, fecha_utc, mensaje_de_error).
        Si tiene éxito, el mensaje de error es None.
    """
    if "*" not in texto_entrada:
        return None, None, get_text("error_formato")
        
    parte_fecha, parte_texto = texto_entrada.split("*", 1)
    parte_fecha = normalizar_hora(parte_fecha.strip())
    
    try:
        user_tz_obj = pytz.timezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        user_tz_obj = pytz.utc
    
    # Configuramos dateparser para que entienda el contexto del usuario.
    settings = {
        # 'future': prefiere fechas futuras (ej: "sábado" será el próximo sábado, no el pasado).
        'PREFER_DATES_FROM': 'future',
        # 'TIMEZONE': le dice a dateparser en qué zona horaria está pensando el usuario.
        'TIMEZONE': user_timezone,
        # 'RELATIVE_BASE': la fecha de referencia para términos como "mañana" o "en 2 horas".
        'RELATIVE_BASE': datetime.now(user_tz_obj),
        # RETURN... True: Obliga a dateparser a devolver un objeto 'aware' en la TZ del usuario.
        'RETURN_AS_TIMEZONE_AWARE': True
    }
    
    fechas = search_dates(parte_fecha, languages=['es'], settings=settings)
    
    if fechas:
        texto_fecha, fecha_procesada = fechas[0]
        fecha_aware = user_tz_obj.localize(fecha_procesada) if fecha_procesada.tzinfo is None else fecha_procesada
        fecha_utc = fecha_aware.astimezone(pytz.utc)

        texto_final = (limpiar_texto_sin_fecha(parte_fecha, texto_fecha) + " " + parte_texto.strip()).strip()
        
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
    """Formatea una única línea de la lista de recordatorios, incluyendo la info del aviso."""
    _, user_id, _, texto, fecha_utc, estado, aviso_previo, timezone_recordatorio = recordatorio
    lineas = []
    fecha_local = None

    if fecha_utc:
        # Ya no necesitamos datetime.fromisoformat(), porque ya tenemos el objeto.
        # Usa la zona horaria específica del recordatorio si existe, si no, la global del usuario.
        tz_para_mostrar = timezone_recordatorio or user_tz_global
        fecha_local = convertir_utc_a_local(fecha_utc, tz_para_mostrar)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")
    else:
        fecha_str = "Sin fecha"
    
    prefijo = "✅" if estado == 1 else "⬜️"
    lineas.append(f"{prefijo} `#{user_id}` - {texto} ({fecha_str})")
    
    # Esta parte ya estaba bien, pero la incluyo para que tengas la función completa.
    now_aware = datetime.now(pytz.timezone(user_tz_global))

    if estado == 0 and fecha_local and fecha_local > now_aware and aviso_previo and aviso_previo > 0:
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

    if context_key == "lista":
        fila_navegacion = []

        # Botón 1 (Izquierda): Alterna entre la vista de Futuro (default) y Pasado.
        # Le hemos acortado el texto a "Pendientes" para que quepa mejor.
        if filtro == "pasado":
            fila_navegacion.append(InlineKeyboardButton("📜 Próximos (Futuros)", callback_data=f"list_pivot:futuro{callback_sufijo_base}"))
        else:
            fila_navegacion.append(InlineKeyboardButton("🗂️ Pasados", callback_data=f"list_pivot:pasado{callback_sufijo_base}"))

        # Botón 2 (Derecha): Alterna entre la vista de Hechos y la de Todos los Pendientes.
        if filtro == "hechos":
            fila_navegacion.append(InlineKeyboardButton("⬜️ Pendientes", callback_data=f"list_pivot:pendientes{callback_sufijo_base}"))
        else:
            fila_navegacion.append(InlineKeyboardButton("✅ Hechos", callback_data=f"list_pivot:hechos{callback_sufijo_base}"))
        
        # Añadimos la fila con los dos botones al teclado.
        keyboard_rows.append(fila_navegacion)

    # --- Fila 2: Paginación (<< y >>) ---
    if total_items > ITEMS_PER_PAGE:
        paginacion_row = []
        # Botón Izquierdo: Anterior o placeholder
        if page > 1:
            paginacion_row.append(InlineKeyboardButton("<<", callback_data=f"list_page:{page - 1}:{filtro}{callback_sufijo_base}"))
        else:
            paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        
        # Botón Derecho: Siguiente o placeholder
        if page < total_pages:
            paginacion_row.append(InlineKeyboardButton(">>", callback_data=f"list_page:{page + 1}:{filtro}{callback_sufijo_base}"))
        else:
            paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        keyboard_rows.append(paginacion_row)

    # --- Fila 3: Acciones (Limpiar, Cancelar) ---
    acciones_row = []
    if context_key == "lista":
        if filtro == "pasado":
            # Formato: "limpiar:filtro_ask"
            acciones_row.append(InlineKeyboardButton("🧹 Limpiar Pasados", callback_data="limpiar:pasados_ask"))
        elif filtro == "hechos":
            acciones_row.append(InlineKeyboardButton("🧹 Limpiar Hechos", callback_data="limpiar:hechos_ask"))
            
    if mostrar_boton_cancelar:
        acciones_row.append(InlineKeyboardButton("❌ Cancelar", callback_data="list_cancel"))
        
    if acciones_row:
        keyboard_rows.append(acciones_row)
    
    reply_markup = InlineKeyboardMarkup(keyboard_rows)

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