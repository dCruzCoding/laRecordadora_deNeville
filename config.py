import locale
import os

# === CONFIGURACIÓN GENERAL ===

# Intentamos establecer el locale a español, pero si falla, no detenemos el programa.
# Simplemente mostraremos un aviso en la consola de Render y continuaremos.
try:
    # Primero intentamos la versión más completa
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    try:
        # Si falla, intentamos una versión más simple
        locale.setlocale(locale.LC_TIME, "es_ES")
    except locale.Error:
        # Si todo falla, informamos en el log y el programa seguirá funcionando
        # con el locale por defecto del sistema (probablemente inglés).
        print("⚠️ Advertencia: El locale 'es_ES' no está disponible en el sistema. Las fechas pueden mostrarse en inglés.")

# Leemos el token desde una variable de entorno para mayor seguridad.
# Si la variable no existe (porque estamos en local), usamos un valor por defecto.
TOKEN = os.getenv("TELEGRAM_TOKEN", "TU_TOKEN_AQUI_PARA_PRUEBAS_LOCALES")  # Cambiar por variable de entorno después

# Configuración meses
MESES_SIGLAS = {
    1: "E",  2: "F",  3: "MZ", 4: "AB", 5: "MY", 6: "JN",
    7: "JL", 8: "AG", 9: "S", 10: "O", 11: "N", 12: "D"
}

# Preferencias del modo seguro
modo_seguro = {
    "confirmar_eliminacion": True,
    "confirmar_transformacion": True
}


# Para que el código sea más limpio, definimos los estados aquí también
ESTADOS = {
    0: "🕒 Pendiente",
    1: "✅ Hecho",
    2: "🗂️ Pasado"
}