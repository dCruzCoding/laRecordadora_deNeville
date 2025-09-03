# Changelog de La Recordadora 👵

Este documento registra los cambios significativos, decisiones de diseño y problemas resueltos a lo largo del desarrollo y despliegue del bot.

---
## [v1.5-edit-and-stability] - *En desarrollo*

### ✨ Mejoras
-   **Nueva funcionalidad -> Comando `/editar`:** ¡Se ha añadido una nueva funcionalidad principal! Los usuarios ahora pueden modificar sus recordatorios existentes a través de un nuevo comando `/editar`.
    -   El comando inicia una conversación guiada que permite elegir un recordatorio por su ID.
    -   Ofrece un menú con botones para seleccionar si se quiere modificar el **contenido** (fecha/texto) o el **aviso previo**.
    -   Cada flujo de edición es conversacional y está integrado con la personalidad del bot.
-   **Gestión de Interrupciones de Comandos (Bug Crítico Solucionado):** Se ha refactorizado la gestión de las conversaciones para solucionar un problema fundamental de la experiencia de usuario.
-   **Sistema de Estados Rediseñado:** Se ha refactorizado por completo la lógica de los estados de los recordatorios para que sea más intuitiva y potente.
    -   El **estado de finalización** (`Pendiente`/`Hecho`) ahora es independiente del **estado temporal**.
    -   El estado **"Pasado"** ya no se guarda en la base de datos, sino que se **calcula dinámicamente** al mostrar las listas si un recordatorio `Pendiente` tiene una fecha expirada.
-   **Visualización de Listas Mejorada:** La presentación de los recordatorios se ha modernizado para una mayor claridad (`⬜️` para Pendiente, `✅` para Hecho).

### 🐛 Problemas Resueltos

-   **_E005_**
    -   **Problema:** Si un usuario escribía un comando (ej: `/lista`) mientras estaba en medio de otra conversación (ej: `/ajustes`), el bot se comportaba de forma errática: a veces el comando se ejecutaba, otras veces era bloqueado por un mensaje de `fallback`, creando una experiencia inconsistente.
    -   **Solución:** Se ha implementado un mecanismo de protección utilizando los `fallbacks` de cada `ConversationHandler`. En muchos casos, si se detecta un comando inesperado, el bot informa al usuario de que está en mitad de un proceso y le instruye para que use `/cancelar` antes de continuar.
    - **_📝 Notas de Desarrollo y Guía de Comportamientos Conocidos_**:
        -   **Decisión Técnica:** Inicialmente se intentó forzar un comportamiento uniforme utilizando los **grupos de prioridad** de la librería `python-telegram-bot`. Sin embargo, se encontraron incompatibilidades o comportamientos inesperados con la versión utilizada. En lugar de explorar la compatibilidad entre versiones, se optó por la solución actual basada en `fallbacks` por ser más simple y estable.
        -   **Causa Raíz:** La inconsistencia se debe a que los **puntos de entrada (`entry_point`) de un nuevo comando conversacional (ej: `/borrar`) tienen prioridad sobre el `fallback` genérico de una conversación ya activa (ej: `/editar`)**.
        -   Se ha decidido aceptar este comportamiento como una **limitación conocida y documentada**. A continuación se explica cómo actuar en cada caso:

        #### ❓ **¿Qué pasa si interrumpo una conversación? Guía Rápida:**

        *   **Caso A: El bot te bloquea con un mensaje ("¡Quieto ahí!")**
            *   **Cuándo ocurre:** Generalmente, cuando estás en una conversación que espera texto (como `/recordar`) e intentas usar un comando simple (como `/lista`).
            *   **Qué hacer:** El bot ha protegido tu progreso. Sigue las instrucciones: o continúas con la conversación actual, o usas `/cancelar` para empezar de nuevo.

        *   **Caso B: El bot te deja abrir otra conversación (Ej: `/editar` y luego `/borrar`)**
            *   **Cuándo ocurre:** Cuando estás en una conversación que espera texto (ej: `/editar`) e inicias *otra* conversación que también espera texto (ej: `/borrar`).
            *   **Comportamiento:** La segunda conversación (`/borrar`) se pone "encima" de la primera. **La conversación que manda es la última que abriste**.
            *   **Qué hacer:** Termina el flujo de la segunda conversación (`/borrar`). Una vez finalizada, el bot volverá automáticamente al punto exacto donde dejaste la primera (`/editar`), permitiéndote continuar.

        *   **Caso C: Estás en una conversación de botones (Ej: `/ajustes`) y abres otra cosa**
            *   **Cuándo ocurre:** Cuando el bot te muestra botones (como en `/ajustes`) y tú escribes un comando (como `/recordar` o `/lista`).
            *   **Comportamiento:** El nuevo comando se ejecutará, abriendo su propia conversación o mostrándote su información. La conversación de `/ajustes` quedará "pausada" en segundo plano. El "foco" lo tiene la última acción que realizaste.
            *   **Qué hacer:** Tienes control total para cambiar el foco. Puedes terminar la nueva conversación que abriste, o puedes volver a la conversación de `/ajustes` simplemente **pulsando uno de sus botones originales** que aún estén visibles en el chat.








## [v1.4-global-support] - 2025-08-22

### ✨ Mejoras
-   **Soporte Global de Zona Horaria:** ¡El bot ahora es consciente de la zona horaria de cada usuario! Se ha añadido un flujo para configurar la zona horaria de forma automática (con ubicación) o manual (escribiendo una ciudad).
-   **Flujo de Onboarding Guiado:** Se ha mejorado la conversación de bienvenida (`/start`) para los nuevos usuarios. El bot se presenta, explica su función y guía al usuario a través de la configuración inicial (modo seguro y zona horaria). 
-   **Comando `/info`:** Se añade comando `/info` que permite revisar el contenido sobre cómo usar el bot que venía en el mensaje de inicio.
-   **Comando `/ajustes` Unificado:** Se ha fusionado el comando `/timezone` dentro de `/configuracion` y todo se ha renombrado a un único y elegante comando `/ajustes`.
-   **Interfaz de Botones Completa:** Todo el flujo de `/ajustes` ahora es 100% interactivo, usando botones `Inline` para una experiencia de usuario fluida y sin errores.
-   **Robustez de las Conversaciones:** Se ha mejorado la cancelación para que elimine los teclados de respuesta y se han pulido los flujos de diálogo para guiar mejor al usuario.
-   **Lógica de Reactivación Inteligente:** Al reactivar un recordatorio (`Hecho` -> `Pendiente`), el bot ahora comprueba si su fecha ya ha pasado para evitar ofrecer la reprogramación de avisos sin sentido.
- **Corrección de sincronización timezone e inclusion de _smart_ timezone:** Se soluciona el error E001, y además se incluye una nueva funcionalidad para que, al cambiar la zona horaria, se puedan pasar los recordatorios que tenías registrados a ese nuevo uso horario.


### 🐛 Problemas Resueltos (Bugs)
-   **_E001_**
    - **Problema:** El teclado de `ReplyKeyboard` para la ubicación podía quedarse "pegado".
    -   **Solución:** Se ha reestructurado el flujo para usar menús de botones `Inline` y se ha mejorado la función `manejar_cancelacion` (antigua cancelar_conversacion) para que limpie el teclado explícitamente.
-   **_E002_**
    -   **Problema:** Mensajes de confirmación poco claros o inconsistentes.
    -   **Solución:** Se han pulido y añadido numerosos textos al archivo `personalidad.py` para que todos los mensajes (especialmente las confirmaciones de configuración) sean claros y mantengan el tono del personaje.
-   **_E003_**
    -   **Problema:** La conversión de zonas horarias fallaba, mostrando horas incorrectas (ej: 10:55 en lugar de 02:55).
    -   **Diagnóstico:** Tras añadir logs de depuración, se descubrió el problema raíz: la librería `dateparser`, a pesar de la configuración, devolvía un objeto de fecha "ingenuo" (sin `tzinfo`). Al intentar convertir esta fecha ingenua a UTC, Python asumía incorrectamente la zona horaria del servidor (ej: `Europe/Madrid`) en lugar de la del usuario (ej: `Australia/Brisbane`), causando un cálculo de offset erróneo.
    -   **Solución:** Se implementó un "parche de seguridad" en `utils.py`. Justo después de recibir la fecha de `dateparser`, el código ahora comprueba si es ingenua. Si lo es, se le "fuerza" explícitamente la zona horaria correcta del usuario (`tz.localize(fecha_naive)`) antes de proceder con cualquier conversión a UTC. Esto garantiza que la conversión siempre parta de la base correcta.
-   **_E004_**  
    -   **Problema:** La detección de zona horaria manual a veces falla, mostrando un mensaje de "timezone_reintentar".
    -   **Diagnóstico:** Se identificó que la librería `geopy` puede fallar por timeouts de red, especialmente en el entorno de Render.
    -   **Solución:** Se ha añadido un `timeout=10` explícito a la llamada de `geopy`. Esto hace al bot más resiliente a la congestión de red, aumentando la probabilidad de éxito sin impactar negativamente en el tiempo de respuesta en condiciones normales. Además, se han añadido interacciones con el usuario en esta parte para mejorar su acompañamiento.


## [v1.3-personality] - 2025-08-20

### ✨ Mejoras
-   **Personalidad de la Abuela:** Se ha creado un archivo `personalidad.py` para centralizar todos los textos del bot, dándole la voz de Augusta Longbottom.
-   **Flujo de Comandos Mejorado:** Se han refactorizado todos los handlers para usar los nuevos textos de personalidad, haciendo las interacciones más dinámicas y carismáticas.
-   **Bienvenida Contextual:** El comando `/start` ahora diferencia entre usuarios nuevos y recurrentes, mostrando un mensaje de bienvenida detallado la primera vez.
-   **UX de `/recordar` Refinada:** El bot ahora confirma que el recordatorio ha sido guardado *antes* de preguntar por el aviso previo, mejorando la sensación de seguridad del usuario.
-   **Código DRY:** La función de cancelar conversaciones (`cancelar_conversacion`) se ha centralizado en `utils.py` para ser reutilizada por todos los handlers.

---

## [v1.2-render-multiuser] - 2025-08-20

### ✨ Mejoras
-   **¡Funcionalidad Multi-Usuario Completa!** El bot ahora puede ser usado por múltiples usuarios de forma simultánea, con sus datos completamente aislados y privados.
-   **IDs Secuenciales por Usuario:** Se reemplazó el sistema de IDs global (`AG01`) por uno secuencial por usuario (`#1`, `#2`...). Esto es más seguro, intuitivo y evita colisiones de datos.
-   **Configuración Aislada:** El "Modo Seguro" ahora es una configuración individual para cada usuario.
-   **Protección de Comandos de Admin:** El comando `/reset` ahora solo puede ser ejecutado por el `OWNER_ID` definido en la configuración.
-   **Flujo de Comandos Mejorado:** Los comandos `/borrar` y `/cambiar` ahora aceptan IDs directamente como argumentos (ej: `/borrar #1`) para una interacción más rápida.

### 🐛 Problemas Resueltos (Bugs)
-   **Problema:** Inconsistencia en el flujo de los comandos `/borrar` y `/cambiar` al llamarse con argumentos.
    -   **Síntoma:** `TypeError: function() takes 2 positional arguments but 3 were given`.
    -   **Solución:** Se refactorizaron los handlers para tener una función de procesamiento central (`_procesar_ids`) que unifica la lógica del modo seguro, garantizando un flujo de datos consistente.

---

## [v1.1-render] - 2025-08-18

### ✨ Mejoras
-   **¡Despliegue en la Nube!** El bot fue desplegado exitosamente en la plataforma **Render**.
-   **Arquitectura Híbrida:** Se implementó una solución con **Flask** en un hilo secundario para pasar los chequeos de salud del "Web Service" gratuito de Render.
-   **Servicio 24/7:** Se configuró un monitor de actividad externo (Uptime Robot) para visitar la URL del bot cada 5 minutos, evitando que el servicio se "duerma" por inactividad.

### 🐛 Problemas Resueltos (Despliegue)
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

---

## [v1.0-local] - (Fecha de Desarrollo Inicial)

### ✨ Mejoras
-   **Versión Inicial Funcional:** Creación del bot con la lógica principal de recordatorios.
-   **Planificador de Avisos:** Implementación de `APScheduler` para gestionar y enviar avisos programados de forma persistente.

### 🐛 Problemas Resueltos (Desarrollo)
-   **Problema:** Los avisos de `APScheduler` no podían enviar mensajes.
    -   **Solución:** Se pasó el objeto `app` de `python-telegram-bot` al scheduler para darle contexto y capacidad de envío.
-   **Problema:** El bot no arrancaba por un `RuntimeError: no running event loop`.
    -   **Solución:** Se usó `post_init` en el `ApplicationBuilder` para iniciar el scheduler en el momento correcto del ciclo de vida de la aplicación.


---


## 🏛️ Decisiones de Arquitectura

Esta sección documenta algunas de las decisiones de diseño clave tomadas durante el desarrollo del proyecto.

### ¿UptimeRobot (Externo) o Auto-Ping (Interno) para Mantener Activo el Servicio de Render?

#### El Dilema
El plan gratuito "Web Service" de Render detiene (hace "spin down") los servicios tras 15 minutos de inactividad de tráfico HTTP externo. Para un bot de `polling` como "La Recordadora", que necesita estar activo 24/7 para enviar avisos programados, esto es inaceptable. Se plantearon dos alternativas para generar actividad constante:

1.  **Auto-Ping Interno:** Añadir una nueva tarea (`APScheduler` o `threading`) dentro del propio bot que hiciera una petición HTTP a su propia URL pública cada X minutos.
2.  **Monitor Externo:** Utilizar un servicio de terceros gratuito (como Uptime Robot) para que visite la URL del bot a intervalos regulares.

#### Análisis y Decisión

| Criterio | Auto-Ping Interno | Monitor Externo (Uptime Robot) |
| :--- | :--- | :--- |
| **Simplicidad de Despliegue** | ✅ **Alta** (autocontenido) | ❌ **Media** (requiere configurar un segundo servicio) |
| **Robustez y Alertas**| ❌ **Baja** (si el bot se cae, el ping también. No hay alertas) | ✅ **Alta** (monitoriza caídas reales y envía notificaciones) |
| **Separación de Responsabilidades** | ❌ **Baja** (mezcla lógica de bot y de infraestructura) | ✅ **Alta** (el bot es el bot, el monitor es el monitor) |
| **Consumo de Recursos** | Mínimo, pero consume ciclos de CPU del propio bot. | Cero consumo de recursos del bot. |

#### Respuesta
Se decidió optar por la solución del **Monitor Externo (Uptime Robot)**.

Aunque la solución de "auto-ping" es atractiva por ser autocontenida, tiene un fallo fundamental: **elimina la capacidad de saber si el servicio se ha caído por un error interno.** Si el bot crashea, el ping también muere, dejando al desarrollador a ciegas.

La dependencia de un servicio externo como Uptime Robot es un pequeño precio a pagar por el inmenso beneficio de tener un sistema de monitorización y alerta imparcial. Esto asegura no solo que el bot se mantenga despierto, sino que también nos notificará si deja de funcionar por cualquier otro motivo, lo cual es crucial para la fiabilidad del servicio.