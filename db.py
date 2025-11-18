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
# FUNCIONES DE GESTIÓN DE RECORDATORIOS (CRUD)
# =============================================================================

# --- CREATE ---

def add_reminder(chat_id: int, text: str, date_iso: str | None, timezone: str) -> tuple[int, int]:
    """Añade un nuevo recordatorio y devuelve su ID global y de usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # RLS Ready
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            sql = """
                INSERT INTO reminders (user_id, chat_id, text, datetime, pre_alert, timezone) 
                VALUES ((SELECT COALESCE(MAX(user_id), 0) + 1 FROM reminders WHERE chat_id = %s), %s, %s, %s, 0, %s) 
                RETURNING id, user_id
            """
            cursor.execute(sql, (chat_id, chat_id, text, date_iso, timezone))
            global_id, user_id = cursor.fetchone()
            return global_id, user_id


# --- READ (GETTERS) ---   

def get_reminders(chat_id: int, filter_type: str = "future", page: int = 1, items_per_page: int = 7) -> Tuple[List, int]:
    now_utc = datetime.now(pytz.utc)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # RLS Ready
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
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

def get_reminder_for_editing(chat_id: int, user_id: int) -> tuple | None:
    """Obtiene la información de un recordatorio para el flujo de edición."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # RLS Ready
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute(
                "SELECT id, text, datetime, timezone, pre_alert FROM reminders WHERE user_id = %s AND chat_id = %s", 
                (user_id, chat_id)
            )
            return cursor.fetchone()

def get_reminder_by_global_id(global_id: int) -> tuple | None:
    """
    Obtiene info por ID global. No usa RLS context, la seguridad depende del handler.
    Usado por el handler de notificaciones que solo conoce el ID global.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT user_id, text, status, datetime, pre_alert, chat_id FROM reminders WHERE id = %s", (global_id,)
            )
            return cursor.fetchone()

def get_reminders_by_user_ids(chat_id: int, user_ids: tuple) -> list:
    """Obtiene información básica de recordatorios específicos por su user_id."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            query = "SELECT user_id, text, status FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (user_ids, chat_id))
            return cursor.fetchall()

def get_reminders_for_deletion(chat_id: int, user_ids: tuple) -> list:
    """Obtiene la información necesaria para mostrar la confirmación de borrado."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            query = "SELECT user_id, text, datetime FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query, (user_ids, chat_id))
            return cursor.fetchall()

def get_reminder_status_for_validation(chat_id: int, global_id: int) -> tuple | None:
    """Obtiene solo el estado y la fecha de un recordatorio para validaciones."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("SELECT status, datetime FROM reminders WHERE id = %s", (global_id,))
            return cursor.fetchone()


# --- UPDATE ---

def update_reminder_content(chat_id: int, global_id: int, text: str, dt: datetime | None, timezone: str):
    """Actualiza el contenido principal (texto, fecha, timezone) de un recordatorio."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute(
                "UPDATE reminders SET text = %s, datetime = %s, timezone = %s WHERE id = %s",
                (text, dt, timezone, global_id)
            )

def update_reminder_pre_alert(chat_id: int, global_id: int, minutes: int):
    """Actualiza el tiempo de aviso previo de un único recordatorio."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("UPDATE reminders SET pre_alert = %s WHERE id = %s", (minutes, global_id))

def change_reminders_status(chat_id: int, user_ids: tuple) -> list:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            query_select = "SELECT id, user_id, status, text, datetime, pre_alert FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_select, (user_ids, chat_id))
            full_info_reminders = cursor.fetchall()
            if not full_info_reminders: return []
            ids_to_pending = [r[1] for r in full_info_reminders if r[2] == 1]
            ids_to_done = [r[1] for r in full_info_reminders if r[2] == 0]
            if ids_to_pending:
                cursor.execute("UPDATE reminders SET status = 0 WHERE user_id IN %s AND chat_id = %s", (tuple(ids_to_pending), chat_id))
            if ids_to_done:
                cursor.execute("UPDATE reminders SET status = 1 WHERE user_id IN %s AND chat_id = %s", (tuple(ids_to_done), chat_id))
            return full_info_reminders

def mark_reminder_as_done(chat_id: int, global_id: int):
    """Marca un recordatorio como 'hecho' (status=1)."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("UPDATE reminders SET status = 1, pre_alert = 0 WHERE id = %s", (global_id,))

def update_all_reminders_timezone(chat_id: int, new_tz: str):
    """Actualiza la 'timezone' de TODOS los recordatorios de un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("UPDATE reminders SET timezone = %s WHERE chat_id = %s", (new_tz, chat_id))


# --- DELETE ---

def delete_reminders_filtered(chat_id: int, filter_type: str) -> tuple[int, List[int]]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            if filter_type == "past":
                sql_where = "WHERE chat_id = %s AND datetime IS NOT NULL AND datetime <= %s"
                params = (chat_id, datetime.now(pytz.utc))
            elif filter_type == "done":
                sql_where = "WHERE chat_id = %s AND status = 1"
                params = (chat_id,)
            else:
                return 0, []
            cursor.execute(f"SELECT id FROM reminders {sql_where}", params)
            ids_to_delete = [item[0] for item in cursor.fetchall()]
            if not ids_to_delete: return 0, []
            cursor.execute("DELETE FROM reminders WHERE id IN %s", (tuple(ids_to_delete),))
            return cursor.rowcount, ids_to_delete

def delete_reminders_by_user_ids(chat_id: int, user_ids: tuple) -> list[int]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            query_ids = "SELECT id FROM reminders WHERE user_id IN %s AND chat_id = %s"
            cursor.execute(query_ids, (user_ids, chat_id))
            global_ids = [row[0] for row in cursor.fetchall()]
            if not global_ids: return []
            cursor.execute("DELETE FROM reminders WHERE user_id IN %s AND chat_id = %s", (user_ids, chat_id))
            return global_ids


# =============================================================================
# FUNCIONES DE GESTIÓN DE RECORDATORIOS FIJOS
# =============================================================================

def add_pinned_reminder(chat_id: int, text: str, local_time: str, timezone: str, week_days: str) -> int:
    """
    Añade un nuevo recordatorio fijo a la base de datos y devuelve su ID.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            sql = """
                INSERT INTO pinned_reminders (chat_id, text, local_time, timezone, week_days)
                VALUES (%s, %s, %s, %s, %s) RETURNING id;
            """
            cursor.execute(sql, (chat_id, text, local_time, timezone, week_days))
            new_id = cursor.fetchone()[0]
            return new_id
        
def get_pinned_by_chat_id(chat_id: int) -> list:
    """Obtiene todos los recordatorios fijos de un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("SELECT id, text, local_time, timezone, week_days FROM pinned_reminders WHERE chat_id = %s ORDER BY local_time ASC", (chat_id,))
            return cursor.fetchall()

def check_pinned_exists(pinned_id: int, chat_id: int) -> bool:
    """Verifica si un recordatorio fijo existe y pertenece al usuario especificado."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute("SELECT id FROM pinned_reminders WHERE id = %s AND chat_id = %s", (pinned_id, chat_id))
            return cursor.fetchone() is not None
        
def update_pinned_by_id(chat_id: int, pinned_id: int, new_text: str, new_time: str, new_days: str):
    """Actualiza el texto y la hora de un recordatorio fijo."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            cursor.execute(
                "UPDATE pinned_reminders SET text = %s, local_time = %s, week_days = %s WHERE id = %s",
                (new_text, new_time, new_days, pinned_id)
            )
            
def delete_pinned_by_ids(chat_id: int, pinned_ids: tuple) -> int:
    """
    Borra uno o más recordatorios fijos por sus IDs y devuelve el número de filas borradas.
    Usa la cláusula IN para una operación en lote eficiente.
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # RLS Ready
            cursor.execute("SET LOCAL app.current_chat_id = %s", (str(chat_id),))
            
            # Usamos 'IN %s' y pasamos una tupla de IDs.
            # El WHERE chat_id es una capa extra de seguridad.
            cursor.execute(
                "DELETE FROM pinned_reminders WHERE id IN %s AND chat_id = %s", 
                (pinned_ids, chat_id)
            )
            return cursor.rowcount
        





# =============================================================================
# FUNCIONES DE ADMINISTRACIÓN Y UTILIDAD
# =============================================================================

def get_all_chat_ids() -> List[int]:
    """Obtiene todos los chat_id únicos. No es específica de usuario, no usa RLS."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT chat_id FROM reminders UNION SELECT DISTINCT chat_id FROM configuration")
            return [item[0] for item in cursor.fetchall()]

def reset_database():
    """Función de admin para borrar todos los datos. No usa RLS."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("TRUNCATE TABLE reminders, pinned_reminders, configuration RESTART IDENTITY CASCADE")
    print("🧹 TODAS las tablas han sido vaciadas.")