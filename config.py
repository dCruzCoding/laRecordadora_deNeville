# config.py
"""
Módulo de Configuración Central.

Este archivo carga y expone las configuraciones para el bot.
Utiliza python-dotenv para cargar un archivo .env en desarrollo local,
manteniendo la compatibilidad con las variables de entorno de producción (Render).
"""

import locale
import os
from dotenv import load_dotenv

# --- Carga de Variables de Entorno ---
# Esta línea busca un archivo .env en el directorio del proyecto y, si lo encuentra,
# carga las variables definidas en él como si fueran variables de entorno del sistema.
# Si el archivo no existe (como en Render), no hace nada y no da error.
load_dotenv()


# =============================================================================
# CONFIGURACIÓN REGIONAL (LOCALE)
# =============================================================================

# Se intenta configurar el 'locale' a español ('es_ES') para que las fechas
# formateadas por Python (ej: nombres de meses) aparezcan en español.
# El bloque try-except anidado maneja el caso en que el sistema operativo
# (especialmente en entornos de despliegue mínimos) no tenga este locale instalado.
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    try:
        locale.setlocale(locale.LC_TIME, "es_ES")
    except locale.Error:
        print("⚠️ Advertencia: El locale 'es_ES' no está disponible en el sistema. Las fechas pueden mostrarse en el idioma por defecto (inglés).")


# =============================================================================
# CREDENCIALES Y AUTORIZACIÓN
# =============================================================================

# --- Token del Bot de Telegram ---
# Se lee el token desde una variable de entorno llamada TELEGRAM_TOKEN.
# Este es el método recomendado y más seguro para entornos de producción (como Render).
# El valor por defecto es un placeholder y NO DEBE ser un token real en el código.
TOKEN: str | None = os.getenv("TELEGRAM_TOKEN")

# --- ID del Propietario del Bot ---
# Se lee desde el entorno. Debe ser un string en el .env que convertimos a int.
OWNER_ID_STR: str | None = os.getenv("OWNER_ID")
OWNER_ID: int = 0 # Valor por defecto seguro
if OWNER_ID_STR and OWNER_ID_STR.isdigit():
    OWNER_ID = int(OWNER_ID_STR)


# =============================================================================
# VALIDACIÓN DE SEGURIDAD INICIAL
# =============================================================================

# Comprobación de que las variables esenciales han sido cargadas.
if not TOKEN or not OWNER_ID:
    print("🚨 ¡ERROR DE CONFIGURACIÓN! 🚨")
    if not TOKEN:
        print("- La variable de entorno TELEGRAM_TOKEN no está definida.")
    if not OWNER_ID:
        print("- La variable de entorno OWNER_ID no está definida o no es un número válido.")
    print("Asegúrate de haber creado un archivo .env en local o de haber configurado las variables en tu plataforma de despliegue.")
    exit()