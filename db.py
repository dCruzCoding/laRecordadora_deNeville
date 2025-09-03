import sqlite3
from config import OWNER_ID # Necesitaremos el OWNER_ID para la migración
from datetime import datetime 
import pytz

DB_PATH = "la_recordadora.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# --- FUNCIÓN PRINCIPAL DE CREACIÓN DE TABLAS ---
def crear_tablas():
    """
    Crea las tablas con la estructura final y correcta si no existen.
    No se necesitan migraciones si empezamos con una base de datos limpia.
    """
    with get_connection() as conn:
        cursor = conn.cursor()

        # --- Tabla de Recordatorios (con la columna 'timezone') ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                texto TEXT,
                fecha_hora TEXT,
                estado INTEGER DEFAULT 0,
                aviso_previo INTEGER,
                timezone TEXT 
            )
        """)

        # --- Tabla de Configuración (con la estructura multi-usuario) ---
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                chat_id INTEGER NOT NULL,
                clave TEXT NOT NULL,
                valor TEXT,
                PRIMARY KEY (chat_id, clave)
            )
        """)
        
        conn.commit()


# --- FUNCIONES DE ACCESO A DATOS  ---
def get_config(chat_id: int, key: str) -> str:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE chat_id = ? AND clave = ?", (chat_id, key))
        row = cursor.fetchone()
        return row[0] if row else None

def set_config(chat_id: int, key: str, value: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO configuracion (chat_id, clave, valor) VALUES (?, ?, ?)", (chat_id, key, value))
        conn.commit()

def get_recordatorios(chat_id: int, filtro: str = "futuro", page: int = 1, items_per_page: int = 7) -> tuple[list, int]:
    """
    Función universal para obtener recordatorios de la base de datos con filtros y paginación.

    Args:
        chat_id (int): El ID del chat del usuario.
        filtro (str): "futuro" o "pasado".
        page (int): El número de página a obtener.
        items_per_page (int): Cuántos ítems por página.

    Returns:
        tuple: (Una lista de recordatorios para la página, el número total de ítems que coinciden con el filtro)
    """
    # Necesitamos la hora actual para los filtros de tiempo
    now_utc_iso = datetime.now(pytz.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()

        # Construimos la consulta base y los parámetros
        query_base = "FROM recordatorios WHERE chat_id = ?"
        params = [chat_id]

        # Aplicamos el filtro de tiempo
        if filtro == "futuro":
            query_base += " AND (fecha_hora IS NULL OR fecha_hora > ?)"
            params.append(now_utc_iso)
        elif filtro == "pasado":
            query_base += " AND fecha_hora IS NOT NULL AND fecha_hora <= ?"
            params.append(now_utc_iso)

        # --- ¡NUEVA LÓGICA! ---
        elif filtro == "hoy":
            # "Hoy" es desde las 00:00:00 hasta las 23:59:59 en la TZ del usuario
            start_of_day_local = now_utc_iso.replace(hour=0, minute=0, second=0, microsecond=0)
            end_of_day_local = now_utc_iso.replace(hour=23, minute=59, second=59, microsecond=999999)

            # Convertimos esos límites a UTC para consultar la base de datos
            start_of_day_utc = start_of_day_local.astimezone(pytz.utc)
            end_of_day_utc = end_of_day_local.astimezone(pytz.utc)
            
            # Buscamos recordatorios PENDIENTES entre esas dos marcas de tiempo
            query_base += " AND estado = 0 AND fecha_hora >= ? AND fecha_hora <= ?"
            params.extend([start_of_day_utc.isoformat(), end_of_day_utc.isoformat()])

        # Contamos el TOTAL de recordatorios que cumplen el filtro.
        cursor.execute(f"SELECT COUNT(id) {query_base}", tuple(params))
        total_items = cursor.fetchone()[0]

        if total_items == 0:
            return [], 0 # Devolvemos una lista vacía y 0 ítems.

        # 2. Calculamos el OFFSET y pedimos la "porción" para la página actual.
        offset = (page - 1) * items_per_page
        query_select = "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone"
        query_order = "ORDER BY fecha_hora ASC"
        
        cursor.execute(f"{query_select} {query_base} {query_order} LIMIT ? OFFSET ?", tuple(params + [items_per_page, offset]))
        recordatorios_pagina = cursor.fetchall()

        return recordatorios_pagina, total_items

def get_todos_los_chat_ids() -> list[int]:
    """
    Obtiene una lista de todos los chat_id únicos de los usuarios
    que tienen al menos un recordatorio o configuración.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # Usamos UNION para obtener IDs de ambas tablas y DISTINCT para evitar duplicados
        cursor.execute("""
            SELECT DISTINCT chat_id FROM recordatorios
            UNION
            SELECT DISTINCT chat_id FROM configuracion
        """)
        # El resultado es una lista de tuplas, ej: [(123,), (456,)]
        # Lo convertimos a una lista simple de enteros.
        return [item[0] for item in cursor.fetchall()]


# --- LIMPIEZA DE DATOS ---
def borrar_recordatorios_pasados(chat_id: int) -> int:
    """
    Elimina TODOS los recordatorios cuya fecha ya ha pasado para un chat_id específico.
    Devuelve el número de recordatorios borrados.
    """
    # Necesitamos la hora actual para saber qué se considera "pasado"
    user_tz_str = get_config(chat_id, "user_timezone") or 'UTC'
    now_aware = datetime.now(pytz.timezone(user_tz_str))

    with get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT id FROM recordatorios WHERE chat_id = ? AND fecha_hora IS NOT NULL AND fecha_hora <= ?",
            (chat_id, now_aware.isoformat())
        )
        # Obtenemos los IDs ANTES de borrar
        ids_a_borrar = [item[0] for item in cursor.fetchall()]

        if not ids_a_borrar:
            return 0, []

        # Usamos los IDs obtenidos para el borrado
        # Esto es más seguro que repetir la lógica del WHERE
        placeholders = ','.join(['?'] * len(ids_a_borrar))
        cursor.execute(
            f"DELETE FROM recordatorios WHERE id IN ({placeholders})",
            tuple(ids_a_borrar)
        )
        num_borrados = cursor.rowcount
        conn.commit()

    # --- YA NO CANCELAMOS AVISOS AQUÍ ---

    # Devolvemos tanto el número como los IDs
    return num_borrados, ids_a_borrar

def resetear_base_de_datos():
    """Elimina TODOS los recordatorios de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada.")