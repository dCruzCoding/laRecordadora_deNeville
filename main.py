# main.py
"""
Punto de Entrada Principal de La Recordadora de Neville.

Este script inicia y coordina los dos componentes principales del bot:
1.  Un micro-servidor web (Flask) en un hilo secundario para cumplir con los
    requisitos de "health check" de plataformas como Render.
2.  El bot de Telegram (python-telegram-bot) en el hilo principal, manejando
    toda la interacción con el usuario mediante polling.
"""

# --- Importaciones de la Librería Estándar ---
import threading
import os
import time
import asyncio

# --- Importaciones de Librerías de Terceros ---
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler
import telegram.error

# --- Importaciones de Módulos Locales ---
from config import TOKEN
from db import crear_tablas
import avisos
# Se importan los módulos de handlers que contienen los objetos handler ya construidos.
from handlers import (
    lista, recordar, cambiar_estado, borrar, ajustes,
    help_reset, start_onboarding, editar, posponer
)

# =============================================================================
# SECCIÓN 1: SERVIDOR WEB PARA COMPATIBILIDAD CON RENDER
# =============================================================================

flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    """
    Ruta raíz que responde a los chequeos de salud de Render.
    Una respuesta exitosa (código 200) mantiene el servicio activo.
    """
    return "¡La Recordadora está viva y escuchando!"

def run_flask():
    """Función que ejecuta el servidor Flask en un hilo dedicado."""
    # Render proporciona el puerto a través de una variable de entorno.
    port = int(os.environ.get('PORT', 10000))
    print(f"🌍 Servidor web Flask iniciado en el puerto {port}...")
    flask_app.run(host='0.0.0.0', port=port)


# =============================================================================
# SECCIÓN 2: LÓGICA PRINCIPAL DEL BOT DE TELEGRAM
# =============================================================================

def run_telegram_bot():
    """Inicializa, configura y ejecuta el bot de Telegram de forma indefinida."""
    # 1. Se asegura de que las tablas de la base de datos existan.
    crear_tablas()

    # 2. Construye la aplicación del bot, vinculando el inicio del scheduler.
    app = ApplicationBuilder().token(TOKEN).post_init(avisos.iniciar_scheduler).build()

    # 3. Registro de Handlers (el "cerebro" del bot).
    # El orden de registro es importante para la legibilidad del código.
    
    # --- Flujo de Bienvenida e Información ---
    app.add_handler(start_onboarding.start_handler)     # /start y el proceso de onboarding.
    app.add_handler(CommandHandler("info", start_onboarding.info))
    app.add_handler(CommandHandler("ayuda", help_reset.ayuda))

    # --- Comandos de Gestión de Recordatorios ---
    app.add_handler(recordar.recordar_handler)         # /recordar
    app.add_handler(cambiar_estado.cambiar_estado_handler) # /cambiar
    app.add_handler(borrar.borrar_handler)             # /borrar
    app.add_handler(editar.editar_handler)             # /editar
    
    # --- Handlers para Listas Interactivas (Comandos y Callbacks) ---
    app.add_handler(lista.lista_command_handler)       # /lista
    app.add_handler(lista.lista_shared_handler)        # Botones de paginación (<<, >>) y pivote (Pasados/Pendientes)
    app.add_handler(lista.limpiar_pasados_handler)     # Botón y flujo para limpiar pasados
    app.add_handler(lista.placeholder_handler)         # Botones invisibles de alineación
    app.add_handler(lista.lista_cancel_handler)        # Botón universal [X] para cancelar en listas

    # --- Handler para Acciones en Notificaciones (Callbacks) ---
    app.add_handler(posponer.posponer_handler)         # Botones (OK, +10min, Hecho) en los avisos

    # --- Handlers de Configuración y Administración ---
    app.add_handler(ajustes.ajustes_handler)           # /ajustes
    app.add_handler(help_reset.reset_handler)          # /reset (comando de admin)

    # 4. Inicio del bot.
    print("🤖 La Recordadora (bot de Telegram) está en marcha...")
    while True:
        try:
            # En lugar de llamar directamente a run_polling, lo ejecutamos dentro de un
            # bucle de eventos gestionado por asyncio.run().
            asyncio.run(app.run_polling(poll_interval=1, timeout=30))
        except telegram.error.NetworkError as e:
            # Capturamos específicamente los errores de red.
            print(f"🚨 ERROR DE RED: {e}")
            print("💤 Esperando 30 segundos antes de intentar reconectar...")
            time.sleep(30) # Damos un respiro antes de reconectar.
            print("🚀 Reiniciando el bucle de polling...")
        except Exception as e:
            # Capturamos cualquier otro error inesperado para que no mate el bot.
            print(f"🚨 ERROR INESPERADO: {e}")
            print("💤 Esperando 60 segundos antes de reiniciar...")
            time.sleep(60)
            print("🚀 Reiniciando...")


# =============================================================================
# SECCIÓN 3: PUNTO DE ENTRADA PRINCIPAL
# =============================================================================

if __name__ == "__main__":
    print("🚀 Iniciando servicios...")
    
    # Se crea un hilo para el servidor Flask.
    flask_thread = threading.Thread(target=run_flask)
    # Se marca como 'daemon' para que se detenga automáticamente si el hilo principal (el bot) lo hace.
    flask_thread.daemon = True
    
    # Se inicia el servidor Flask en su propio hilo.
    flask_thread.start()
    
    # Se ejecuta el bot de Telegram en el hilo principal.
    run_telegram_bot()