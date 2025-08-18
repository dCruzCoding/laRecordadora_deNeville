### **README.md para La Recordadora (Versión Unificada)**

# La Recordadora 👵 (Versión Unificada)

> ¡Ay, criatura! Que no se te olvide nada. Soy tu abuela digital, aquí para ayudarte a recordar todas esas cosillas importantes de la vida, ya sea desde tu ordenador o desde la nube.

**La Recordadora** es un bot de Telegram personalizable diseñado para ser tu asistente de recordatorios personal. Este repositorio contiene el código para ejecutar el bot tanto en un **entorno de desarrollo local** como en un **despliegue continuo y gratuito en la nube (Render)**.

## ✨ Características Principales

-   **Doble Entorno de Ejecución**: Optimizado para funcionar en local para pruebas y en la nube (Render) para un servicio 24/7.
-   **Creación de Recordatorios Intuitiva**: Añade recordatorios usando un formato simple y flexible.
-   **Avisos Previos Personalizables**: Configura notificaciones para que te lleguen minutos, horas o incluso días antes.
-   **Gestión de Estados Inteligente**: Los recordatorios pueden estar `Pendientes`, `Hechos` o pasar automáticamente a `Pasados` si su fecha expira.
-   **Listas Claras y Agrupadas**: Visualiza todos tus recordatorios organizados por su estado para una máxima claridad.
-   **Persistencia de Datos**: Gracias a **SQLite** y **APScheduler**, los recordatorios y avisos programados sobreviven a los reinicios.
-   **Modo Seguro**: Configura la necesidad de confirmación para acciones destructivas.
-   **Atajos de Comandos**: Interactúa rápidamente proporcionando IDs directamente con los comandos `/borrar` y `/cambiar`.

## 🏛️ Arquitectura y Versionado

El bot ha evolucionado a través de varias versiones clave, cada una marcada con un **Tag de Git** para facilitar la consulta de su código fuente en un punto específico del tiempo. La rama `main` siempre contiene la última versión estable.

### v1.0: Entorno Local (Polling Puro)
-   **Tag en Git**: `v1.0-local`
-   **Ejecución**: Se ejecuta con `python main.py` en un entorno local.
-   **Mecanismo**: Utiliza `python-telegram-bot` en modo `polling`, donde el bot pregunta constantemente a Telegram si hay mensajes nuevos.
-   **Uso Ideal**: Desarrollo, pruebas y añadir nuevas funcionalidades.

### v1.1: Entorno Cloud - Render (Híbrido Polling + Servidor Web)
-   **Tag en Git**: `v1.1-render`
-   **Ejecución**: Desplegado como un "Web Service" gratuito en Render.
-   **Mecanismo**: Para cumplir con los requisitos del plan gratuito de Render, el bot utiliza una arquitectura híbrida:
    *   Un **hilo principal** ejecuta el bot en modo `polling`.
    *   Un **hilo secundario** levanta un micro-servidor **Flask** que responde a los chequeos de salud de Render, evitando que el servicio sea detenido.
    *   Un **monitor de actividad externo** (como Uptime Robot) visita la URL del servicio cada 5 minutos para evitar que se "duerma" por inactividad.
-   **Uso Ideal**: Producción. Un servicio estable, gratuito y que funciona 24/7.


## 🚀 Guía de Instalación y Despliegue

### Requisitos Previos
-   Python 3.11+
-   Git
-   Una cuenta de GitHub

### 1. Clonar y Preparar el Entorno
```bash
# Clona el repositorio
git clone [URL_DE_TU_REPOSITORIO]
cd La_Recordadora

# Crea y activa un entorno virtual
python -m venv venv
# En Windows: venv\Scripts\activate
# En macOS/Linux: source venv/bin/activate

# Instala las dependencias
pip install -r requirements.txt
```

### 2. Configuración (`config.py`)
Crea un archivo `config.py` en la raíz del proyecto. Este archivo está diseñado para funcionar tanto en local como en Render sin necesidad de cambios.

```python
# config.py
import os
import locale

# Intenta configurar el idioma a español, si falla, continúa sin detenerse.
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except locale.Error:
    print("⚠️ Advertencia: El locale 'es_ES' no está disponible.")

# Lee el TOKEN desde una variable de entorno (para Render).
# Si no la encuentra, usa el valor que pongas aquí (para local).
TOKEN = os.environ.get("TOKEN", "AQUI_VA_TU_TOKEN_SI_ESTAS_EN_LOCAL")

# Diccionario de estados
ESTADOS = {
    0: "🕒", # Pendiente
    1: "✅", # Hecho
    2: "🗂️"  # Pasado
}
```

### Opción A: Ejecución en Local
1.  Asegúrate de haber puesto tu token de Telegram en la línea `TOKEN = ...` de `config.py`.
2.  Ejecuta el bot desde la terminal:
    ```bash
    python main.py
    ```
    El bot empezará a funcionar. Para detenerlo, pulsa `Ctrl+C`.

### Opción B: Despliegue en Render (Cloud 24/7)
1.  **Sube tu código a un repositorio de GitHub.** Asegúrate de que el archivo `.gitignore` está presente para no subir las bases de datos locales.

2.  **Crea un "Web Service" en Render** con la siguiente configuración:
    *   **Name**: `la-recordadora` (o el que prefieras)
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `python main.py`
    *   **Instance Type**: `Free`

3.  **Configura las Variables de Entorno** en la pestaña `Environment` del servicio:
    *   `TOKEN`: `(Pega aquí tu token de Telegram)`
    *   `PYTHON_VERSION`: `3.12.4`

4.  **Configura un Monitor de Actividad Externo** (ej: Uptime Robot):
    *   Copia la URL pública que te da Render (ej: `https://la-recordadora.onrender.com`).
    *   En Uptime Robot, crea un monitor `HTTP(s)` que visite esa URL cada `5 minutos`. Esto mantendrá el servicio siempre activo.

## 📖 Guía de Comandos
*(Esta sección resume la funcionalidad para el usuario final)*

-   **/start**: Inicia la conversación con la abuela.
-   **/ayuda**: Muestra la lista completa de comandos.
-   **/lista `[filtro]`**: Muestra los recordatorios agrupados por estado (`pendientes`, `hechos`, `pasados`).
-   **/recordar `[fecha * texto]`**: Crea un nuevo recordatorio.
-   **/borrar `[ID1 ID2 ...]`**: Elimina uno o más recordatorios.
-   **/cambiar `[ID1 ID2 ...]`**: Cambia el estado de uno o más recordatorios.
-   **/configuracion `[nivel]`**: Ajusta el "Modo Seguro".
-   **/reset**: ⚠️ Borra **TODOS** los recordatorios (requiere confirmación).
-   **/cancelar**: Cancela la operación en curso.

## 🛣️ Próximos Pasos (Roadmap)
-   **v1.2**: Implementación de funcionalidad **Multi-Usuario**, permitiendo que diferentes personas usen el bot de forma aislada.
-   **v2.0**: Migración de la arquitectura a **Google Cloud Platform (GCP)**, usando Webhooks (Cloud Run) y un planificador externo (Cloud Scheduler) para una solución 100% serverless y más eficiente.

## 🏷️ Versionado

Este proyecto utiliza **Tags de Git** para marcar los lanzamientos de versiones estables. Puedes ver una lista de todas las versiones en la sección de **"Tags"** o **"Releases"** del repositorio en GitHub.

Para descargar el código de una versión específica (por ejemplo, `v1.0-local`), puedes usar el siguiente comando:
```bash
# Clona el repositorio y se posiciona directamente en el tag deseado
git clone --branch v1.0-local [URL_DE_TU_REPOSITORIO]
```