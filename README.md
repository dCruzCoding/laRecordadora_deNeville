# La Recordadora de Neville 👵

> ¡Ay, criatura! Que no se te olvide nada. Haz como Neville y usa la Recordadora para ayudarte con todas esas cosillas importantes de la vida, ya sea desde tu ordenador o desde la nube.

**La Recordadora** es un bot de Telegram multifuncional y con personalidad propia, diseñado para ser tu asistente de recordatorios personal. Este repositorio contiene el código fuente completo, optimizado para funcionar tanto en un **entorno de desarrollo local** como en un **despliegue 24/7 gratuito en la nube (Render)**.

## ✨ Características Principales

-   🌍 **Soporte Global de Zona Horaria**: Configura tu zona horaria para que los recordatorios y avisos siempre lleguen a la hora correcta, sin importar dónde estés.
-   🚀 **Flujo de Bienvenida Guiado**: Un proceso de *onboarding* para nuevos usuarios que presenta a la abuela, explica el funcionamiento y ayuda a realizar la configuración inicial.
-   🪄 **Creación y Edición Avanzada**: Añade recordatorios con un lenguaje natural y modifícalos en cualquier momento con el comando `/editar`, permitiendo cambiar el contenido (fecha/texto) o el aviso previo de forma separada.
-   🔔 **Avisos Previos Personalizables**: Configura notificaciones para que te lleguen minutos, horas o incluso días antes de la fecha límite.
-   📊 **Gestión de Estados Inteligente**: Los recordatorios son `Pendientes` (⬜️) o `Hechos` (✅). Aquellos cuya fecha expira se clasifican dinámicamente como "Pasados" en las listas.
-   🛡️ **Modo Seguro Configurable**: Activa mensajes de confirmación para acciones importantes como borrar o cambiar estados, evitando errores accidentales.
-   ⚙️ **Panel de Ajustes Unificado**: Gestiona todas tus preferencias (Modo Seguro, Zona Horaria) desde un único comando `/ajustes` con una interfaz de botones intuitiva.
-   🔒 **Soporte Multi-Usuario**: El bot puede ser usado por múltiples personas de forma simultánea, manteniendo los datos y configuraciones de cada uno completamente aislados y privados.
-   💾 **Persistencia Total**: Gracias a **SQLite** y **APScheduler**, los recordatorios, configuraciones y avisos programados sobreviven a los reinicios del bot.

## 🛠️ Tecnologías Utilizadas

-   **Lenguaje**: Python 3.12+
-   **Framework del Bot**: `python-telegram-bot`
-   **Planificación de Tareas**: `APScheduler`
-   **Base de Datos**: `SQLite`
-   **Análisis de Fechas**: `dateparser`
-   **Gestión de Zonas Horarias**: `pytz` y `timezonefinderL`
-   **Geolocalización**: `geopy`
-   **Servidor Web (para Render)**: `Flask`

## 🚀 Guía de Instalación y Despliegue

### Requisitos Previos
-   Python 3.12+
-   Git
-   Una cuenta de Telegram y un token para tu bot (obtenido de [@BotFather](https://t.me/BotFather)).

### 1. Clonar y Preparar el Entorno
```bash
# Clona el repositorio
git clone https://github.com/tu-usuario/La_Recordadora.git
cd La_Recordadora

# Crea y activa un entorno virtual
python -m venv venv
# En Windows: venv\Scripts\activate
# En macOS/Linux: source venv/bin/activate

# Instala las dependencias
pip install -r requirements.txt
```

### 2. Configuración (`config.py`)
El archivo `config.py` ya está incluido y preparado. Solo necesitas configurar tu token y tu ID de Telegram.

```python
# config.py
import os
# ... (código del locale) ...

# 1. TOKEN: Lee el token desde una variable de entorno (para Render).
#    Si no la encuentra, usa el valor que pongas aquí (para local).
TOKEN = os.getenv("TELEGRAM_TOKEN", "AQUI_VA_TU_TOKEN_DE_TELEGRAM")

# 2. OWNER_ID: Pon aquí tu ID de usuario de Telegram.
#    Lo puedes obtener hablando con bots como @userinfobot.
OWNER_ID = 123456789
```
La base de datos (`la_recordadora.db`) y el archivo de trabajos (`jobs.sqlite`) se crearán automáticamente en la misma carpeta la primera vez que ejecutes el bot.

### Opción A: Ejecución en Local
1.  Asegúrate de haber puesto tu token y tu ID en `config.py`.
2.  Ejecuta el bot desde la terminal:
    ```bash
    python main.py
    ```
    El bot empezará a funcionar. Para detenerlo, pulsa `Ctrl+C`.

### Opción B: Despliegue en Render (Cloud 24/7)
1.  **Sube tu código a un repositorio de GitHub.** Asegúrate de que el archivo `.gitignore` está presente para no subir las bases de datos locales (`*.db`, `*.sqlite`).

2.  **Crea un "Web Service" en Render** con la siguiente configuración:
    *   **Environment**: `Python`
    *   **Build Command**: `pip install -r requirements.txt`
    *   **Start Command**: `python main.py`
    *   **Instance Type**: `Free`

3.  **Configura las Variables de Entorno** en la pestaña `Environment` del servicio:
    *   `TELEGRAM_TOKEN`: `(Pega aquí tu token de Telegram)`
    *   `PYTHON_VERSION`: `3.12.4`

4.  **Configura un Monitor de Actividad Externo** (ej: Uptime Robot):
    *   Copia la URL pública que te da Render (ej: `https://la-recordadora.onrender.com`).
    *   En Uptime Robot, crea un monitor `HTTP(s)` que visite esa URL cada `5 minutos`. Esto mantendrá el servicio siempre activo y evitará que Render lo "duerma".

## 📖 Guía de Comandos

-   **/start**: Inicia la conversación con la abuela y comienza el proceso de bienvenida si es tu primera vez.
-   **/ayuda**: Muestra la lista completa de comandos disponibles.
-   **/info**: Vuelve a mostrar la guía de uso sobre cómo añadir y gestionar recordatorios.
-   **/lista `[filtro]`**: Muestra todos tus recordatorios. Opcionalmente, puedes filtrar por `pendientes`, `hechos`.
-   **/recordar `[fecha * texto]`**: Crea un nuevo recordatorio. El bot te guiará para añadir un aviso previo.
-   **/borrar `[ID1 ID2 ...]`**: Elimina uno o más recordatorios por su ID.
-   **/cambiar `[ID1 ID2 ...]`**: Cambia el estado de un recordatorio (de `pendiente` a `hecho` o viceversa).
-   **/editar**: Inicia una conversación para modificar un recordatorio existente (contenido o aviso).
-   **/ajustes**: Abre el panel de configuración para gestionar el modo seguro, tu zona horaria o el resumen diario.
-   **/cancelar**: Cancela cualquier operación o conversación en curso.
-   **/reset**: ⚠️ **(Solo para el dueño del bot)** Borra **TODOS** los recordatorios de la base de datos.

## 🏛️ Arquitectura y Versionado

Este proyecto utiliza **Tags de Git** para marcar los lanzamientos de versiones estables. La rama `main` siempre contiene la última versión funcional y probada.

Puedes ver una lista de todas las versiones en la sección de **"Tags"** o **"Releases"** del repositorio en GitHub. Además, consultando el archivo consulta el archivo **[CHANGELOG.md](CHANGELOG.md)** puede explorar un historial detallado de cada versión con información sobre los cambios, mejoras y decisiones de diseño.

Para descargar el código de una versión específica (por ejemplo, `v1.0-local`), puedes usar el siguiente comando:
```bash
# 1. Clona el repositorio de la forma habitual
git clone https://github.com/tu-usuario/La_Recordadora.git
cd La_Recordadora

# 2. Haz "checkout" al tag que quieras revisar
git checkout tags/v1.0-local
```


## 🛣️ Próximos Pasos (Roadmap)

-   **Recordatorios Recurrentes**: Implementar la capacidad de crear recordatorios que se repitan (ej: "todos los lunes a las 9:00").
-   **Estadísticas de Usuario**: Un comando que muestre un resumen de tareas completadas.
-   **(Largo Plazo) v2.0**: Explorar la migración a una arquitectura 100% serverless (ej: Google Cloud Run con Webhooks y Cloud Scheduler) para optimizar costes y eficiencia a gran escala.