from telegram.error import Forbidden
import bot_state 
from db import get_recordatorios
from utils import construir_mensaje_lista_completa
from personalidad import get_text

async def enviar_resumen_para_usuario(chat_id: int):
    """
    Esta es la función que ejecuta el scheduler PARA UN USUARIO ESPECÍFICO.
    """
    print(f"🌞 Ejecutando resumen diario para el chat_id: {chat_id}")
    try:
        recordatorios_hoy, total = get_recordatorios(chat_id, filtro="hoy")
        if recordatorios_hoy:
            introduccion = get_text("resumen_diario_con_tareas")
            cuerpo_lista = construir_mensaje_lista_completa(chat_id, recordatorios_hoy)
            mensaje_final = introduccion + "\n\n" + cuerpo_lista

            await bot_state.telegram_app.bot.send_message(
                chat_id=chat_id,
                text=mensaje_final,
                parse_mode="Markdown"
            )
            print(f"  ✅ Resumen enviado al chat {chat_id}")

    except Forbidden:
        print(f"⚠️ No se pudo enviar el resumen al chat {chat_id}, el usuario ha bloqueado el bot.")
    except Exception as e:
        print(f"🚨 Error enviando resumen al chat {chat_id}: {e}")