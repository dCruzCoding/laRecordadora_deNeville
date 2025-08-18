# La Recordadora 👵 (Versión Cloud en Render)

> ¡Ay, criatura! Que no se te olvide nada. Soy tu abuela digital, ahora viviendo en la nube para recordarte tus cosas 24/7.

Esta es la versión de **La Recordadora** diseñada para un despliegue continuo y gratuito en la plataforma **Render**. Utiliza una arquitectura híbrida para asegurar un funcionamiento 24/7, superando las limitaciones de los planes gratuitos.

## ✨ Características Principales

-   **Siempre Activa**: Gracias a una estrategia de "health check" y un monitor de actividad externo, el bot nunca se duerme y está siempre listo para responder y enviar avisos.
-   **Creación de Recordatorios Intuitiva**: Añade recordatorios usando un formato simple y flexible.
-   **Avisos Previos Personalizables**: Configura notificaciones para que te lleguen minutos, horas o incluso días antes.
-   **Gestión de Estados Inteligente**: Los recordatorios pueden estar `Pendientes`, `Hechos` o pasar automáticamente a `Pasados` si su fecha expira.
-   **Listas Claras y Agrupadas**: Visualiza todos tus recordatorios organizados por su estado para una máxima claridad.
-   **Persistencia de Datos**: Gracias a **SQLite** y **APScheduler**, tus recordatorios y avisos programados sobreviven a los reinicios y redespliegues del servicio.

## 🏗️ Arquitectura de Despliegue

Este bot utiliza una estrategia específica para funcionar en el plan gratuito de **Render** sin ser detenido por inactividad.

1.  **El Problema**: Los "Web Services" gratuitos de Render se "duermen" (spin down) tras 15 minutos sin recibir tráfico HTTP externo, lo que detendría el planificador de avisos (`APScheduler`). Por otro lado, los "Background Workers" (que no se duermen) no están disponibles en el plan gratuito.

2.  **La Solución Híbrida**:
    *   **Bot de Polling (Hilo Principal)**: El núcleo del bot (`python-telegram-bot` con `run_polling()`) se ejecuta en el hilo principal del programa, asegurando que tiene la prioridad necesaria para funcionar correctamente.
    *   **Servidor de Health Check (Hilo Secundario)**: Un micro-servidor web **Flask** se ejecuta en un hilo secundario. Su único propósito es abrir un puerto y responder a las peticiones de salud de Render con un "Estoy vivo". Esto evita que Render detenga el servicio.
    *   **Monitor de Actividad Externo**: Un servicio gratuito como **Uptime Robot** se configura para visitar la URL pública del servicio cada 5 minutos. Esto genera el "tráfico externo" necesario para evitar que Render ponga el servicio a dormir por inactividad.

## 🚀 Guía de Despliegue en Render

Sigue estos pasos para desplegar tu propia instancia de La Recordadora.

### Pre-requisitos
-   Una cuenta en **GitHub** con el código del bot.
-   Una cuenta en **Render.com**.
-   Una cuenta en **UptimeRobot.com** (o un servicio similar).

### Paso 1: Preparar el Repositorio
Asegúrate de que tu repositorio de GitHub contiene:
1.  Todo el código fuente del bot (`main.py`, `config.py`, `handlers/`, etc.).
2.  Un archivo `requirements.txt` con el siguiente contenido exacto:
    ```txt
    # requirements.txt
    python-telegram-bot
    apscheduler
    SQLAlchemy
    dateparser
    pytz
    tzdata
    Flask
    ```

### Paso 2: Configurar el Servicio en Render
1.  En tu Dashboard de Render, haz clic en **New +** y selecciona **Web Service**.
2.  Conecta tu cuenta de GitHub y elige el repositorio del bot.
3.  Rellena la configuración con los siguientes valores:

| Campo | Valor |
| :--- | :--- |
| **Name** | `la-recordadora` (o el nombre que prefieras) |
| **Region** | `Frankfurt (EU Central)` (o la más cercana) |
| **Branch** | `main` (o tu rama principal) |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `python main.py` |
| **Instance Type** | **Free** |

### Paso 3: Configurar las Variables de Entorno
1.  Tras crear el servicio, ve a la pestaña **Environment**.
2.  Haz clic en **Edit** y añade las siguientes dos variables:

| Key | Value |
| :--- | :--- |
| `TOKEN` | `TU_TOKEN_DE_TELEGRAM` |
| `PYTHON_VERSION` | `3.12.4` |

3.  Guarda los cambios. Render iniciará el despliegue.

### Paso 4: ¡Mantenerlo Despierto!
1.  Copia la URL pública de tu servicio de Render (ej: `https://la-recordadora.onrender.com`).
2.  En Uptime Robot, crea un nuevo monitor:
    *   **Monitor Type**: `HTTP(s)`
    *   **Friendly Name**: `La Recordadora Bot`
    *   **URL (or IP)**: Pega la URL de tu servicio.
    *   **Monitoring Interval**: `5 minutes`
3.  Guarda el monitor. ¡Listo! Tu bot se mantendrá activo 24/7.

## 📖 Guía de Comandos

*(Esta sección es idéntica a la del README local, ya que la funcionalidad para el usuario no ha cambiado)*

-   **/start**: Inicia la conversación con la abuela.
-   **/ayuda**: Muestra la lista completa de comandos.
-   **/lista `[filtro]`**: Muestra los recordatorios agrupados por estado (`pendientes`, `hechos`, `pasados`).
-   **/recordar `[fecha * texto]`**: Crea un nuevo recordatorio.
-   **/borrar `[ID1 ID2 ...]`**: Elimina uno o más recordatorios.
-   **/cambiar `[ID1 ID2 ...]`**: Cambia el estado de uno o más recordatorios.
-   **/configuracion `[nivel]`**: Ajusta el "Modo Seguro" para las confirmaciones.
-   **/reset**: ⚠️ Borra **TODOS** los recordatorios (requiere confirmación).
-   **/cancelar**: Cancela la operación en curso.
