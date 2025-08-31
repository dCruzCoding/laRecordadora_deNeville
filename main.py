import threading
from flask import Flask
from telegram.ext import ApplicationBuilder, CommandHandler
from config import TOKEN
from db import crear_tablas
from handlers import lista, recordar, cambiar_estado, borrar, ajustes, help_reset, start_onboarding, editar, posponer
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

# --- Parte 2: La Lógica de tu Bot ---
def run_telegram_bot():
    """Función que contiene la lógica para iniciar el bot."""
    # Ya no necesitamos crear un loop, porque esto se ejecutará en el hilo principal
    crear_tablas()
    app = ApplicationBuilder().token(TOKEN).post_init(avisos.iniciar_scheduler).build()

    # # --- GRUPO -1: EL HANDLER DE INTERRUPCIONES (MÁXIMA PRIORIDAD) ---
    # # Añadimos nuestro handler importado al grupo de máxima prioridad.
    # app.add_handler(interruption_handler, group=-1)

    # --- GRUPO 0: TUS CONVERSACIONES Y COMANDOS NORMALES ---
    # 1. Conversación de Bienvenida (Onboarding)
    app.add_handler(start_onboarding.start_handler)

    # 2. Comandos Básicos y de Ayuda
    app.add_handler(CommandHandler("info", start_onboarding.info))
    app.add_handler(CommandHandler("ayuda", help_reset.ayuda))

    # 3. Comandos de Gestión de Recordatorios
    app.add_handler(lista.lista_handler)
    app.add_handler(lista.lista_shared_handler) # paginacion + pivot
    app.add_handler(lista.limpiar_pasados_handler)

    app.add_handler(recordar.recordar_handler)
    app.add_handler(posponer.posponer_handler)

    app.add_handler(cambiar_estado.cambiar_estado_handler)
    app.add_handler(borrar.borrar_handler)
    app.add_handler(editar.editar_handler)

    # 4. Comandos de Ajustes
    app.add_handler(ajustes.ajustes_handler)

    # 5. Comandos de Administrador
    app.add_handler(help_reset.reset_handler)

    print("🤖 La Recordadora (bot de Telegram) está en marcha...")
    try:
        app.add_handler(start_onboarding.start_handler)
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