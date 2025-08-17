from telegram.ext import ApplicationBuilder, CommandHandler
from config import TOKEN
from db import crear_tablas
from handlers import start_help_reset, lista, recordar, cambiar_estado, borrar, configuracion
import avisos

def main():
    crear_tablas()

    # 1. Guarda el objeto 'app' en una variable
    app = ApplicationBuilder().token(TOKEN).post_init(avisos.iniciar_scheduler).build()

     # Básicos
    app.add_handler(CommandHandler("start", start_help_reset.start))
    app.add_handler(CommandHandler("ayuda", start_help_reset.ayuda))

    # Lista
    app.add_handler(CommandHandler("lista", lista.lista))

    # Recordar
    app.add_handler(recordar.recordar_handler)

    # Cambiar estado
    app.add_handler(cambiar_estado.cambiar_estado_handler)

    # Borrar
    app.add_handler(borrar.borrar_handler)

    # Configuración
    app.add_handler(configuracion.configuracion_handler)

    # Resetear
    app.add_handler(start_help_reset.reset_handler)

    print("🤖 La Recordadora está en marcha...")
    
    try:
        app.run_polling()
    finally:
        # La llamada para detenerlo sí se queda aquí
        avisos.detener_scheduler()

if __name__ == "__main__":
    main()