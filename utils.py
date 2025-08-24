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
        texto_capitalizado = texto.strip().capitalize()
        
        return texto_capitalizado, fecha_utc, None
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


def formatear_lista_para_mensaje(chat_id: int, recordatorios: list, mostrar_info_aviso: bool = False) -> str:
    """
    Toma una lista de recordatorios y la convierte en un string formateado para un mensaje.
    AHORA RECIBE 'user_id' en lugar de 'rid'.
    """
    # Si la lista está vacía, no hay nada que hacer.
    if not recordatorios:
        return ""

    user_tz = get_config(chat_id, "user_timezone") or 'UTC'
    lineas = []
    
    for _, user_id, _, texto, fecha_iso, _, aviso_previo in recordatorios:
        # Primero, manejamos el caso de que no haya fecha
        if not fecha_iso:
            lineas.append(f"`#{user_id}` - {texto} (Sin fecha)")
            continue

        # --- CONVERSIÓN A LOCAL (Punto único de verdad para la fecha) ---
        fecha_utc = datetime.fromisoformat(fecha_iso)
        fecha_local = convertir_utc_a_local(fecha_utc, user_tz)
        fecha_str = fecha_local.strftime("%d %b %Y, %H:%M")
        
        # Línea principal
        entrada = f"`#{user_id}` - {texto} ({fecha_str})"
        
        if mostrar_info_aviso:
            if aviso_previo and aviso_previo > 0:
                # --- ¡CORRECCIÓN AQUÍ! ---
                # Calculamos la hora del aviso a partir de la fecha LOCAL
                fecha_aviso_local = fecha_local - timedelta(minutes=aviso_previo)
                info_aviso_str = f"🔔 Aviso a las: {fecha_aviso_local.strftime('%d %b, %H:%M')}"
            else:
                info_aviso_str = "🔕 Sin aviso programado"
            
            entrada += f"\n  └─ {info_aviso_str}"
            
        lineas.append(entrada)
        
    return "\n".join(lineas)


async def manejar_cancelacion(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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