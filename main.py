import threading
import asyncio
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler
from config import TOKEN
from db import crear_tablas
from handlers import start_help_reset, lista, recordar, cambiar_estado, borrar, configuracion
import avisos

# --- Parte 1: El Servidor Web para Render (sin cambios) ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "¡La Recordadora está viva y escuchando!"

def run_flask():
    import os
    port = int(os.environ.get('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- Parte 2: La Lógica de tu Bot (sin el truco del loop) ---
def run_telegram_bot():
    """Función que contiene la lógica para iniciar el bot."""
    # Ya no necesitamos crear un loop, porque esto se ejecutará en el hilo principal
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

# --- Parte 3: El Punto de Entrada Principal (CON EL INTERCAMBIO) ---
if __name__ == "__main__":
    print("🚀 Iniciando servicios...")
    
    # Creamos un hilo para el servidor Flask
    flask_thread = threading.Thread(target=run_flask)
    # Lo marcamos como 'daemon'. Esto significa que si el hilo principal (el bot) se detiene,
    # este hilo secundario se detendrá automáticamente con él.
    flask_thread.daemon = True
    
    # Iniciamos el servidor Flask en su propio hilo
    flask_thread.start()
    
    # Y ejecutamos el bot de Telegram en el hilo principal, donde debe estar.
    run_telegram_bot()