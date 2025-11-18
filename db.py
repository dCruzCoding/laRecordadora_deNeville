# db.py
"""
Módulo de Acceso a la Base de Datos (Capa de Datos).

Este archivo contiene toda la lógica para interactuar con la base de datos externa
alojada en Supabase (PostgreSQL).
"""

import psycopg2
from typing import Tuple, List, Optional
from datetime import datetime
import pytz

# Importaciones módulos locales
from config import SUPABASE_DB_URL


def get_connection(): 
    """
    Establece y devuelve una conexión a la base de datos PostgreSQL en Supabase.
    """
    # psycopg2 gestiona el 'threading' de forma diferente y más robusta.
    return psycopg2.connect(SUPABASE_DB_URL)


# =============================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# =============================================================================

def create_tables():
    """
    Crea las tablas 'reminders', 'configuration' y 'pinned_reminders' si no existen.
    """
    # Usamos 'with' para asegurar que la conexión y el cursor se cierren solos.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id BIGSERIAL PRIMARY KEY,                  -- ID único global
                    user_id INTEGER NOT NULL,
                    chat_id BIGINT NOT NULL,                   -- Usar BIGINT para chat_id por si acaso
                    text TEXT,
                    datetime TIMESTAMPTZ,                    -- TIMESTAMPTZ es el tipo ideal para UTC en Postgres
                    status INTEGER DEFAULT 0,
                    pre_alert INTEGER,
                    timezone TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuration (
                    chat_id BIGINT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT,
                    PRIMARY KEY (chat_id, key)
                )
            """)
            
            # --- TABLA PARA RECORDATORIOS FIJOS ---
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pinned_reminders (
                    id BIGSERIAL PRIMARY KEY,
                    chat_id BIGINT NOT NULL,
                    text TEXT NOT NULL,
                    local_time TIME NOT NULL,
                    timezone TEXT NOT NULL,
                    week_days TEXT NOT NULL DEFAULT 'mon,tue,wed,thu,fri,sat,sun' -- Por defecto, todos los días
                )
            """)


# =============================================================================
# FUNCIONES DE CONFIGURACIÓN (CLAVE-VALOR)
# =============================================================================

def get_config(chat_id: int, key: str) -> Optional[str]:
    """Obtiene el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM configuration WHERE chat_id = %s AND key = %s", (chat_id, key))
            row = cursor.fetchone()
            return row[0] if row else None

def set_config(chat_id: int, key: str, value: str):
    """Establece o actualiza el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: 'INSERT OR REPLACE' es de SQLite. El equivalente en PostgreSQL es 'INSERT ... ON CONFLICT'.
            sql = """
                INSERT INTO configuration (chat_id, key, value) VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, key) DO UPDATE SET value = EXCLUDED.value;
            """
            cursor.execute(sql, (chat_id, key, value))

# =============================================================================
# FUNCIONES DE GESTIÓN DE RECORDATORIOS
# =============================================================================

def get_reminders(chat_id: int, filter_type: str = "future", page: int = 1, items_per_page: int = 7) -> Tuple[List, int]:
    now_utc = datetime.now(pytz.utc)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            query_base = "FROM reminders WHERE chat_id = %s"
            params = [chat_id]

            # AÑADIMOS LOS FILTROS POR ESTADO
            if filter_type == "done":
                query_base += " AND status = 1"
                # No se añaden más parámetros
            elif filter_type == "pending":
                query_base += " AND status = 0"

            # AÑADIMOS LOS FILTROS TEMPORALES 
            if filter_type == "future":
                query_base += " AND (datetime IS NULL OR datetime > %s)"
                params.append(now_utc) # psycopg2 maneja objetos datetime directamente
            elif filter_type == "past":
                query_base += " AND datetime IS NOT NULL AND datetime <= %s"
                params.append(now_utc)
            elif filter_type == "today":
                user_tz_str = get_config(chat_id, "user_timezone") or "UTC"
                user_tz = pytz.timezone(user_tz_str)
                now_local = now_utc.astimezone(user_tz)
                
                start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

                start_of_day_utc = start_of_day_local.astimezone(pytz.utc)
                end_of_day_utc = end_of_day_local.astimezone(pytz.utc)
                
                query_base += " AND status = 0 AND datetime >= %s AND datetime <= %s"
                params.extend([start_of_day_utc, end_of_day_utc])

            cursor.execute(f"SELECT COUNT(id) {query_base}", tuple(params))
            total_items = cursor.fetchone()[0]

            if total_items == 0:
                return [], 0

            offset = (page - 1) * items_per_page
            query_select = "SELECT id, user_id, chat_id, text, datetime, status, pre_alert, timezone"
            query_order = "ORDER BY datetime ASC"

            # Si filtramos por estado, tiene más sentido ordenar por fecha de más reciente a más antiguo.
            if filter_type in ["done", "pending"]:
                query_order = "ORDER BY datetime DESC"
            
            cursor.execute(f"{query_select} {query_base} {query_order} LIMIT %s OFFSET %s", tuple(params + [items_per_page, offset]))
            reminders_page = cursor.fetchall()

            return reminders_page, total_items

def get_all_chat_ids() -> List[int]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT chat_id FROM reminders UNION SELECT DISTINCT chat_id FROM configuration")
            return [item[0] for item in cursor.fetchall()]

def delete_reminders_filtered(chat_id: int, filter_type: str) -> tuple[int, List[int]]:
    """
    Función universal para eliminar recordatorios de un usuario basándose en un filtro.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Construimos la consulta SQL dinámicamente según el filtro
            if filter_type == "past":
                sql_where = "WHERE chat_id = %s AND datetime IS NOT NULL AND datetime <= %s"
                params = (chat_id, datetime.now(pytz.utc))
            elif filter_type == "done":
                sql_where = "WHERE chat_id = %s AND status = 1"
                params = (chat_id,)
            else:
                # Si se pasa un filtro no válido, no hacemos nada.
                return 0, []

            # 1. Obtenemos los IDs de los recordatorios que vamos a borrar.
            cursor.execute(f"SELECT id FROM reminders {sql_where}", params)
            
            ids_to_delete = [item[0] for item in cursor.fetchall()]

            if not ids_to_delete:
                return 0, []

            # 2. Los borramos usando sus IDs.
            cursor.execute("DELETE FROM reminders WHERE id IN %s", (tuple(ids_to_delete),))
            num_deleted = cursor.rowcount

    return num_deleted, ids_to_delete

def reset_database():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Usamos TRUNCATE en ambas tablas para un borrado rápido y eficiente.
            # CASCADE es una salvaguarda por si en el futuro se añaden dependencias.
            cursor.execute("TRUNCATE TABLE reminders, pinned_reminders RESTART IDENTITY CASCADE")
    print("🧹 TODOS los recordatorios han sido eliminados por completo.")

# =============================================================================
# FUNCIONES DE GESTIÓN DE RECORDATORIOS FIJOS
# =============================================================================

def add_pinned_reminder(chat_id: int, text: str, local_time: str, timezone: str, week_days: str) -> int:
    """
    Añade un nuevo recordatorio fijo a la base de datos y devuelve su ID.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            sql = """
                INSERT INTO pinned_reminders (chat_id, text, local_time, timezone, week_days)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """
            cursor.execute(sql, (chat_id, text, local_time, timezone, week_days))
            new_id = cursor.fetchone()[0]
            return new_id
        
def get_next_pinned_reminders(chat_id: int) -> list:
    """
    Obtiene los recordatorios fijos de un usuario y calcula la próxima
    fecha de ocurrencia para cada uno.
    """
    from datetime import time, timedelta, datetime
    import pytz

    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT id, text, local_time, timezone, week_days FROM pinned_reminders WHERE chat_id = %s",
                (chat_id,)
            )
            pinned_raw = cursor.fetchall()

    next_pinned = []
    if not pinned_raw:
        return []

    user_tz_str = get_config(chat_id, "user_timezone") or "UTC"
    user_tz = pytz.timezone(user_tz_str)
    now_local = datetime.now(user_tz)

    # Mapeo de nombre de día a número (Lunes=0, Domingo=6)
    days_map = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}

    for pinned_id, text, local_time, timezone, week_days in pinned_raw:
        active_days = {days_map[day] for day in week_days.split(',')}
        fixed_time = time(local_time.hour, local_time.minute)   # Crea un objeto 'time' a partir de la hora guardada
        # Iteramos los próximos 7 días para encontrar la siguiente ocurrencia
        for i in range(8):
            day_to_check = now_local + timedelta(days=i)
            
            # Si el día de la semana está en los días activos...
            if day_to_check.weekday() in active_days:
                next_occurrence_local = day_to_check.replace(
                    hour=fixed_time.hour, minute=fixed_time.minute, second=0, microsecond=0
                )
                # ...y si esa fecha/hora es en el futuro, hemos encontrado la próxima ocurrencia
                if next_occurrence_local > now_local:
                    next_occurrence_utc = next_occurrence_local.astimezone(pytz.utc)
                    next_pinned.append(
                        (pinned_id, pinned_id, chat_id, text, next_occurrence_utc, 0, 0, timezone, True)
                    )
                    break # Salimos del bucle y vamos al siguiente recordatorio fijo
                    
    return next_pinned

def get_pinned_by_chat_id(chat_id: int) -> list:
    """Obtiene todos los recordatorios fijos de un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id, text, local_time, week_days FROM pinned_reminders WHERE chat_id = %s ORDER BY local_time ASC", (chat_id,))
            return cursor.fetchall()

def check_pinned_exists(pinned_id: int, chat_id: int) -> bool:
    """Verifica si un recordatorio fijo existe y pertenece al usuario especificado."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT id FROM pinned_reminders WHERE id = %s AND chat_id = %s", (pinned_id, chat_id))
            return cursor.fetchone() is not None
        
def update_pinned_by_id(pinned_id: int, new_text: str, new_time: str, new_days: str):
    """Actualiza el texto y la hora de un recordatorio fijo."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "UPDATE pinned_reminders SET text = %s, local_time = %s, week_days = %s WHERE id = %s",
                (new_text, new_time, new_days, pinned_id)
            )
def delete_pinned_by_id(pinned_id: int) -> int:
    """Borra un recordatorio fijo por su ID y devuelve el número de filas borradas."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM pinned_reminders WHERE id = %s", (pinned_id,))
            return cursor.rowcount