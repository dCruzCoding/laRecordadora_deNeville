import sqlite3
from config import OWNER_ID # Necesitaremos el OWNER_ID para la migración
from datetime import datetime 
import pytz
from avisos import cancelar_avisos

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
    user_tz_str = get_config(chat_id, "user_timezone") or 'UTC'
    now_aware = datetime.now(pytz.timezone(user_tz_str))

    with get_connection() as conn:
        cursor = conn.cursor()

        # Construimos la consulta base y los parámetros
        query_base = "FROM recordatorios WHERE chat_id = ?"
        params = [chat_id]

        # Aplicamos el filtro de tiempo
        if filtro == "futuro":
            query_base += " AND estado = 0 AND (fecha_hora IS NULL OR fecha_hora > ?)"
            params.append(now_aware.isoformat())
        elif filtro == "pasado":
            query_base += " AND fecha_hora IS NOT NULL AND fecha_hora <= ?"
            params.append(now_aware.isoformat())

        # 1. Contamos el TOTAL de recordatorios que cumplen el filtro.
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
        
        # Primero, obtenemos los IDs de los jobs del scheduler que vamos a necesitar cancelar
        cursor.execute(
            "SELECT id FROM recordatorios WHERE chat_id = ? AND fecha_hora IS NOT NULL AND fecha_hora <= ?",
            (chat_id, now_aware.isoformat())
        )
        # El resultado es una lista de tuplas, ej: [(123,), (124,)]
        ids_a_borrar = [item[0] for item in cursor.fetchall()]

        # Ahora, borramos los recordatorios de la base de datos
        cursor.execute(
            "DELETE FROM recordatorios WHERE chat_id = ? AND fecha_hora IS NOT NULL AND fecha_hora <= ?",
            (chat_id, now_aware.isoformat())
        )
        num_borrados = cursor.rowcount
        conn.commit()

    # Cancelamos los avisos asociados a los recordatorios borrados
    for rid in ids_a_borrar:
        cancelar_avisos(str(rid)) # Asumimos que cancelar_avisos está disponible

    return num_borrados
def resetear_base_de_datos():
    """Elimina TODOS los recordatorios de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada.")