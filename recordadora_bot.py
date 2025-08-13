import sqlite3
import re
from dateparser.search import search_dates
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    ConversationHandler, MessageHandler, filters
)

# Configurar formato hora en español
import locale

try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_TIME, "es_ES")

# === CONFIG ===
TOKEN = "TU_TOKEN_AQUI_PARA_PRUEBAS_LOCALES"  # Pon tu token aquí

# === DB SETUP ===
conn = sqlite3.connect("recordadora.db", check_same_thread=False)
cursor = conn.cursor()

# Nueva tabla con estado INTEGER y id TEXT personalizado
cursor.execute("""
CREATE TABLE IF NOT EXISTS recordatorios (
    id TEXT PRIMARY KEY,
    texto TEXT NOT NULL,
    fecha_hora TEXT,
    estado INTEGER NOT NULL DEFAULT 0 CHECK(estado IN (0, 1))
)
""")
conn.commit()

# === Configuración meses ===
MESES_SIGLAS = {
    1: "E",  2: "F",  3: "MZ", 4: "AB", 5: "MY", 6: "JN",
    7: "JL", 8: "AG", 9: "S", 10: "O", 11: "N", 12: "D"
}

def generar_id(fecha):
    mes = fecha.month
    sigla = MESES_SIGLAS[mes]
    cursor.execute("SELECT id FROM recordatorios WHERE id LIKE ? ORDER BY id DESC LIMIT 1", (f"{sigla}%",))
    ultimo = cursor.fetchone()
    if ultimo:
        ultimo_num = int(ultimo[0][len(sigla):])
        nuevo_num = ultimo_num + 1
    else:
        nuevo_num = 1
    return f"{sigla}{nuevo_num:02d}"

# === Funciones de parsing ===
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

# === HANDLERS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👵 ¡Ay criatura! Soy *La Recordadora*, tu abuela digital.\n"
        "Dime qué no quieres olvidar y yo te lo recordaré.\n\n"
        "Usa /ayuda para ver lo que puedo hacer.",
        parse_mode="Markdown"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📜 *Comandos disponibles:*\n"
        "/start - Presentación\n"
        "/ayuda - Lista comandos\n"
        "/recordar - Añade un recordatorio (formato: fecha \\* texto)\n"
        "/lista - Ver recordatorios pendientes\n"
        "/hecho id - Marcar recordatorio como hecho\n"
        "/borrar id - Eliminar recordatorio",
        parse_mode="Markdown" 
    )

async def lista(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Pendientes
    cursor.execute("SELECT id, texto, fecha_hora FROM recordatorios WHERE estado=0 ORDER BY fecha_hora")
    pendientes = cursor.fetchall()
    # Hechos
    cursor.execute("SELECT id, texto, fecha_hora FROM recordatorios WHERE estado=1 ORDER BY fecha_hora")
    hechos = cursor.fetchall()

    mensaje = "📋 *Pendientes:*\n" if pendientes else "📋 *Pendientes:* (ninguno)\n"
    for id_, texto, fecha_hora in pendientes:
        fecha_str = formatear_fecha_para_mensaje(fecha_hora)
        mensaje += f"{id_} — {texto} ({fecha_str})\n"

    mensaje += "\n✅ *Hechos:*\n" if hechos else "\n✅ *Hechos:* (ninguno)\n"
    for id_, texto, fecha_hora in hechos:
        fecha_str = formatear_fecha_para_mensaje(fecha_hora)
        mensaje += f"{id_} — {texto} ({fecha_str})\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")


##################
# Conversación para /recordar
ESPERANDO_RECORDATORIO = 0   # Estados del conversation handler

# --- Función para empezar /recordar ---
async def recordar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_entrada = " ".join(context.args).strip()
    if texto_entrada:
        # Si hay argumentos, procesamos directamente
        return await procesar_recordatorio(update, context, texto_entrada)
    else:
        # Modo conversacional
        await update.message.reply_text(
            "📝 Dime qué quieres recordar. Recuerda usar el formato: `fecha * texto`",
            parse_mode="Markdown"
        )
        return ESPERANDO_RECORDATORIO

# --- Función que recibe el mensaje del usuario ---
async def recordar_recibir(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto_entrada = update.message.text.strip()
    return await procesar_recordatorio(update, context, texto_entrada)

# --- Función que procesa un recordatorio (puede usarse desde args o conversación) ---
async def procesar_recordatorio(update: Update, context: ContextTypes.DEFAULT_TYPE, texto_entrada: str):
    texto, fecha_obj, error = parsear_recordatorio(texto_entrada)
    if error:
        await update.message.reply_text(error)
        return ESPERANDO_RECORDATORIO  # Mantiene la conversación activa

    texto = texto.capitalize()
    fecha_iso = fecha_obj.isoformat() if fecha_obj else None
    nuevo_id = generar_id(fecha_obj or datetime.now())

    cursor.execute(
        "INSERT INTO recordatorios (id, texto, fecha_hora) VALUES (?, ?, ?)",
        (nuevo_id, texto, fecha_iso)
    )
    conn.commit()

    fecha_mensaje = formatear_fecha_para_mensaje(fecha_iso)
    await update.message.reply_text(
        f"✅ Recordatorio guardado:\n» {texto}\n🆔 ID: {nuevo_id}\n⏰ Para el {fecha_mensaje}"
    )
    return ConversationHandler.END

async def recordar_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


##################
# Conversación para /hecho
PREGUNTAR_ID_HECHO, CONFIRMAR_CAMBIO_ESTADO = range(2)

async def hecho_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args

    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()

    cursor.execute("SELECT id, fecha_hora, texto FROM recordatorios WHERE estado=0 ORDER BY fecha_hora")
    pendientes = cursor.fetchall()

    cursor.execute("SELECT id, fecha_hora, texto FROM recordatorios WHERE estado=1 ORDER BY fecha_hora")
    hechos = cursor.fetchall()

    conexion.close()

    if args:
        # Si el usuario escribió /hecho <ID>
        id_seleccionado = args[0].strip().upper()
        return await procesar_id_hecho(update, context, id_seleccionado)

    # Modo conversacional
    mensaje = "🆔 *Indica el ID que quieres marcar o desmarcar como hecho*\n\n"
    if pendientes:
        mensaje += "📌 *Pendientes:*\n"
        for id_, fecha, texto in pendientes:
            fecha_str = formatear_fecha_para_mensaje(fecha)
            mensaje += f"  {id_} - {fecha_str} → {texto}\n"
    else:
        mensaje += "📌 *Pendientes:*\n  (No hay)\n"

    mensaje += "\n"

    if hechos:
        mensaje += "✅ *Hechos:*\n"
        for id_, fecha, texto in hechos:
            fecha_str = formatear_fecha_para_mensaje(fecha)
            mensaje += f"  {id_} - {fecha_str} → {texto}\n"
    else:
        mensaje += "✅ *Hechos:*\n  (No hay)\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")
    return PREGUNTAR_ID_HECHO

async def procesar_id_hecho(update: Update, context: ContextTypes.DEFAULT_TYPE, id_seleccionado: str):
    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT estado FROM recordatorios WHERE id=?", (id_seleccionado,))
    fila = cursor.fetchone()
    conexion.close()

    if not fila:
        await update.message.reply_text(
            f"❗ No encontré recordatorios con id \"{id_seleccionado}\".\nPor favor escriba un ID válido o escriba /cancelar para terminar la operación."
        )
        return PREGUNTAR_ID_HECHO  # Mantener conversación

    estado_actual = fila[0]
    context.user_data["hecho_id"] = id_seleccionado
    context.user_data["estado_actual"] = estado_actual

    if estado_actual == 0:
        await update.message.reply_text(
            f"⚠️ ¿Marcar el recordatorio {id_seleccionado} como *hecho*? (sí/no)",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            f"⚠️ El recordatorio {id_seleccionado} ya está hecho.\n¿Quieres pasarlo a *pendiente*? (sí/no)",
            parse_mode="Markdown"
        )

    return CONFIRMAR_CAMBIO_ESTADO


async def hecho_recibir_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text
    # parsear varios IDs separados por coma o espacio
    ids = [i.strip().upper() for i in texto.replace(',', ' ').split()]
    context.user_data["ids_por_procesar"] = ids
    context.user_data["indice_id_actual"] = 0  # índice del ID actual
    return await procesar_siguiente_id(update, context)

async def procesar_siguiente_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = context.user_data.get("ids_por_procesar", [])
    indice = context.user_data.get("indice_id_actual", 0)

    if indice >= len(ids):
        await update.message.reply_text("✅ Todos los IDs han sido procesados.")
        return ConversationHandler.END

    id_actual = ids[indice]

    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()
    cursor.execute("SELECT estado FROM recordatorios WHERE id=?", (id_actual,))
    fila = cursor.fetchone()
    conexion.close()

    if not fila:
        await update.message.reply_text(
            f"❗ No encontré recordatorios con ID \"{id_actual}\".\nEscribe un ID válido o /cancelar para terminar."
        )
        context.user_data["indice_id_actual"] += 1
        return await procesar_siguiente_id(update, context)

    estado_actual = fila[0]
    context.user_data["estado_actual"] = estado_actual
    context.user_data["id_actual"] = id_actual

    if estado_actual == 0:
        await update.message.reply_text(f"⚠️ ¿Marcar el recordatorio {id_actual} como *hecho*? (sí/no)", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"⚠️ El recordatorio {id_actual} ya está hecho.\n¿Pasarlo a pendiente? (sí/no)", parse_mode="Markdown")

    return CONFIRMAR_CAMBIO_ESTADO

async def hecho_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto not in ("sí", "si", "no"):
        await update.message.reply_text("Por favor responde con 'sí' o 'no'.")
        return CONFIRMAR_CAMBIO_ESTADO

    id_actual = context.user_data["id_actual"]
    estado_actual = context.user_data["estado_actual"]

    if texto in ("sí", "si"):
        nuevo_estado = 1 if estado_actual == 0 else 0
        conexion = sqlite3.connect("recordadora.db")
        cursor = conexion.cursor()
        cursor.execute("UPDATE recordatorios SET estado=? WHERE id=?", (nuevo_estado, id_actual))
        conexion.commit()
        conexion.close()

        if nuevo_estado == 1:
            await update.message.reply_text(f"✅ Recordatorio {id_actual} marcado como hecho.")
        else:
            await update.message.reply_text(f"↩️ Recordatorio {id_actual} pasado a pendiente.")
    else:
        await update.message.reply_text(f"❌ Se dejó sin cambios el recordatorio {id_actual}.")

    context.user_data["indice_id_actual"] += 1
    return await procesar_siguiente_id(update, context)


async def hecho_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


##################
# Conversación para borrar recordatorios
PREGUNTAR_QUÉ_BORRAR, CONFIRMAR_BORRADO = range(2)

async def borrar_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()

    cursor.execute("SELECT id, fecha_hora, texto FROM recordatorios WHERE estado = 0 ORDER BY fecha_hora")
    pendientes = cursor.fetchall()

    cursor.execute("SELECT id, fecha_hora, texto FROM recordatorios WHERE estado = 1 ORDER BY fecha_hora")
    hechos = cursor.fetchall()

    conexion.close()

    if args:
        # Si usuario escribió /borrar <algo>
        peticion = args[0].lower()
        if peticion == "hechos":
            context.user_data["borrar_objeto"] = "hechos"
            await update.message.reply_text(
                "⚠️ Estás a punto de borrar *todos* los recordatorios hechos.\n¿Estás seguro? Responde sí o no.",
                parse_mode="Markdown"
            )
            return CONFIRMAR_BORRADO
        else:
            # Se asume que es un ID
            context.user_data["borrar_objeto"] = peticion
            await update.message.reply_text(
                f"⚠️ Estás a punto de borrar el recordatorio con ID {peticion}.\n¿Estás seguro? Responde sí o no.",
                parse_mode="Markdown"
            )
            return CONFIRMAR_BORRADO

    # Si no hay args, mostramos listas para que elija
    mensaje = "🗑 *Selecciona un ID para borrar o escribe `hechos` para borrar todos los hechos*\n\n"

    if pendientes:
        mensaje += "📌 *Pendientes:*\n"
        for id_, fecha, texto in pendientes:
            fecha_str = formatear_fecha_para_mensaje(fecha)
            mensaje += f"  {id_} - {fecha_str} → {texto}\n"
    else:
        mensaje += "📌 *Pendientes:*\n  (No hay)\n"

    mensaje += "\n"

    if hechos:
        mensaje += "✅ *Hechos:*\n"
        for id_, fecha, texto in hechos:
            fecha_str = formatear_fecha_para_mensaje(fecha)
            mensaje += f"  {id_} - {fecha_str} → {texto}\n"
    else:
        mensaje += "✅ *Hechos:*\n  (No hay)\n"

    mensaje += "\nEscribe el ID o `hechos` para borrar.\n"

    await update.message.reply_text(mensaje, parse_mode="Markdown")

    return PREGUNTAR_QUÉ_BORRAR

async def borrar_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.lower().strip()
    if texto not in ("sí", "si", "no"):
        await update.message.reply_text("Por favor responde con 'sí' o 'no'.")
        return CONFIRMAR_BORRADO

    if texto in ("no",):
        await update.message.reply_text("❌ Operación cancelada.")
        return ConversationHandler.END

    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()

    if context.user_data.get("borrar_objeto") == "hechos":
        cursor.execute("DELETE FROM recordatorios WHERE estado=1")
        await update.message.reply_text("✅ Todos los recordatorios hechos han sido borrados.")
    else:
        ids = context.user_data.get("borrar_ids", [])
        cursor.executemany("DELETE FROM recordatorios WHERE id=?", [(id_,) for id_ in ids])
        await update.message.reply_text(f"✅ Recordatorios borrados: {', '.join(ids)}")

    conexion.commit()
    conexion.close()
    return ConversationHandler.END


async def borrar_cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END


async def borrar_recibir_objeto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    texto = update.message.text.strip().upper()

    # parsear varios IDs separados por coma o espacio
    ids = [i.strip() for i in texto.replace(',', ' ').split()]
    context.user_data["ids_a_borrar"] = ids
    context.user_data["ids_invalidos"] = []
    context.user_data["ids_validos"] = []

    conexion = sqlite3.connect("recordadora.db")
    cursor = conexion.cursor()

    for id_ in ids:
        if id_ == "HECHOS":
            context.user_data["ids_validos"].append("HECHOS")
            continue
        cursor.execute("SELECT id FROM recordatorios WHERE id=?", (id_,))
        if cursor.fetchone():
            context.user_data["ids_validos"].append(id_)
        else:
            context.user_data["ids_invalidos"].append(id_)

    conexion.close()

    mensaje = ""
    if context.user_data["ids_invalidos"]:
        mensaje += f"❗ IDs no encontrados: {', '.join(context.user_data['ids_invalidos'])}\n"

    if context.user_data["ids_validos"]:
        proximo_id = context.user_data["ids_validos"].pop(0)
        context.user_data["id_actual"] = proximo_id
        if proximo_id == "HECHOS":
            mensaje += "⚠️ Estás a punto de borrar *todos* los recordatorios hechos.\n¿Estás seguro? (sí/no)"
        else:
            mensaje += f"⚠️ Estás a punto de borrar el recordatorio {proximo_id}.\n¿Estás seguro? (sí/no)"
    else:
        await update.message.reply_text("No hay IDs válidos para borrar. Operación cancelada.")
        return ConversationHandler.END

    await update.message.reply_text(mensaje, parse_mode="Markdown")
    return CONFIRMAR_BORRADO


##########################################################
#                   === MAIN ===
##########################################################

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    
    recordar_handler = ConversationHandler(
        entry_points=[CommandHandler("recordar", recordar_start)],
        states={
            ESPERANDO_RECORDATORIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, recordar_recibir)],
        },
        fallbacks=[CommandHandler("cancelar", recordar_cancelar)],
        per_message=False
    )

    hecho_handler = ConversationHandler(
        entry_points=[CommandHandler("hecho", hecho_start)],
        states={
            PREGUNTAR_ID_HECHO: [MessageHandler(filters.TEXT & ~filters.COMMAND, hecho_recibir_id)],
            CONFIRMAR_CAMBIO_ESTADO: [MessageHandler(filters.Regex(r"(?i)^(sí|si|no)$"), hecho_confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", hecho_cancelar)],
        per_message=False
    )

    borrar_handler = ConversationHandler(
        entry_points=[CommandHandler("borrar", borrar_start)],
        states={
            PREGUNTAR_QUÉ_BORRAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, borrar_recibir_objeto)],
            CONFIRMAR_BORRADO: [MessageHandler(filters.Regex(r"(?i)^(sí|si|no)$"), borrar_confirmar)],
        },
        fallbacks=[CommandHandler("cancelar", borrar_cancelar)],
        per_message=False
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))
    app.add_handler(CommandHandler("lista", lista))
    app.add_handler(recordar_handler)
    app.add_handler(hecho_handler)
    app.add_handler(borrar_handler)
    
    print("🤖 La Recordadora está en marcha...")
    app.run_polling()

if __name__ == "__main__":
    main()
