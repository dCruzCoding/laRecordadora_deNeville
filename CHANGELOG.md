# Changelog de La Recordadora 👵

Este documento registra los cambios significativos, decisiones de diseño y problemas resueltos a lo largo del desarrollo y despliegue del bot.

---

## [v1.7-migration-supabase] - 2025-10-28

### ✨ Mejoras

-   **Renovación integral del comando `/lista` con filtrado avanzado:** Se ha mejorado la capacidad de gestión de recordatorios.
    -   **Navegación por Estado:** La interfaz de `/lista` ahora incluye botones (`✅ Hechos` / `⬜️ Pendientes`) que permiten filtrar los recordatorios por su estado de completado, además del filtrado temporal existente (`📜 Próximos` / `🗂️ Pasados`).
    -   **Limpieza de Tareas Completadas:** Se ha añadido un botón `🧹 Limpiar Hechos` en la vista correspondiente, permitiendo a los usuarios archivar y borrar masivamente todas las tareas que ya han completado.
    -   **Interfaz Optimizada:** El teclado de navegación de la lista se ha rediseñado para ser más compacto, unificando los botones de filtrado en una sola fila.
    -   **Modo Rápido Funcional:** Ahora es posible acceder directamente a una vista filtrada usando comandos como `/lista hechos` o `/lista pasados`.
  
-   **Migración completa de la base de datos a Supabase (PostgreSQL):** Externalización BBDD de SQLite (local) a Supabase (PostgreSQL).
    -   **Persistencia y Seguridad:** Los datos ahora residen en una base de datos cloud, eliminando el riesgo de pérdida de datos que existía al estar en un archivo local que se borraba con cada despliegue en Render.
    -   **Refactorización de la capa de datos para compatibilidad con PostgreSQL:** Para la migración se ha adaptado el código:
        1. Actualización de la sintaxis, sustituyendo el placeholder `?` (de SQLite) por `%s` (de `psycopg2`) en todas las consultas SQL. (2) 
        2. Funciones de las consultas específicas de SQLite sustituidas por equivalentes en PostgreSQL (ej: `IFNULL` a `COALESCE`, `INSERT OR REPLACE` a `INSERT ... ON CONFLICT`).

### 🐛 Problemas resueltos

-   **_E014_ - El comando `/lista` ignoraba los argumentos de filtrado**
    -   **Problema (1):** Aunque la documentación y la ayuda del bot indicaban que se podía usar `/lista pasados` o `/lista hechos`, esta funcionalidad no estaba implementada. Siempre mostraba por defecto de recordatorios pendientes.
    -   **Solución (1):** Se ha modificado el `CommandHandler` del comando `/lista` para que lea y procese los argumentos (`context.args`). Ahora, el bot interpreta correctamente los filtros proporcionados, como "pasados" o "hechos", y muestra la vista correspondiente, mejorando significativamente la usabilidad y la coherencia con la documentación.

-   **_E013_ - Corrección de fallos críticos post-migración a Supabase**
    -   **Problema (1):** El bot no podía arrancar en el servidor de producción debido a un fallo de conexión de red (`Host desconocido`) al intentar contactar con la nueva base de datos.
    -   **Solución (1):** Se diagnosticó que los nuevos proyectos gratuitos de Supabase ya no asignan una IP pública IPv4. Se migró la estrategia de conexión para usar el **Connection Pooler** de Supabase (puerto `6543`), que sí es compatible, y se ajustó la configuración de `APScheduler` para asegurar una conexión estable.

    -   **Problema (2):** Múltiples comandos (`/lista`, `/editar`, `/borrar`, `/cambiar`) y las notificaciones se caían con un `TypeError` al procesar recordatorios que incluían una fecha.
    -   **Solución (2):** Se refactorizó todo el código que maneja fechas para tratar directamente con los objetos `datetime` nativos que `psycopg2` devuelve, eliminando las conversiones redundantes desde el formato ISO 8601 (`fromisoformat`) que causaban el error.



## [v1.6-assistant-upgrade] - 2025-09-10

### ✨ Mejoras

-   **Funcionalidad proactiva -> resumen diario personalizable:** La Recordadora ahora toma la iniciativa.
    -   Cada mañana, envía un resumen con las tareas programadas para ese día, utilizando la zona horaria del usuario para ser precisa.
    -   Esta funcionalidad es totalmente configurable desde un nuevo menú en `/ajustes`. Los usuarios pueden activar/desactivar el resumen y elegir la hora exacta en la que quieren recibirlo.
    -   La programación es individual para cada usuario y se gestiona mediante eventos, siendo una solución muy eficiente.

-   **Notificaciones interactivas (acciones directas):** Los avisos (previos y principales) ya no son solo texto, ahora incluyen botones de acción rápida.
    -   `✅ Hecho`: Marca el recordatorio como completado y cancela cualquier aviso futuro.
    -   `⏰ +10 min`: Pospone el recordatorio. Esta acción no solo reprograma el aviso, sino que **actualiza la fecha y hora del recordatorio** en la base de datos.
    -   `👌 OK`: Descarta la notificación y la marca como "vista", evitando que el aviso vuelva a aparecer en la lista de pendientes.
    -   Los botones se muestran de forma inteligente (ej: no se puede posponer un aviso de menos de 10 minutos).

-   **Interfaz de listas unificada y reutilizable:** Se ha refactorizado por completo la forma en que se muestran las listas de recordatorios.
    -   Los comandos `/borrar`, `/cambiar` y `/editar` ahora utilizan el mismo componente de lista interactiva que `/lista`, creando una experiencia de usuario 100% consistente.
    -   Esta interfaz universal incluye **paginación** (`<<` y `>>`), la capacidad de **cambiar entre vistas** (Pendientes/Pasados) y **botones de acción contextuales** (`Limpiar`, `Cancelar`).
    -   La posición de los botones de navegación se ha fijado para evitar que se muevan, mejorando la usabilidad.

-   **Optimización y refactorización integral del código:** Se ha realizado una revisión completa de todo el código base para mejorar su calidad, rendimiento y mantenibilidad.
    -   **Optimización de consultas SQL:** Se han eliminado bucles ineficientes en los handlers `/borrar` y `/cambiar`, reemplazándolos por consultas `... WHERE user_id IN (...)`, lo que reduce drásticamente las operaciones de base de datos.
    -   **Mejora de la estructura de módulos:** Se ha refactorizado la lógica para una mejor separación de responsabilidades (ej: la gestión del resumen diario ahora está completamente encapsulada en su propio módulo).
    -   **Se ha enriquecido la documentación** en todos los archivos con `docstrings` y comentarios explicativos para aclarar la arquitectura y las decisiones de diseño.
    -   **Manejo de secretos profesional:** Se ha implementado el uso de archivos `.env` con `python-dotenv` para la gestión segura de credenciales en entornos locales.


### 🐛 Problemas resueltos

-   **_E012_ - Corrección de precisión en el cálculo de tiempos**
    -   **Problema:** Se producía un desajuste de un minuto al posponer avisos debido a un error de cálculo al convertir los segundos restantes a minutos, que truncaba los decimales (`int()`).
    -   **Solución:** Se ha sustituido el truncamiento por un redondeo (`round()`). Este ajuste garantiza la máxima precisión y elimina cualquier inconsistencia entre la hora notificada al usuario y la mostrada en `/lista`.

-   **_E011_ - Mejoras en la funcionalidad para posponer avisos**
    -   **Problema:** Un aviso solo se podía posponer una vez, ya que la notificación resultante no incluía de nuevo el botón para posponer. Además, la nueva hora del aviso no se reflejaba en `/lista`.
    -   **Solución:** Se ha modificado la lógica para que los avisos pospuestos generen una notificación que también incluye el botón de posponer, permitiendo un bucle continuo. Adicionalmente, el campo `aviso_previo` ahora se recalcula y se **actualiza en la base de datos** con cada posposición, asegurando que `/lista` siempre muestre la hora del próximo aviso de forma precisa.
  
-   **_E010_ - Gestión del ciclo de vida y apagado local controlado (`Ctrl+C`)**
    -   **Problema:** Al ejecutar el bot en local, la señal de interrupción (`Ctrl+C`) era capturada incorrectamente por la lógica de reinicio de errores, impidiendo un apagado limpio.
    -   **Solución:** Se ha reestructurado el bucle principal del programa. Ahora, solo los errores de red (`NetworkError`) activan un reinicio automático. Cualquier otro `Exception` o `Ctrl+C` detiene el bot de forma predecible, mejorando la robustez y la experiencia de desarrollo.

-   **_E009_ - Optimización de la navegación y mantenibilidad en `/ajustes`**
    -   **Problema:** El botón `<< Volver` en los submenús de `/ajustes` no funcionaba y rompía la conversación debido a un `AttributeError`. Esto ocurría al reutilizar la función del comando, que esperaba una estructura de `update` diferente a la proporcionada por un botón.
    -   **Solución:** Se ha refactorizado la lógica creando una función interna (`_build_main_menu`) dedicada a construir el menú principal. Esto elimina la duplicación de código, soluciona el error y mejora la experiencia de usuario al editar el mensaje en lugar de borrarlo y reenviarlo.

-   **_E008_ - Reparación del flujo de bienvenida (`/start`)**
    -   **Problema:** Un `AttributeError` fatal rompía el proceso de bienvenida para nuevos usuarios justo después de seleccionar el Modo Seguro, impidiendo completar la configuración.
    -   **Solución:** Se ha corregido la obtención del `chat_id` en el `CallbackQueryHandler` correspondiente para que use `query.message.chat_id`, permitiendo que el flujo de 'onboarding' se complete sin errores.

-   **_E007_ - Mejoras en la robustez de la interfaz y entradas de usuario**
    -   **Problema (1):** La aplicación se caía con un `AttributeError` al pulsar botones en varios menús, porque el código intentaba acceder al `chat_id` desde `query.effective_chat`, que no existe en las respuestas de botones.
    -   **Solución (1):** Se ha estandarizado el acceso al identificador del chat en todos los `CallbackQueryHandlers` para que utilicen la forma correcta: `query.message.chat_id`.

    -   **Problema (2):** Las confirmaciones que requerían escribir "SI" o "NO" eran sensibles a mayúsculas y acentos, forzando al usuario a escribirlo de una única manera.
    -   **Solución (2):** Se ha implementado el uso de una función de normalización de texto para que el bot entienda de forma flexible distintas variaciones (`Sí`, `si`, `NO`, `no`, etc.).

    -   **Problema (3):** El bot generaba un `ValueError` si, al construir un teclado dinámico, una de las filas de botones quedaba vacía.
    -   **Solución (3):** Se ha añadido una comprobación para asegurar que solo las filas que contienen botones se añadan al `InlineKeyboardMarkup` final.

-   **_E006_ - Correcciones en la lógica de listas y avisos**
    -   **Problema (1):** Los recordatorios marcados como 'Hecho' (`✅`) desaparecían de la lista de pendientes antes de que su fecha expirara, lo cual resultaba confuso.
    -   **Solución (1):** Se ha ajustado la consulta a la base de datos para que los recordatorios completados permanezcan en la vista de pendientes hasta que su fecha/hora haya pasado.

    -   **Problema (2):** El bot permitía programar avisos para una fecha que ya estaba en el pasado, lo que no tenía sentido y no generaba ninguna notificación.
    -   **Solución (2):** Se ha implementado una validación en los flujos de `/recordar` y `/editar` que comprueba si la hora del aviso es futura. Si no lo es, el bot informa al usuario y le permite introducir un nuevo valor.

    -   **Problema (3):** Al navegar entre las páginas o al cambiar de la vista de "Pendientes" a "Pasados", el botón `❌ Cancelar` desaparecía en los contextos que lo requerían (como en `/borrar` o `/editar`).
    -   **Solución (3):** Se ha corregido la gestión de estado en los `callback_data` de los botones de navegación para que la información sobre la visibilidad del botón "Cancelar" persista correctamente.

    -   **Problema (4):** La lista de recordatorios "Pasados" mostraba información irrelevante sobre avisos previos que ya no iban a ocurrir.
    -   **Solución (4):** Se ha añadido una comprobación en la función de formato de listas para que la línea del aviso (`🔔 Aviso a las...`) solo se muestre para recordatorios pendientes y futuros.


### 📝 Notas de desarrollo y seguridad

-   **_S001 - Fuga de Credenciales en el Historial de Git_**
    -   **Incidente:** Se detectó que, al hacer público el repositorio, las credenciales (`TELEGRAM_TOKEN` y `OWNER_ID`) eran visibles en los commits más antiguos del historial de Git.
    -   **Acciones de mitigación (Protocolo estándar):**
        1.  **Revocación inmediata:** El `TELEGRAM_TOKEN` expuesto fue revocado inmediatamente a través de `@BotFather` para invalidarlo por completo, eliminando el riesgo principal.
        2.  **Limpieza del historial:** Se utilizó la herramienta `git-filter-repo` para reescribir toda la historia del repositorio. Este proceso recorrió cada commit y reemplazó las credenciales expuestas por placeholders genéricos (`***REDACTED***`).
        3.  **Push forzado:** El nuevo historial limpio fue subido a GitHub usando `git push --force`, sobreescribiendo la versión "sucia" de forma permanente.
    -   **Resultado:** El repositorio es ahora 100% seguro y no contiene ninguna información sensible en su historial, manteniendo al mismo tiempo la integridad de los commits y los tags. Esta operación subraya la importancia de nunca incluir secretos directamente en el código fuente.





## [v1.5-edit-and-stability] - 2025-08-30

### ✨ Mejoras
-   **Nueva funcionalidad -> Comando `/editar`:** ¡Se ha añadido una nueva funcionalidad principal! Los usuarios ahora pueden modificar sus recordatorios existentes a través de un nuevo comando `/editar`.
    -   El comando inicia una conversación guiada que permite elegir un recordatorio por su ID.
    -   Ofrece un menú con botones para seleccionar si se quiere modificar el **contenido** (fecha/texto) o el **aviso previo**.
    -   Cada flujo de edición es conversacional y está integrado con la personalidad del bot.
-   **Gestión de interrupciones de comandos (bug crítico solucionado):** Se ha refactorizado la gestión de las conversaciones para solucionar un problema fundamental de la experiencia de usuario.
-   **Sistema de estados rediseñado:** Se ha refactorizado por completo la lógica de los estados de los recordatorios para que sea más intuitiva y potente.
    -   El **estado de finalización** (`Pendiente`/`Hecho`) ahora es independiente del **estado temporal**.
    -   El estado **"Pasado"** ya no se guarda en la base de datos, sino que se **calcula dinámicamente** al mostrar las listas si un recordatorio `Pendiente` tiene una fecha expirada.
-   **Visualización de listas mejorada:** La presentación de los recordatorios se ha modernizado para una mayor claridad (`⬜️` para Pendiente, `✅` para Hecho).

### 🐛 Problemas resueltos

-   **_E005_**
    -   **Problema:** Si un usuario escribía un comando (ej: `/lista`) mientras estaba en medio de otra conversación (ej: `/ajustes`), el bot se comportaba de forma errática: a veces el comando se ejecutaba, otras veces era bloqueado por un mensaje de `fallback`, creando una experiencia inconsistente.
    -   **Solución:** Se ha implementado un mecanismo de protección utilizando los `fallbacks` de cada `ConversationHandler`. En muchos casos, si se detecta un comando inesperado, el bot informa al usuario de que está en mitad de un proceso y le instruye para que use `/cancelar` antes de continuar.

### 📝 Notas de desarrollo

-   **_E005_ - Comportamiento conocido de interrupciones:**
    -   **Decisión yécnica:** Se exploró el uso de **grupos de prioridad** para forzar un bloqueo total de interrupciones, pero se descartó por añadir una complejidad excesiva al código. La solución actual con `fallbacks` es más simple y cubre la mayoría de los casos.
    -   **Causa raíz:** La inconsistencia restante se debe a que los **puntos de entrada (`entry_point`) de un nuevo comando conversacional (ej: `/borrar`) tienen prioridad sobre el `fallback` genérico de una conversación ya activa (ej: `/editar`)**.
    -   **Guía de comportamiento:** Se ha aceptado este comportamiento como una limitación conocida y documentada. La siguiente guía rápida explica cómo responde el bot en cada escenario:

        #### ❓ **¿Qué pasa si interrumpo una conversación?**

        *   **Caso A: El bot te bloquea con un mensaje ("¡Quieto ahí!")**
            *   **Cuándo:** Generalmente, al usar un comando simple (como `/lista`) durante una conversación que espera texto (como `/recordar`).
            *   **Qué hacer:** Tu progreso está a salvo. Continúa la conversación o usa `/cancelar`.

        *   **Caso B: El bot "anida" las conversaciones (Ej: `/editar` y luego `/borrar`)**
            *   **Cuándo:** Al iniciar una conversación sobre otra que también espera texto.
            *   **Comportamiento:** La conversación de `/borrar` se pone "encima". Al terminarla, volverás automáticamente al punto donde dejaste `/editar`.
            *   **Qué hacer:** Termina la conversación más reciente para volver a la anterior.

        *   **Caso C: Un comando se "cuela" (Ej: `/ajustes` y luego `/lista`)**
            *   **Cuándo:** Al usar un comando de texto cuando el bot espera una pulsación de botón.
            *   **Comportamiento:** El comando `/lista` se ejecutará. La conversación de `/ajustes` quedará "pausada" en segundo plano.
            *   **Qué hacer:** Puedes volver a la conversación de `/ajustes` simplemente pulsando uno de sus botones originales.





## [v1.4-global-support] - 2025-08-22

### ✨ Mejoras
-   **Soporte global de zona horaria:** ¡El bot ahora es consciente de la zona horaria de cada usuario! Se ha añadido un flujo para configurar la zona horaria de forma automática (con ubicación) o manual (escribiendo una ciudad).
-   **Flujo de onboarding guiado:** Se ha mejorado la conversación de bienvenida (`/start`) para los nuevos usuarios. El bot se presenta, explica su función y guía al usuario a través de la configuración inicial (modo seguro y zona horaria). 
-   **Comando `/info`:** Se añade comando `/info` que permite revisar el contenido sobre cómo usar el bot que venía en el mensaje de inicio.
-   **Comando `/ajustes` Unificado:** Se ha fusionado el comando `/timezone` dentro de `/configuracion` y todo se ha renombrado a un único y elegante comando `/ajustes`.
-   **Interfaz de botones completa:** Todo el flujo de `/ajustes` ahora es 100% interactivo, usando botones `Inline` para una experiencia de usuario fluida y sin errores.
-   **Robustez de las conversaciones:** Se ha mejorado la cancelación para que elimine los teclados de respuesta y se han pulido los flujos de diálogo para guiar mejor al usuario.
-   **Lógica de reactivación inteligente:** Al reactivar un recordatorio (`Hecho` -> `Pendiente`), el bot ahora comprueba si su fecha ya ha pasado para evitar ofrecer la reprogramación de avisos sin sentido.
- **Corrección de sincronización timezone e inclusion de _smart_ timezone:** Se soluciona el error E001, y además se incluye una nueva funcionalidad para que, al cambiar la zona horaria, se puedan pasar los recordatorios que tenías registrados a ese nuevo uso horario.


### 🐛 Problemas resueltos
-   **_E004_**  
    -   **Problema:** La detección de zona horaria manual a veces falla, mostrando un mensaje de "timezone_reintentar".
    -   **Diagnóstico:** Se identificó que la librería `geopy` puede fallar por timeouts de red, especialmente en el entorno de Render.
    -   **Solución:** Se ha añadido un `timeout=10` explícito a la llamada de `geopy`. Esto hace al bot más resiliente a la congestión de red, aumentando la probabilidad de éxito sin impactar negativamente en el tiempo de respuesta en condiciones normales. Además, se han añadido interacciones con el usuario en esta parte para mejorar su acompañamiento.
-   -   **_E003_**
    -   **Problema:** La conversión de zonas horarias fallaba, mostrando horas incorrectas (ej: 10:55 en lugar de 02:55).
    -   **Diagnóstico:** Tras añadir logs de depuración, se descubrió el problema raíz: la librería `dateparser`, a pesar de la configuración, devolvía un objeto de fecha "ingenuo" (sin `tzinfo`). Al intentar convertir esta fecha ingenua a UTC, Python asumía incorrectamente la zona horaria del servidor (ej: `Europe/Madrid`) en lugar de la del usuario (ej: `Australia/Brisbane`), causando un cálculo de offset erróneo.
    -   **Solución:** Se implementó un "parche de seguridad" en `utils.py`. Justo después de recibir la fecha de `dateparser`, el código ahora comprueba si es ingenua. Si lo es, se le "fuerza" explícitamente la zona horaria correcta del usuario (`tz.localize(fecha_naive)`) antes de proceder con cualquier conversión a UTC. Esto garantiza que la conversión siempre parta de la base correcta.
-   **_E002_**
    -   **Problema:** Mensajes de confirmación poco claros o inconsistentes.
    -   **Solución:** Se han pulido y añadido numerosos textos al archivo `personalidad.py` para que todos los mensajes (especialmente las confirmaciones de configuración) sean claros y mantengan el tono del personaje.
-   **_E001_**
    - **Problema:** El teclado de `ReplyKeyboard` para la ubicación podía quedarse "pegado".
    -   **Solución:** Se ha reestructurado el flujo para usar menús de botones `Inline` y se ha mejorado la función `manejar_cancelacion` (antigua cancelar_conversacion) para que limpie el teclado explícitamente.


## [v1.3-personality] - 2025-08-20

### ✨ Mejoras
-   **Personalidad:** Se ha creado un archivo `personalidad.py` para centralizar todos los textos del bot, dándole la voz y el carácter de Augusta Longbottom.
-   **Flujo de comandos mejorado:** Se han refactorizado todos los handlers para usar los nuevos textos de personalidad, haciendo las interacciones más dinámicas y carismáticas.
-   **Bienvenida contextual:** El comando `/start` ahora diferencia entre usuarios nuevos y recurrentes, mostrando un mensaje de bienvenida detallado la primera vez.
-   **UX de `/recordar` refinada:** El bot ahora confirma que el recordatorio ha sido guardado *antes* de preguntar por el aviso previo, mejorando la sensación de seguridad del usuario.
-   **Código DRY (dont repeat yourself):** La función de cancelar conversaciones (`cancelar_conversacion`) se ha centralizado en `utils.py` para ser reutilizada por todos los handlers.



## [v1.2-render-multiuser] - 2025-08-20

### ✨ Mejoras
-   **¡Funcionalidad Multi-Usuario Completa!** El bot ahora puede ser usado por múltiples usuarios de forma simultánea, con sus datos completamente aislados y privados.
-   **IDs secuenciales por usuario:** Se reemplazó el sistema de IDs global (`AG01`) por uno secuencial por usuario (`#1`, `#2`...). Esto es más seguro, intuitivo y evita colisiones de datos.
-   **Configuración aislada:** El "Modo Seguro" ahora es una configuración individual para cada usuario.
-   **Protección de comandos de admin:** El comando `/reset` ahora solo puede ser ejecutado por el `OWNER_ID` definido en la configuración.
-   **Flujo de comandos mejorado:** Los comandos `/borrar` y `/cambiar` ahora aceptan IDs directamente como argumentos (ej: `/borrar #1`) para una interacción más rápida.

### 🐛 Problemas resueltos 
-   **Problema:** Inconsistencia en el flujo de los comandos `/borrar` y `/cambiar` al llamarse con argumentos.
    -   **Síntoma:** `TypeError: function() takes 2 positional arguments but 3 were given`.
    -   **Solución:** Se refactorizaron los handlers para tener una función de procesamiento central (`_procesar_ids`) que unifica la lógica del modo seguro, garantizando un flujo de datos consistente.



## [v1.1-render] - 2025-08-18

### ✨ Mejoras
-   **¡Despliegue en la nube!** El bot fue desplegado exitosamente en la plataforma **Render**.
-   **Arquitectura híbrida:** Se implementó una solución con **Flask** en un hilo secundario para pasar los chequeos de salud del "Web Service" gratuito de Render.
-   **Servicio 24/7:** Se configuró un monitor de actividad externo (Uptime Robot) para visitar la URL del bot cada 5 minutos, evitando que el servicio se "duerma" por inactividad.

### 🐛 Problemas resueltos
-   **Problema:** El despliegue fallaba buscando un `Dockerfile`.
    -   **Solución:** Se cambió el **`Runtime`** del servicio en Render de `Docker` a `Python 3`.
-   **Problema:** El `build` fallaba por dependencias incompatibles.
    -   **Solución:** Se reemplazó el `requirements.txt` generado por `pip freeze` por uno minimalista con solo las librerías esenciales.
-   **Problema:** El bot crasheaba al inicio por un error de `locale`.
    -   **Solución:** Se envolvió la llamada `locale.setlocale()` en un bloque `try...except` para que el programa pudiera continuar si el `locale` español no estaba disponible.
-   **Problema:** El bot crasheaba por un error de `weak reference` de `python-telegram-bot`.
    -   **Solución:** Se fijó una versión de Python estable (`3.12.4`) mediante la variable de entorno `PYTHON_VERSION` en Render.
-   **Problema:** Render detenía el bot por no encontrar un puerto abierto.
    -   **Solución:** Se cambió el tipo de servicio a **`Web Service`** y se añadió Flask para abrir un puerto y pasar el chequeo de salud. *(Nota: La solución inicial de usar un "Background Worker" se descartó al descubrir que no estaba en el plan gratuito).*



## [v1.0-local] - ...

### ✨ Mejoras
-   **Versión inicial funcional:** Creación del bot con la lógica principal de recordatorios.
-   **Planificador de avisos:** Implementación de `APScheduler` para gestionar y enviar avisos programados de forma persistente.

### 🐛 Problemas resueltos (bugs)
-   **Problema:** Los avisos de `APScheduler` no podían enviar mensajes.
    -   **Solución:** Se pasó el objeto `app` de `python-telegram-bot` al scheduler para darle contexto y capacidad de envío.
-   **Problema:** El bot no arrancaba por un `RuntimeError: no running event loop`.
    -   **Solución:** Se usó `post_init` en el `ApplicationBuilder` para iniciar el scheduler en el momento correcto del ciclo de vida de la aplicación.


---


## 🏛️ Decisiones de Arquitectura y Diseño

Esta sección documenta algunas de las decisiones de diseño clave tomadas durante el desarrollo del proyecto.

-   **_D001 - Estrategia para mantener activo el servicio en Render_**
    -   **Dilema:** El plan gratuito "Web Service" de Render detiene los servicios tras 15 minutos de inactividad HTTP. Para un bot de `polling` que necesita estar activo 24/7 para enviar avisos programados, esto es inaceptable. Se evaluaron dos estrategias para generar actividad constante: un "auto-ping" interno dentro del propio bot o el uso de un monitor externo.
    -   **Decisión:** Se optó por la solución del **monitor externo (UptimeRobot)**.
    -   **Justificación:** Aunque la solución de "auto-ping" es atractiva por ser autocontenida, tiene un fallo fundamental: elimina la capacidad de saber si el servicio se ha caído por un error interno. Si el bot crashea, el ping también muere, dejando al desarrollador a ciegas. La dependencia de un servicio externo es un pequeño precio a pagar por el inmenso beneficio de tener un sistema de monitorización y alerta imparcial. Esto asegura no solo que el bot se mantenga despierto, sino que también nos notificará si deja de funcionar por cualquier otro motivo, lo cual es crucial para la fiabilidad del servicio.

-   **_D002 - Uso de `psycopg2` vs. `supabase-py`_**
    -   **Decisión:** Se optó por utilizar una conexión directa a la base de datos PostgreSQL con la librería estándar `psycopg2` en lugar del cliente oficial de Supabase (`supabase-py`).
    -   **Justificación:**
        1.  **Compatibilidad de Herramientas:** La librería `APScheduler`, crucial para los avisos, requiere una cadena de conexión de base de datos estándar (DSN/URI) para su `SQLAlchemyJobStore`. El cliente de Supabase no proporciona esta interfaz, lo que lo hace incompatible.
        2.  **Modelo de Backend de Confianza:** El bot opera como un servicio de backend único y de confianza. No necesita la capa de abstracción y seguridad (RLS) que el cliente de Supabase está diseñado para proporcionar a clientes no seguros (como un navegador web). Una conexión directa es más eficiente para este caso de uso.
        3.  **Menor Refactorización:** La lógica de la aplicación ya estaba escrita en SQL. Migrar de un dialecto SQL (SQLite) a otro (PostgreSQL) fue significativamente más sencillo que reescribir toda la la capa de datos para usar una API programática (`.select()`, `.insert()`, etc.).

-   **_D003 - Desactivación de la Seguridad a Nivel de Fila (RLS)_**
    -   **Decisión:** Se ha desactivado explícitamente la política de RLS en las tablas `recordatorios` y `configuracion` en Supabase.
    -   **Justificación:** La seguridad y el aislamiento de los datos de los usuarios no se delegan a la base de datos, sino que **son gestionados por la lógica de la aplicación del bot**. El bot es la única entidad que tiene acceso a la base de datos, y cada consulta que realiza está diseñada para incluir siempre una cláusula `WHERE chat_id = %s`, asegurando que un usuario solo pueda ver y modificar sus propios datos. Este modelo de "backend de confianza" es estándar y seguro, siempre que la cadena de conexión a la base de datos se mantenga secreta. RLS está diseñado para un modelo de seguridad diferente, donde clientes no seguros podrían acceder a la API de la base de datos directamente.