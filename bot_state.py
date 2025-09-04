# bot_state.py
"""
Módulo de Estado Global de la Aplicación.

Este archivo resuelve un problema de importaciones circulares. Su único propósito
es mantener una referencia global a la instancia de la aplicación de
`python-telegram-bot` (`Application`) una vez que esta ha sido creada en `main.py`.

El problema original:
- `avisos.py` necesita poder enviar mensajes, por lo que necesita acceso a la app.
- Módulos de `handlers` (como `resumen_diario.py`) necesitan importar funciones de `avisos.py`.
- `avisos.py` no puede importar handlers directamente porque los handlers ya lo
  importan a él, creando un círculo.

La solución:
- `main.py` crea la `app` y la guarda en la variable `telegram_app` de este módulo.
- Cualquier otro módulo que necesite enviar un mensaje (como `avisos.py` o
  `resumen_diario.py`) importa esta variable `telegram_app` desde `bot_state.py`,
  un módulo neutral que no depende de nadie y del que todos pueden depender.
"""

from typing import Optional
from telegram.ext import Application

# --- Variable de Estado Global ---
# Esta variable contendrá la instancia de la aplicación del bot una vez que se inicie.
# Se inicializa a `None` y se le asigna el valor real en `avisos.iniciar_scheduler`,
# que es llamado por `main.py` justo después de crear la aplicación.
telegram_app: Optional[Application] = None