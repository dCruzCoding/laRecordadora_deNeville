# Guía de Configuración y Despliegue Completa

Este documento proporciona una guía paso a paso para configurar y desplegar "La Recordadora" desde cero, tanto en un entorno local como en la nube usando Supabase, Render y UptimeRobot.

## Requisitos Previos

1.  **Token de Bot de Telegram**: Habla con [@BotFather](https://t.me/BotFather) en Telegram para crear un nuevo bot y obtener su token.
2.  **Tu ID de Telegram**: Habla con [@userinfobot](https://t.me/userinfobot) para obtener tu `chat_id`.
3.  **Cuentas Gratuitas**:
    -   [GitHub](https://github.com/): Para alojar tu código.
    -   [Supabase](https://supabase.com/): Para la base de datos PostgreSQL.
    -   [Render](https://render.com/): Para alojar y ejecutar el bot.
    -   [UptimeRobot](https://uptimerobot.com/): Para mantener el bot activo 24/7.

---

## Paso 1: Configuración del Entorno Local

1.  **Clonar el Repositorio:**
    ```bash
    git clone https://github.com/tu-usuario/La_Recordadora.git
    cd La_Recordadora
    ```

2.  **Crear y Activar un Entorno Virtual:**
    ```bash
    # Crea el entorno
    python -m venv venv_recordadora

    # Activa el entorno
    # En Windows (CMD):
    venv_recordadora\Scripts\activate
    # En macOS/Linux:
    source venv_recordadora/bin/activate
    ```

3.  **Instalar Dependencias:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Crear el Archivo de Configuración (`.env`):**
    -   Busca el archivo `.env.example` en el repositorio.
    -   Crea una copia y renómbrala a `.env`.
    -   Este archivo contendrá tus "secretos" y será ignorado por Git.

---

## Paso 2: Configuración de la Base de Datos (Supabase)

1.  **Crear un Nuevo Proyecto en Supabase:**
    -   Inicia sesión en tu cuenta y haz clic en **"New Project"**.
    -   Rellena los datos de configuración. Aquí tienes las opciones recomendadas:
        -   **Name**: Dale un nombre claro (ej: `la-recordadora-bot`).
        -   **Database Password**: Haz clic en "Generate a password" y **guarda esta contraseña inmediatamente** en un lugar seguro. Es la única vez que la verás.
        -   **Region**: Elige la que prefieras (ej: `Western Europe (Frankfurt)`).
        -   **Secutiry Options & Advanced Configuration**: Deja la opción default (Data API + ConnString, Use public schem & Postgres)
    -   Haz clic en **"Create new project"** y espera a que termine la configuración.

2.  **Obtener la Cadena de Conexión (Connection String):**
    -   Dentro de tu proyecto, visualiza en la barra superior el botón de ***Connect*** y haz click.
    -   **¡IMPORTANTE!** Copia la URI que corresponde al **Connection Pooler** (la que usa el puerto `6543`). Debido a las restricciones de red (IPv4/IPv6), esta es la única que garantiza la conexión desde Render.

3.  **Rellenar el Archivo `.env`:**
    -   Abre tu archivo `.env`.
    -   Pega la URI del Connection Pooler en la variable `SUPABASE_DB_URL`.
    -   Reemplaza `[YOUR-PASSWORD]` en la URI con la contraseña que guardaste al crear el proyecto.
    -   Rellena el resto de las variables con tu token de bot y tu ID de Telegram.

    Tu `.env` se verá así:
    ```env
    # .env
    TELEGRAM_TOKEN="12345:ABCDEFG..."
    OWNER_ID="987654321"
    SUPABASE_DB_URL="postgresql://postgres.xxxxxxxx:[TU_CONTRASEÑA]@aws-0-eu-central-1.pooler.supabase.com:6543/postgres"
    ```

---

## Paso 3: Despliegue en la Nube (Render)

1.  **Subir el Código a GitHub:**
    -   Asegúrate de que tu proyecto está en un repositorio de GitHub.
    -   Verifica que tu archivo `.gitignore` incluye la línea `.env` para no subir tus secretos.

2.  **Crear un "Web Service" en Render:**
    -   En tu Dashboard de Render, haz clic en **New -> Web Service**.
    -   Conecta tu repositorio de GitHub y selecciona el de tu bot.
    -   Configura el servicio con los siguientes valores:
        -   **Name**: `la-recordadora` (o el que prefieras).
        -   **Environment**: `Python`.
        -   **Region**: La que prefieras (ej: Frankfurt).
        -   **Build Command**: `pip install -r requirements.txt`.
        -   **Start Command**: `python main.py`.
        -   **Instance Type**: `Free`.

3.  **Añadir las Variables de Entorno:**
    -   Antes de finalizar, ve a la sección **"Advanced Settings"** o busca la pestaña **"Environment"** después de crear el servicio.
    -   Añade las siguientes variables (haz clic en "Add Environment Variable" por cada una):
        -   **Key**: `TELEGRAM_TOKEN`, **Value**: `(Pega aquí tu token de Telegram)`
        -   **Key**: `OWNER_ID`, **Value**: `(Pega aquí tu ID de Telegram)`
        -   **Key**: `SUPABASE_DB_URL`, **Value**: `(Pega aquí la URI COMPLETA de Supabase, con la contraseña)`
        -   **Key**: `PYTHON_VERSION`, **Value**: `3.12.4` (o la versión que uses)

4.  **Lanzar el Despliegue:**
    -   Haz clic en **"Create Web Service"**. Render construirá e iniciará tu bot. El primer despliegue puede tardar unos minutos.

5.  **Configurar la Base de Datos por Primera Vez:**
    -   Una vez que el despliegue sea exitoso ("Live"), el bot se habrá ejecutado una vez y habrá creado las tablas en Supabase.
    -   Ve a tu proyecto de Supabase -> **SQL Editor**.
    -   Pega y ejecuta el siguiente script para desactivar RLS:
        ```sql
        ALTER TABLE public.recordatorios DISABLE ROW LEVEL SECURITY;
        ALTER TABLE public.configuracion DISABLE ROW LEVEL SECURITY;
        ```

---

## Paso 4: Mantener el Bot Activo (UptimeRobot)

1.  **Obtener la URL de Render:**
    -   En la página de tu servicio en Render, copia la URL pública (ej: `https://la-recordadora.onrender.com`).

2.  **Crear un Monitor en UptimeRobot:**
    -   Inicia sesión y haz clic en **"+ Add New Monitor"**.
    -   **Monitor Type**: `HTTP(s)`.
    -   **Friendly Name**: `La Recordadora Bot`.
    -   **URL (or IP)**: Pega la URL de Render.
    -   **Monitoring Interval**: **5 minutes**.
    -   Haz clic en **"Create Monitor"**.

¡Listo! Con estos pasos, tu bot estará funcionando 24/7 en la nube, con una base de datos persistente y un sistema que lo mantiene siempre activo.