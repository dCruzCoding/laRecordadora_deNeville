import re
from datetime import datetime
from dateparser.search import search_dates
from config import MESES_SIGLAS        # <— antes .config
from db import get_connection           # <— antes .db

def generar_id(fecha):
    mes = fecha.month
    sigla = MESES_SIGLAS[mes]
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id FROM recordatorios WHERE id LIKE ? ORDER BY id DESC LIMIT 1",
            (f"{sigla}%",)
        )
        ultimo = cursor.fetchone()
    if ultimo:
        ultimo_num = int(ultimo[0][len(sigla):])
        nuevo_num = ultimo_num + 1
    else:
        nuevo_num = 1
    return f"{sigla}{nuevo_num:02d}"

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

def parsear_recordatorio(texto_entrada):
    if "*" not in texto_entrada:
        return None, None, "❗ Formato inválido. Usa: fecha * texto"
    parte_fecha, parte_texto = texto_entrada.split("*", 1)
    parte_fecha = normalizar_hora(parte_fecha.strip())
    fechas = search_dates(parte_fecha, languages=['es'], settings={'PREFER_DATES_FROM': 'future'})
    if fechas:
        texto_fecha, fecha = fechas[0]
        texto = limpiar_texto_sin_fecha(parte_fecha, texto_fecha) + " " + parte_texto.strip()
        texto = texto.strip()
        return texto, fecha, None
    else:
        return None, None, "❗ No se pudo detectar fecha/hora en la parte izquierda"

def formatear_fecha_para_mensaje(fecha_iso):
    if not fecha_iso:
        return "Sin fecha específica"
    fecha = datetime.fromisoformat(fecha_iso)
    if fecha.hour == 0 and fecha.minute == 0 and fecha.second == 0:
        return fecha.strftime("%d %b %Y")
    else:
        return fecha.strftime("%d %b %Y, %H:%M")
