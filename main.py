from telegram.ext import ApplicationBuilder, CommandHandler
from config import TOKEN
from db import crear_tablas
from handlers import start_help, lista, recordar, cambiar_estado, borrar, configuracion

def main():
    crear_tablas()
    app = ApplicationBuilder().token(TOKEN).build()

    # Básicos
    app.add_handler(CommandHandler("start", start_help.start))
    app.add_handler(CommandHandler("ayuda", start_help.ayuda))

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

    print("🤖 La Recordadora está en marcha...")
    app.run_polling()

if __name__ == "__main__":
    main()
