import locale

# === CONFIGURACIÓN GENERAL ===
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    locale.setlocale(locale.LC_TIME, "es_ES")

TOKEN = "TU_TOKEN_AQUI_PARA_PRUEBAS_LOCALES"  # Cambiar por variable de entorno después

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
