import threading
import asyncio
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler
from config import TOKEN
from db import crear_tablas
from handlers import start_help_reset, lista, recordar, cambiar_estado, borrar, configuracion
import avisos

# --- Parte 1: El Servidor Web para Render ---
# Creamos una instancia de una aplicación web Flask
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    """Esta es la página que Render visitará para ver si estamos vivos."""
    return "¡La Recordadora está viva y escuchando!"

def run_flask():
    """Función para ejecutar el servidor Flask."""
    # Render necesita que el servidor escuche en el host 0.0.0.0 y en un puerto que él asigna.
    # El puerto se nos da a través de una variable de entorno llamada PORT.
    # Usamos 10000 como valor por defecto si estamos en local.
    import os
    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)

    # --- Parte 2: La Lógica de tu Bot (ligeramente modificada) ---
def run_telegram_bot():
    """Función que contiene la lógica para iniciar el bot."""

     # Creamos un nuevo bucle de eventos para este hilo
    loop = asyncio.new_event_loop()
    # Establecemos el nuevo bucle como el actual para este hilo
    asyncio.set_event_loop(loop)

    # ------------------------------------
    
    crear_tablas()
    app = ApplicationBuilder().token(TOKEN).post_init(avisos.iniciar_scheduler).build()

    # Añadimos todos los handlers
    app.add_handler(CommandHandler("start", start_help_reset.start))
    app.add_handler(CommandHandler("ayuda", start_help_reset.ayuda))
    app.add_handler(start_help_reset.reset_handler)
    app.add_handler(CommandHandler("lista", lista.lista))
    app.add_handler(recordar.recordar_handler)
    app.add_handler(cambiar_estado.cambiar_estado_handler)
    app.add_handler(borrar.borrar_handler)
    app.add_handler(configuracion.configuracion_handler)

    print("🤖 La Recordadora (bot de Telegram) está en marcha...")
    try:
        app.run_polling()
    finally:
        avisos.detener_scheduler()

# --- Parte 3: El Punto de Entrada Principal ---
if __name__ == "__main__":
    print("🚀 Iniciando servicios...")
    
    # Creamos un hilo para el bot de Telegram
    bot_thread = threading.Thread(target=run_telegram_bot)
    
    # El servidor Flask se ejecuta en el hilo principal
    
    bot_thread.start() # Iniciamos el bot en su propio hilo
    run_flask()      # Iniciamos Flask en el hilo principal