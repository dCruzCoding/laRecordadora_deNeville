import re
import pytz
from datetime import datetime, timedelta
from dateparser.search import search_dates
from personalidad import get_text
from db import get_config
from telegram import Update, ReplyKeyboardRemove
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

def _formatear_linea_individual(chat_id: int, recordatorio: tuple, user_tz_global: str) -> str:
    """Función privada ayudante. Formatea UNA SOLA línea."""
    _, user_id, _, texto, fecha_iso, estado, _, timezone_recordatorio = recordatorio
       
    fecha_str = "Sin fecha"

    if fecha_iso:
        fecha_utc = datetime.fromisoformat(fecha_iso)
        tz_para_mostrar = timezone_recordatorio or user_tz_global
        fecha_local = convertir_utc_a_local(fecha_utc, tz_para_mostrar)
        fecha_str = fecha_local.strftime("%d %b, %H:%M")

    prefijo = "✅ " if estado == 1 else "⬜️ "
    return f"{prefijo}`#{user_id}` - {texto} ({fecha_str})"


def construir_mensaje_lista_completa(chat_id: int, recordatorios: list, titulo_general: str = None) -> str:
    """
    Función universal. Toma una lista de recordatorios y devuelve el mensaje
    completo, clasificado en Futuros y Pasados.
    """
    if not recordatorios:
        return get_text("lista_vacia") # Usamos la personalidad para el mensaje de lista vacía

    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    now_aware = datetime.now(pytz.timezone(user_tz))

    futuros_y_sin_fecha = []
    pasados = []

    for r in recordatorios:
        fecha_iso, timezone_r = r[4], r[7]
        if fecha_iso:
            fecha_utc = datetime.fromisoformat(fecha_iso)
            tz_para_comparar = timezone_r or user_tz
            fecha_local = convertir_utc_a_local(fecha_utc, tz_para_comparar)
            if fecha_local < now_aware:
                pasados.append(r)
            else:
                futuros_y_sin_fecha.append(r)
        else:
            futuros_y_sin_fecha.append(r)

    mensaje_partes = []
    if titulo_general:
        mensaje_partes.append(f"*{titulo_general}*")

    if futuros_y_sin_fecha:
        lineas_futuras = [_formatear_linea_individual(chat_id, r, user_tz) for r in futuros_y_sin_fecha]
        mensaje_partes.append("\n".join(lineas_futuras))

    if pasados:
        mensaje_partes.append("\n--- *Pasados* ---\n")
        lineas_pasadas = [_formatear_linea_individual(chat_id, r, user_tz) for r in pasados]
        mensaje_partes.append("\n".join(lineas_pasadas))
        
    return "\n".join(mensaje_partes)

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