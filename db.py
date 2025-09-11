# db.py
"""
Módulo de Acceso a la Base de Datos (Capa de Datos).

Este archivo contiene toda la lógica para interactuar con la base de datos SQLite.
Se encarga de la creación de tablas, y de todas las operaciones de lectura y
escritura (CRUD) para los recordatorios y las configuraciones de usuario.
"""

import sqlite3
from typing import Tuple, List, Optional
from datetime import datetime
import pytz

# --- CONSTANTES Y CONEXIÓN ---
DB_PATH = "la_recordadora.db"

def get_connection() -> sqlite3.Connection:
    """
    Establece y devuelve una conexión a la base de datos SQLite.
    `check_same_thread=False` es necesario porque el bot se ejecuta en un hilo
    diferente al del servidor web (Flask) en el despliegue de Render.
    """
    return sqlite3.connect(DB_PATH, check_same_thread=False)


# =============================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# =============================================================================

def crear_tablas():
    """

    Crea las tablas 'recordatorios' y 'configuracion' si no existen.
    Esta función es idempotente y segura de ejecutar en cada inicio del bot.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # Tabla para almacenar los recordatorios de todos los usuarios.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,      -- ID único global para cada recordatorio
                user_id INTEGER NOT NULL,                  -- ID secuencial por usuario (ej: #1, #2)
                chat_id INTEGER NOT NULL,                  -- ID del chat donde se creó
                texto TEXT,
                fecha_hora TEXT,                           -- Fecha y hora en formato ISO y zona horaria UTC
                estado INTEGER DEFAULT 0,                  -- 0: Pendiente, 1: Hecho
                aviso_previo INTEGER,                      -- Minutos de antelación para el aviso
                timezone TEXT                              -- Zona horaria original con la que se creó
            )
        """)

        # Tabla para almacenar configuraciones clave-valor por usuario.
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                chat_id INTEGER NOT NULL,
                clave TEXT NOT NULL,
                valor TEXT,
                PRIMARY KEY (chat_id, clave)
            )
        """)
        
        conn.commit()


# =============================================================================
# FUNCIONES DE CONFIGURACIÓN (CLAVE-VALOR)
# =============================================================================

def get_config(chat_id: int, key: str) -> Optional[str]:
    """Obtiene el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE chat_id = ? AND clave = ?", (chat_id, key))
        row = cursor.fetchone()
        return row[0] if row else None

def set_config(chat_id: int, key: str, value: str):
    """Establece o actualiza el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO configuracion (chat_id, clave, valor) VALUES (?, ?, ?)", (chat_id, key, value))
        conn.commit()


# =============================================================================
# FUNCIONES DE GESTIÓN DE RECORDATORIOS
# =============================================================================

def get_recordatorios(chat_id: int, filtro: str = "futuro", page: int = 1, items_per_page: int = 7) -> Tuple[List, int]:
    """
    Función universal para obtener recordatorios con filtros y paginación.
    """
    now_utc = datetime.now(pytz.utc)

    with get_connection() as conn:
        cursor = conn.cursor()
        query_base = "FROM recordatorios WHERE chat_id = ?"
        params = [chat_id]

        if filtro == "futuro":
            query_base += " AND (fecha_hora IS NULL OR fecha_hora > ?)"
            params.append(now_utc.isoformat())
        elif filtro == "pasado":
            query_base += " AND fecha_hora IS NOT NULL AND fecha_hora <= ?"
            params.append(now_utc.isoformat())
        elif filtro == "hoy":
            # Se calcula el inicio y fin del día en la TZ del usuario para precisión.
            user_tz_str = get_config(chat_id, "user_timezone") or "UTC"
            user_tz = pytz.timezone(user_tz_str)
            now_local = now_utc.astimezone(user_tz)
            
            start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Se convierten los límites a UTC para la consulta en la base de datos.
            start_of_day_utc = start_of_day_local.astimezone(pytz.utc)
            end_of_day_utc = end_of_day_local.astimezone(pytz.utc)
            
            query_base += " AND estado = 0 AND fecha_hora >= ? AND fecha_hora <= ?"
            params.extend([start_of_day_utc.isoformat(), end_of_day_utc.isoformat()])

        cursor.execute(f"SELECT COUNT(id) {query_base}", tuple(params))
        total_items = cursor.fetchone()[0]

        if total_items == 0:
            return [], 0

        offset = (page - 1) * items_per_page
        query_select = "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone"
        query_order = "ORDER BY fecha_hora ASC"
        
        cursor.execute(f"{query_select} {query_base} {query_order} LIMIT ? OFFSET ?", tuple(params + [items_per_page, offset]))
        recordatorios_pagina = cursor.fetchall()

        return recordatorios_pagina, total_items

def get_todos_los_chat_ids() -> List[int]:
    """Obtiene una lista de todos los chat_id únicos de los usuarios del bot."""
    with get_connection() as conn:
        cursor = conn.cursor()
        # UNION es más eficiente que dos consultas separadas para obtener IDs únicos.
        cursor.execute("SELECT DISTINCT chat_id FROM recordatorios UNION SELECT DISTINCT chat_id FROM configuracion")
        return [item[0] for item in cursor.fetchall()]

def borrar_recordatorios_pasados(chat_id: int) -> tuple[int, List[int]]:
    """
    Elimina los recordatorios pasados de un usuario basándose en la hora UTC.
    
    Returns:
        tuple: (Número de recordatorios borrados, Lista de IDs de los recordatorios borrados).
    """
    now_utc_iso = datetime.now(pytz.utc).isoformat()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM recordatorios WHERE chat_id = ? AND fecha_hora IS NOT NULL AND fecha_hora <= ?",
            (chat_id, now_utc_iso)
        )
        ids_a_borrar = [item[0] for item in cursor.fetchall()]

        if not ids_a_borrar:
            return 0, []

        placeholders = ','.join(['?'] * len(ids_a_borrar))
        cursor.execute(f"DELETE FROM recordatorios WHERE id IN ({placeholders})", tuple(ids_a_borrar))
        num_borrados = cursor.rowcount
        conn.commit()

    return num_borrados, ids_a_borrar

def resetear_base_de_datos():
    """
    Función de administrador. ¡PELIGRO! Elimina TODOS los recordatorios de TODOS los usuarios.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada por completo.")