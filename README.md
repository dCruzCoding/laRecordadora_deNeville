# La Recordadora de Neville 👵

> ¡Ay, criatura! Que no se te olvide nada. Haz como Neville y usa la Recordadora para ayudarte con todas esas cosillas importantes de la vida, ya sea desde tu ordenador o desde la nube.

**La Recordadora** es un bot de Telegram multifuncional y con personalidad propia, diseñado para ser tu asistente de recordatorios personal. Este repositorio contiene el código fuente completo, construido sobre una arquitectura robusta y escalable, listo para funcionar tanto en un **entorno de desarrollo local** como en un **despliegue 24/7 en la nube**.

## ✨ Características Principales

-   🌍 **Soporte Global de Zona Horaria**: Configura tu zona horaria para que los recordatorios y avisos siempre lleguen a la hora correcta, sin importar dónde estés.
-   🌞 **Resumen Diario Proactivo**: Cada mañana, recibe un resumen con las tareas del día, totalmente personalizable en hora y estado desde `/ajustes`.
-   🚀 **Flujo de Bienvenida Guiado**: Un proceso de *onboarding* para nuevos usuarios que presenta a la abuela, explica el funcionamiento y ayuda a realizar la configuración inicial.
-   🪄 **Creación y Edición Avanzada**: Añade recordatorios con un lenguaje natural y modifícalos en cualquier momento con el comando `/editar`.
-   🔔 **Notificaciones Interactivas**: Los avisos incluyen botones para posponer (`+10 min`), marcar como hecho (`✅ Hecho`) o simplemente descartar (`👌 OK`).
-   🛡️ **Modo Seguro Configurable**: Activa mensajes de confirmación para acciones importantes como borrar o cambiar estados, evitando errores accidentales.
-   🔒 **Soporte Multi-Usuario**: El bot puede ser usado por múltiples personas de forma simultánea, manteniendo los datos de cada uno completamente aislados.
-   💾 **Persistencia Total en la Nube**: Gracias a **Supabase (PostgreSQL)**, los recordatorios, configuraciones y avisos programados sobreviven a los reinicios y se mantienen seguros en una base de datos cloud.

## 🛠️ Tecnologías Utilizadas

-   **Lenguaje**: Python 3.12+
-   **Framework del Bot**: `python-telegram-bot`
-   **Planificación de Tareas**: `APScheduler`
-   **Base de Datos**: `PostgreSQL` (a través de **Supabase**)
-   **Driver de Base de Datos**: `psycopg2-binary`
-   **Análisis de Fechas**: `dateparser`
-   **Gestión de Zonas Horarias**: `pytz` y `timezonefinderL`
-   **Geolocalización**: `geopy`
-   **Servidor Web (para Health Checks)**: `Flask`

## 🚀 Instalación y Despliegue

Este proyecto está diseñado para ser desplegado fácilmente. La configuración se gestiona a través de un archivo `.env` para el desarrollo local y variables de entorno en producción.

### Requisitos Previos
-   Python 3.12+
-   Git
-   Una cuenta de Telegram y un token de bot (obtenido de [@BotFather](https://t.me/BotFather)).
-   Cuentas en [Supabase](https://supabase.com/), [Render](https://render.com/) y [UptimeRobot](https://uptimerobot.com/) (para el despliegue en la nube).

### Configuración Rápida
1.  Clona el repositorio.
2.  Crea y activa un entorno virtual e instala las dependencias con `pip install -r requirements.txt`.
3.  Crea un archivo `.env` a partir de `.env.example` y rellénalo con tus credenciales.

### 📖 **Guía Completa de Despliegue**

Para obtener una guía detallada y paso a paso sobre cómo configurar el entorno local, la base de datos en Supabase, el despliegue en Render y el monitor de actividad en UptimeRobot, por favor, consulta el siguiente documento:

➡️ **[HOWTO.md - Guía de Configuración y Despliegue Completa](HOWTO.md)**

## 📖 Guía de Comandos
   
-   **/start**: Inicia la conversación con la abuela y comienza el proceso de bienvenida si es tu primera vez.
-   **/ayuda**: Muestra la lista completa de comandos disponibles.
-   **/info**: Vuelve a mostrar la guía de uso sobre cómo añadir y gestionar recordatorios.
-   **/lista**: Muestra todos tus recordatorios con una interfaz interactiva.
-   **/recordar**: Crea un nuevo recordatorio. El bot te guiará para añadir un aviso previo.
-   **/borrar**: Inicia una conversación para eliminar uno o más recordatorios.
-   **/cambiar**: Abre la interfaz para cambiar el estado de un recordatorio (de `pendiente` a `hecho` o viceversa).
-   **/editar**: Inicia una conversación para modificar un recordatorio existente (contenido o aviso).
-   **/ajustes**: Abre el panel de configuración para gestionar el modo seguro, tu zona horaria o el resumen diario.
-   **/cancelar**: Cancela cualquier operación o conversación en curso.
-   **/reset**: ⚠️ **(Solo para el dueño del bot)** Borra **TODOS** los recordatorios de la base de datos.

### ⚡ Modo Rápido (Atajos)

Para agilizar el uso, la mayoría de los comandos de gestión aceptan argumentos directamente en la misma línea, permitiéndote saltar pasos intermedios:

-   **/recordar**: Puedes crear un recordatorio en un solo paso.
    -   *Ejemplo:* `/recordar mañana a las 15:00 * Comprar ingredientes para la poción`

-   **/borrar** y **/cambiar**: Puedes aplicar la acción a varios recordatorios a la vez separando sus IDs por espacios.
    -   *Ejemplo:* `/borrar 1 5 12`

-   **/editar**: Puedes especificar directamente el ID del recordatorio que quieres modificar (solo se permite un ID a la vez).
    -   *Ejemplo:* `/editar 7`
  
-   **/lista**: Puedes incluir un filtro para visualizar únicamente recordatorios pendientes o sólo los que ya marcaste como hechos.
    -   *Ejemplo:* `/lista hecho` o `/lista pendiente`
-   

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
-   **(Largo Plazo) Explorar Alternativas a Render**: Tras probar y descartar arquitecturas *serverless* (como GCP Cloud Functions) por su incompatibilidad fundamental con componentes con estado (`ConversationHandler`, `APScheduler`), se explorará en el futuro el despliegue en **Fly.io**. Su generoso plan gratuito permite ejecutar procesos persistentes 24/7, lo que lo convierte en un candidato ideal para una solución de alojamiento gratuita y más robusta.