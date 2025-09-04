import re
import pytz
from math import ceil
from datetime import datetime, timedelta
from dateparser.search import search_dates
from personalidad import get_text
from db import get_config, get_recordatorios
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler
)

def normalizar_hora(texto):
    """
    Añade ':00' a las horas en punto para ayudar a dateparser.
    Ej: "a las 11" -> "a las 11:00"
    """
    patron = r'(a las|a la) (\d{1,2})(?![:\d])'
    return re.sub(patron, r'\1 \2:00', texto)

def limpiar_texto_sin_fecha(texto, texto_fecha):
    patron = re.escape(texto_fecha)
    resultado = re.search(patron, texto, re.IGNORECASE)
    if resultado:
        start, end = resultado.span()
        texto_limpio = texto[:start] + texto[end:]
        texto_limpio = re.sub(r'\s+', ' ', texto_limpio).strip()
        return texto_limpio
    else:
        return texto

def parsear_recordatorio(texto_entrada, user_timezone='UTC'):
    """
    Parsea una cadena de texto para extraer un recordatorio y una fecha.
    La fecha devuelta siempre estará en formato UTC.
    """
    if "*" not in texto_entrada:
        return None, None, get_text("error_formato")
        
    parte_fecha, parte_texto = texto_entrada.split("*", 1)
    parte_fecha = normalizar_hora(parte_fecha.strip())
    
    try:
        user_tz_obj = pytz.timezone(user_timezone)
        now_in_user_timezone = datetime.now(user_tz_obj)
    except pytz.UnknownTimeZoneError:
        user_tz_obj = pytz.utc
        now_in_user_timezone = datetime.now(user_tz_obj)

    # Configuración esencial para dateparser
    settings = {
        'PREFER_DATES_FROM': 'future',
        'TIMEZONE': user_timezone,
        'RELATIVE_BASE': now_in_user_timezone
    }
    
    fechas = search_dates(parte_fecha, languages=['es'], settings=settings)
    
    if fechas:
        texto_fecha, fecha_naive = fechas[0]
        
        # Forzamos la fecha a ser "consciente" con la zona horaria del usuario
        fecha_aware = user_tz_obj.localize(fecha_naive) if fecha_naive.tzinfo is None else fecha_naive
        
        # La convertimos a UTC para el almacenamiento y la programación
        fecha_utc = fecha_aware.astimezone(pytz.utc)
        
        texto = limpiar_texto_sin_fecha(parte_fecha, texto_fecha) + " " + parte_texto.strip()
        if texto:
            # Creamos el nuevo texto cogiendo el primer carácter, poniéndolo en mayúscula,
            # y luego concatenando el RESTO de la cadena (desde el segundo carácter hasta el final).
            texto_formateado = texto[0].upper() + texto[1:]
        else:
            texto_formateado = ""

        return texto_formateado, fecha_utc, None
    else:
        return None, None, get_text("error_formato")

def formatear_fecha_para_mensaje(fecha_iso):
    if not fecha_iso:
        return "Sin fecha específica"
    fecha = datetime.fromisoformat(fecha_iso)
    if fecha.hour == 0 and fecha.minute == 0 and fecha.second == 0:
        return fecha.strftime("%d %b %Y")
    else:
        return fecha.strftime("%d %b %Y, %H:%M")
    
    
def convertir_utc_a_local(fecha_utc: datetime, user_timezone_str: str) -> datetime:
    """Convierte una fecha UTC a la zona horaria local del usuario."""
    if not fecha_utc or not user_timezone_str:
        return fecha_utc
    try:
        user_timezone = pytz.timezone(user_timezone_str)
        return fecha_utc.astimezone(user_timezone)
    except pytz.UnknownTimeZoneError:
        return fecha_utc # Si la zona horaria es inválida, devuelve UTC


def parsear_tiempo_a_minutos(valor: str):
    """Convierte 2h, 1d, 30m o 0 a minutos."""
    if valor == "0":
        return 0
    try:
        if valor.endswith("h"):
            return int(valor[:-1]) * 60
        elif valor.endswith("d"):
            return int(valor[:-1]) * 1440
        elif valor.endswith("m"):
            return int(valor[:-1])
    except ValueError:
        return None
    return None


# CONSTRUCCIÓN DE LISTADOS

def _formatear_linea_individual(chat_id: int, recordatorio: tuple, user_tz_global: str) -> str:
    """Función privada ayudante. Formatea UNA SOLA línea."""
    _, user_id, _, texto, fecha_iso, estado, aviso_previo, timezone_recordatorio = recordatorio
       
    fecha_str = "Sin fecha"
    lineas = []
    fecha_local = None

    # Construimos la línea principal (la que tiene el ID y el texto)
    linea_principal = ""
    if fecha_iso:
        fecha_utc = datetime.fromisoformat(fecha_iso)
        tz_para_mostrar = timezone_recordatorio or user_tz_global
        fecha_local = convertir_utc_a_local(fecha_utc, tz_para_mostrar)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")

    # Decidimos el prefijo
    prefijo = "✅ " if estado == 1 else "⬜️ "
        
    linea_principal = f"{prefijo} `#{user_id}` - {texto} ({fecha_str})"
    lineas.append(linea_principal)

    # Solo mostramos el aviso si se cumplen TODAS estas condiciones:
    ''' 1. El recordatorio está pendiente (estado 0) | 2. Tiene una fecha. | 3. La fecha es FUTURA. | 4. Tiene  aviso previo programado (> 0).'''
    now_aware = datetime.now(pytz.timezone(user_tz_global))

    if estado == 0 and fecha_local and fecha_local > now_aware and aviso_previo and aviso_previo > 0:
        fecha_aviso_local = fecha_local - timedelta(minutes=aviso_previo)
        info_aviso_str = f"🔔 Aviso a las: {fecha_aviso_local.strftime('%d %b, %H:%M')}"
        lineas.append(f"  └─ {info_aviso_str}")
        
    return "\n".join(lineas)


def construir_mensaje_lista_completa(chat_id: int, recordatorios: list) -> str:
    """
    Función universal. Toma una lista de recordatorios y devuelve el mensaje
    completo, clasificado en Futuros y Pasados.
    """
    if not recordatorios:
        return get_text("lista_vacia") # Usamos la personalidad para el mensaje de lista vacía

    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    lineas = [_formatear_linea_individual(chat_id, r, user_tz) for r in recordatorios]
        
    return "\n".join(lineas)

ITEMS_PER_PAGE = 7 # Podemos definir esto como una constante global aquí

async def enviar_lista_interactiva(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE, 
    context_key: str, # <-- NUEVO: 'lista', 'borrar', 'editar', 'cambiar'
    titulos: dict,    # <-- NUEVO: Un diccionario con los títulos
    page: int = 1, 
    filtro: str = "futuro",
    mostrar_boton_cancelar: bool = False
):
    """
    Función universal y reutilizable para enviar una lista interactiva.
    Ahora es consciente del contexto para generar los botones correctos.
    """
    chat_id = update.effective_chat.id
    recordatorios_pagina, total_items = get_recordatorios(chat_id, filtro=filtro, page=page, items_per_page=ITEMS_PER_PAGE)

    # --- LÓGICA PARA LISTAS VACÍAS ---
    if total_items == 0:
        if filtro == "futuro":
            mensaje = get_text("lista_vacia")
            # Añadimos el context_key al callback_data
            keyboard = [[InlineKeyboardButton("🗂️ PASADOS", callback_data=f"list_pivot:pasado:{context_key}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        else: # filtro == "pasado"
            mensaje = "🗂️ No tienes recordatorios PASADOS."
            # Añadimos el context_key al callback_data
            keyboard = [[InlineKeyboardButton("📜 PENDIENTES", callback_data=f"list_pivot:futuro:{context_key}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(text=mensaje, reply_markup=reply_markup)
        else:
            await update.message.reply_text(text=mensaje, reply_markup=reply_markup)
        return

    total_pages = ceil(total_items / ITEMS_PER_PAGE)
    
    # Usamos los títulos del diccionario que nos pasan
    titulo = titulos[filtro] # Accedemos al título de 'futuro' o 'pasado'
    if total_pages > 1:
        titulo += f" (Pág. {page}/{total_pages})"
    titulo += "\n\n"
        
    cuerpo_lista = construir_mensaje_lista_completa(chat_id, recordatorios_pagina)
    mensaje_final = titulo + cuerpo_lista
    
    # --- BOTONES FIJOS ---

    # Creamos un "sufijo" para el callback_data que llevará toda la información de estado.
    # El '1' o '0' al final representa el estado de mostrar_boton_cancelar.
    cancel_flag = "1" if mostrar_boton_cancelar else "0"
    callback_sufijo = f":{filtro}:{context_key}:{cancel_flag}"

    keyboard_row = []
    paginacion_row = []
    
    # Columna Izquierda: Botón "Anterior" o un placeholder
    if page > 1:
        paginacion_row.append(InlineKeyboardButton("<<", callback_data=f"list_page:{page - 1}{callback_sufijo}"))
    else:
        paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))

    # Columna Central: Botón de cambio de vista
    if filtro == "futuro":
        paginacion_row.append(InlineKeyboardButton("🗂️ PASADOS", callback_data=f"list_pivot:pasado:{context_key}:{cancel_flag}"))
    else:
        paginacion_row.append(InlineKeyboardButton("📜 PENDIENTES", callback_data=f"list_pivot:futuro:{context_key}:{cancel_flag}"))
        
    # Columna Derecha: Botón "Siguiente" o un placeholder
    if page < total_pages:
        paginacion_row.append(InlineKeyboardButton(">>", callback_data=f"list_page:{page + 1}{callback_sufijo}"))
    else:
        paginacion_row.append(InlineKeyboardButton(" ", callback_data="placeholder"))
        
    keyboard_row.append(paginacion_row)

    # Fila 2: Acciones (Limpiar, Cancelar)
    acciones_row = []
    if filtro == "pasado" and context_key == "lista":
        acciones_row.append(InlineKeyboardButton("🧹 Limpiar", callback_data="limpiar_pasados_ask"))
    
    if mostrar_boton_cancelar:
        acciones_row.append(InlineKeyboardButton("❌ Cancelar", callback_data="list_cancel"))
        
    if acciones_row:
        keyboard_row.append(acciones_row)

    reply_markup = InlineKeyboardMarkup(keyboard_row)

    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text=mensaje_final, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await update.message.reply_text(text=mensaje_final, reply_markup=reply_markup, parse_mode="Markdown")



## GESTIONAR CIERRES DE CONVERSACIÓN

async def cancelar_conversacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Función genérica para el fallback de /cancelar.
    Limpia datos, teclado y envía un mensaje de confirmación.
    """
    # Limpiamos los datos de la conversación por si acaso
    if context.user_data:
        context.user_data.clear()
        
    await update.message.reply_text(
        text=get_text("cancelar"),
        reply_markup=ReplyKeyboardRemove()
    )
    
    return ConversationHandler.END

async def comando_inesperado(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Se activa si se recibe un comando inesperado.
    Le recuerda al usuario que debe usar /cancelar.
    NO termina la conversación.
    """
    await update.message.reply_text(get_text("error_interrupcion"))


async def cancelar_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Callback para el botón [X]. Llama a la función de cancelar estándar.
    """
    query = update.callback_query
    await query.answer()
    
    # Editamos el mensaje original para mostrar la confirmación de cancelación
    await query.edit_message_text(text=get_text("cancelar"))
    
    # Limpiamos los datos y terminamos la conversación
    if context.user_data:
        context.user_data.clear()
    return ConversationHandler.END