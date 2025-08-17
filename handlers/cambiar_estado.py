from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters
)
from datetime import datetime
from db import get_connection, get_config, actualizar_recordatorios_pasados
from utils import formatear_lista_para_mensaje
from avisos import cancelar_avisos, programar_avisos
from config import ESTADOS

ELEGIR_ID, CONFIRMAR = range(2)

async def cambiar_estado_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Punto de entrada para /cambiar.
    Maneja tanto el cambio directo con argumentos como el modo conversacional.
    """
    actualizar_recordatorios_pasados()

    if context.args:
        # CASO 1: El usuario proveyó IDs (ej: /cambiar AG01 AG02)
        ids = context.args
        context.user_data["ids_a_cambiar"] = ids
        
        modo_seguro = int(get_config("modo_seguro") or 0)
        if modo_seguro in (2, 3):
            # Modo seguro activado: pedimos confirmación y pasamos al estado CONFIRMAR
            await update.message.reply_text(
                f"⚠️ Vas a cambiar el estado de {len(ids)} recordatorio(s). Escribe 'SI' para confirmar."
            )
            return CONFIRMAR
        else:
            # Modo seguro desactivado: ejecutamos directamente y terminamos la conversación
            return await ejecutar_cambio(update, ids)
    else:
        # CASO 2: El usuario no proveyó IDs (ej: /cambiar)
        # Mostramos la lista y pasamos al estado ELEGIR_ID.
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, texto, fecha_hora, estado, aviso_previo FROM recordatorios ORDER BY CASE WHEN fecha_hora IS NULL THEN 1 ELSE 0 END, fecha_hora")
            recordatorios = cursor.fetchall()

        if not recordatorios:
            await update.message.reply_text("📭 No tienes recordatorios guardados.")
            return ConversationHandler.END

        pendientes = [r for r in recordatorios if r[3] == 0]
        hechos = [r for r in recordatorios if r[3] == 1]
        pasados = [r for r in recordatorios if r[3] == 2]

        secciones_mensaje = []
        if pendientes:
            secciones_mensaje.append(f"*{ESTADOS[0]}:*\n{formatear_lista_para_mensaje(pendientes)}")
        if pasados:
            secciones_mensaje.append(f"*{ESTADOS[2]}:*\n{formatear_lista_para_mensaje(pasados)}")
        if hechos:
            secciones_mensaje.append(f"*{ESTADOS[1]}:*\n{formatear_lista_para_mensaje(hechos)}")

        mensaje_final = "*CAMBIAR ESTADO 🔄*\n\n" + "\n\n".join(secciones_mensaje)
        mensaje_final += "\n\n✏️ Escribe el/los ID que quieras cambiar de estado o /cancelar si quieres salir:"
        
        await update.message.reply_text(mensaje_final, parse_mode="Markdown")
        return ELEGIR_ID


async def recibir_ids(update: Update, context: ContextTypes.DEFAULT_TYPE):
    ids = update.message.text.split()
    if not ids:
        await update.message.reply_text("⚠️ No escribiste ningún ID.")
        return ELEGIR_ID
    
    context.user_data["ids_a_cambiar"] = ids
    modo_seguro = int(get_config("modo_seguro") or 0)
    if modo_seguro in (2, 3):
        await update.message.reply_text(
            f"⚠️ Vas a cambiar el estado de {len(ids)} recordatorio(s). Escribe 'SI' para confirmar."
        )
        return CONFIRMAR
    return await ejecutar_cambio(update, ids)


async def confirmar_cambio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip().upper() == "SI":
        ids = context.user_data.get("ids_a_cambiar", [])
        return await ejecutar_cambio(update, ids)
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

async def ejecutar_cambio(update: Update, ids):
    with get_connection() as conn:
        cursor = conn.cursor()
        cambiados = []
        reprogramados = []

        for rid in ids:
            # Obtenemos la info necesaria de la base de datos
            cursor.execute("SELECT estado, texto, fecha_hora, aviso_previo, chat_id FROM recordatorios WHERE id = ?", (rid,))
            row = cursor.fetchone()

            if row is not None:
                estado_actual, texto, fecha_iso, aviso_previo, chat_id = row
                
                # --- NUEVA LÓGICA DE TRANSICIÓN DE ESTADOS ---
                nuevo_estado = estado_actual # Por defecto, no cambia
                if estado_actual == 0: # Pendiente -> Hecho
                    nuevo_estado = 1
                elif estado_actual == 1: # Hecho -> Pendiente
                    nuevo_estado = 0
                elif estado_actual == 2: # Pasado -> Hecho
                    nuevo_estado = 1

                # Si el estado ha cambiado, lo actualizamos
                if nuevo_estado != estado_actual:
                    cursor.execute("UPDATE recordatorios SET estado = ? WHERE id = ?", (nuevo_estado, rid))
                    cambiados.append(rid)

                    # Si el nuevo estado es NO PENDIENTE (Hecho o Pasado), cancelamos avisos
                    if nuevo_estado in (1, 2):
                        cancelar_avisos(rid)
                        print(f"✅ Avisos para '{rid}' cancelados (ya no está pendiente).")
                    
                    # Si el nuevo estado es PENDIENTE, reprogramamos
                    elif nuevo_estado == 0:
                        if fecha_iso and chat_id and aviso_previo is not None:
                            fecha_dt = datetime.fromisoformat(fecha_iso)
                            await programar_avisos(chat_id, rid, texto, fecha_dt, aviso_previo)
                            reprogramados.append(rid)
                            print(f"🔄 Avisos para '{rid}' reprogramados.")

        conn.commit()

    # Construimos un mensaje de confirmación más informativo
    mensaje_confirmacion = ""
    if cambiados:
        mensaje_confirmacion += f"🔄 Estado cambiado para: {', '.join(cambiados)}"
    if reprogramados:
        mensaje_confirmacion += f"\n\n🗓️ ¡Avisos reactivados para: {', '.join(reprogramados)}!"

    if mensaje_confirmacion:
        await update.message.reply_text(mensaje_confirmacion)
    else:
        await update.message.reply_text("⚠️ No se encontró ningún ID válido.")
        
    return ConversationHandler.END

async def cancelar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Operación cancelada.")
    return ConversationHandler.END

cambiar_estado_handler = ConversationHandler(
    entry_points=[CommandHandler("cambiar", cambiar_estado_cmd)],
    states={
        ELEGIR_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_ids)],
        CONFIRMAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirmar_cambio)]
    },
    fallbacks=[CommandHandler("cancelar", cancelar)],
)
