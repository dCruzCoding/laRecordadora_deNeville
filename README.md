
# 🤖🧠 Bot de Telegram: *La Recordadora*

> Inspirado en la entrañable esfera mágica de Neville Longbottom, *La Recordadora* es un asistente de memoria con alma de abuela cariñosa y regañona. Su misión es ayudarte a no olvidar aquello que dijiste que harías... aunque a veces se te pase.

---

## 🎯 Objetivo del proyecto

Diseñar un bot conversacional en Telegram que actúe como asistente de memoria personal, ayudando al usuario a recordar tareas, hábitos o eventos que ha registrado previamente. A diferencia de otros bots de productividad, *La Recordadora* incorpora una personalidad propia, entrañable y ligeramente regañona, para fomentar el cumplimiento con un tono humorístico y familiar.

**Usuarios objetivo:** Personas olvidadizas, estudiantes, trabajadores multitarea o cualquier persona que quiera recordar tareas con un poco de humor.

---

## 🔧 Funcionalidades principales

### 1. Inicio y configuración

* `/start`: bienvenida y explicación del funcionamiento del bot.
* Configuración opcional del tono de la Recordadora: `dulce` / `sarcástica`.

### 2. Registro de recordatorios

* `/recordar`: añadir recordatorio con o sin fecha/hora.

  * Soporte para lenguaje natural, por ejemplo:

    * “Recuérdame llamar a mi madre mañana a las 6.”
    * “Tengo que estudiar para el examen del viernes.”
* Posibilidad de categorizarlos: `tarea`, `hábito`, `cita`.

### 3. Gestión de recordatorios

* `/lista`: ver recordatorios activos.
* `/hecho`: marcar como completados.
* `/borrar`: eliminar un recordatorio.
* `/ayuda`: resumen de comandos y funcionalidades.

### 4. Seguimiento automático

* Envío de recordatorios programados.
* Detección de tareas no cumplidas y respuesta con frases como:

  * “Ay, criatura, ¿otra vez se te ha olvidado?”
  * “Mira que te lo dije, ¿eh?”

### 5. Extras opcionales (Fase 2)

* Estadísticas: cuántas veces se repite una tarea sin hacer.
* Integración con Google Calendar.
* Interfaz web de gestión (dashboard ligero).

---

## 🔁 Flujo de uso del bot

A continuación, se presenta un diagrama del flujo básico de interacción:

```
[Usuario inicia bot con /start]
         ↓
[Bot da la bienvenida y pide tareas a recordar]
         ↓
[Usuario escribe: "Recuérdame beber agua cada día a las 12"]
         ↓
[Bot guarda el recordatorio y lo programa]
         ↓
[Hora del recordatorio → Bot envía mensaje]
         ↓
[Usuario responde con /hecho o ignora]
         ↓
[Si ignora → Bot reenvía recordatorio con tono de abuela]
```

---

## 🛠️ Tecnologías y herramientas

### Lenguaje

* **Python** (sencillo, mantenible y con buena documentación)

### Librerías

* `python-telegram-bot`: para la gestión del bot.
* `apscheduler`: para la programación de tareas.
* `dateparser` o `parsedatetime`: para entender lenguaje natural con fechas y horas.

### Almacenamiento

* **SQLite** para desarrollo local.
* **Firestore (GCP)** para almacenamiento persistente y despliegue cloud.

### Despliegue

* Desarrollo local y pruebas en PC.
* Despliegue final en **Google Cloud Run** o **Cloud Functions** (con Scheduler si se requiere ejecución periódica).

---

## 🗺️ Hoja de ruta (Roadmap)

### 🟢 Fase 1: Mínimo Producto Viable (MVP)

* [ ] Crear el bot con BotFather y obtener token.
* [ ] Configurar entorno local (Python + librerías).
* [ ] Implementar `/start`, `/recordar`, `/lista`, `/hecho`, `/borrar`.
* [ ] Añadir almacenamiento local (SQLite).
* [ ] Programar notificaciones con `apscheduler`.

### 🟡 Fase 2: Persistencia y despliegue cloud

* [ ] Migrar almacenamiento a Firestore.
* [ ] Desplegar en Google Cloud Functions/Run.
* [ ] Configurar programación con Cloud Scheduler.

### 🔵 Fase 3: Mejora UX y personalidad

* [ ] Añadir frases personalizadas y modo "abuela regañona".
* [ ] Permitir configuración de tono (sarcástico vs dulce).
* [ ] Añadir estadísticas de cumplimiento.
* [ ] Validación de lenguaje natural con `dateparser`.

### 🔴 Fase 4: Extras opcionales

* [ ] Categorías de recordatorios.
* [ ] Integración con Google Calendar.
* [ ] Interfaz web ligera.

---

## 🛡️ Consideraciones adicionales

* Manejo de errores (fechas inválidas, comandos mal escritos, etc.).
* Protección de datos del usuario.
* Escalabilidad (si decides abrirlo a más personas).

---

## ⚠️ Importante

Este bot no pretende ser un sistema de gestión de tareas completo, sino un asistente simpático para el día a día. Las decisiones técnicas están orientadas a facilitar el desarrollo y despliegue personal, sin comprometer seguridad ni escalabilidad en producción masiva.


