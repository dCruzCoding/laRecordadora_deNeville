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
    # No se necesita el check_same_thread=False.
    return psycopg2.connect(SUPABASE_DB_URL)


# =============================================================================
# INICIALIZACIÓN DE LA BASE DE DATOS
# =============================================================================

def crear_tablas():
    """
    Crea las tablas 'recordatorios' y 'configuracion' si no existen.
    """
    # Usamos 'with' para asegurar que la conexión y el cursor se cierren solos.
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: La sintaxis de autoincremento en PostgreSQL es SERIAL o BIGSERIAL.
            # BIGSERIAL es mejor para IDs que pueden crecer mucho.
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS recordatorios (
                    id BIGSERIAL PRIMARY KEY,                  -- ID único global
                    user_id INTEGER NOT NULL,
                    chat_id BIGINT NOT NULL,                   -- Usar BIGINT para chat_id por si acaso
                    texto TEXT,
                    fecha_hora TIMESTAMPTZ,                    -- TIMESTAMPTZ es el tipo ideal para UTC en Postgres
                    estado INTEGER DEFAULT 0,
                    aviso_previo INTEGER,
                    timezone TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS configuracion (
                    chat_id BIGINT NOT NULL,
                    clave TEXT NOT NULL,
                    valor TEXT,
                    PRIMARY KEY (chat_id, clave)
                )
            """)
            


# =============================================================================
# FUNCIONES DE CONFIGURACIÓN (CLAVE-VALOR)
# =============================================================================

# CAMBIO CLAVE: PostgreSQL usa %s como placeholder en lugar de ?.

def get_config(chat_id: int, key: str) -> Optional[str]:
    """Obtiene el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT valor FROM configuracion WHERE chat_id = %s AND clave = %s", (chat_id, key))
            row = cursor.fetchone()
            return row[0] if row else None

def set_config(chat_id: int, key: str, value: str):
    """Establece o actualiza el valor de una clave de configuración para un usuario."""
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # CAMBIO: 'INSERT OR REPLACE' es de SQLite. El equivalente en PostgreSQL es 'INSERT ... ON CONFLICT'.
            sql = """
                INSERT INTO configuracion (chat_id, clave, valor) VALUES (%s, %s, %s)
                ON CONFLICT (chat_id, clave) DO UPDATE SET valor = EXCLUDED.valor;
            """
            cursor.execute(sql, (chat_id, key, value))

# =============================================================================
# FUNCIONES DE GESTIÓN DE RECORDATORIOS
# =============================================================================

def get_recordatorios(chat_id: int, filtro: str = "futuro", page: int = 1, items_per_page: int = 7) -> Tuple[List, int]:
    now_utc = datetime.now(pytz.utc)

    with get_connection() as conn:
        with conn.cursor() as cursor:
            query_base = "FROM recordatorios WHERE chat_id = %s"
            params = [chat_id]

            # AÑADIMOS LOS FILTROS POR ESTADO
            if filtro == "hechos":
                query_base += " AND estado = 1"
                # No se añaden más parámetros
            elif filtro == "pendientes":
                query_base += " AND estado = 0"

            # AÑADIMOS LOS FILTROS TEMPORALES 
            if filtro == "futuro":
                query_base += " AND (fecha_hora IS NULL OR fecha_hora > %s)"
                params.append(now_utc) # psycopg2 maneja objetos datetime directamente
            elif filtro == "pasado":
                query_base += " AND fecha_hora IS NOT NULL AND fecha_hora <= %s"
                params.append(now_utc)
            elif filtro == "hoy":
                user_tz_str = get_config(chat_id, "user_timezone") or "UTC"
                user_tz = pytz.timezone(user_tz_str)
                now_local = now_utc.astimezone(user_tz)
                
                start_of_day_local = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day_local = now_local.replace(hour=23, minute=59, second=59, microsecond=999999)

                start_of_day_utc = start_of_day_local.astimezone(pytz.utc)
                end_of_day_utc = end_of_day_local.astimezone(pytz.utc)
                
                query_base += " AND estado = 0 AND fecha_hora >= %s AND fecha_hora <= %s"
                params.extend([start_of_day_utc, end_of_day_utc])

            cursor.execute(f"SELECT COUNT(id) {query_base}", tuple(params))
            total_items = cursor.fetchone()[0]

            if total_items == 0:
                return [], 0

            offset = (page - 1) * items_per_page
            query_select = "SELECT id, user_id, chat_id, texto, fecha_hora, estado, aviso_previo, timezone"
            query_order = "ORDER BY fecha_hora ASC"

            # Si filtramos por estado, tiene más sentido ordenar por fecha de más reciente a más antiguo.
            if filtro in ["hechos", "pendientes"]:
                query_order = "ORDER BY fecha_hora DESC"
            
            cursor.execute(f"{query_select} {query_base} {query_order} LIMIT %s OFFSET %s", tuple(params + [items_per_page, offset]))
            recordatorios_pagina = cursor.fetchall()

            return recordatorios_pagina, total_items

def get_todos_los_chat_ids() -> List[int]:
    with get_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT DISTINCT chat_id FROM recordatorios UNION SELECT DISTINCT chat_id FROM configuracion")
            return [item[0] for item in cursor.fetchall()]

def borrar_recordatorios_por_filtro(chat_id: int, filtro: str) -> tuple[int, List[int]]:
    """
    Función universal para eliminar recordatorios de un usuario basándose en un filtro.

    Args:
        chat_id (int): El ID del chat del usuario.
        filtro (str): El criterio para borrar. Puede ser "pasados" o "hechos".

    Returns:
        tuple: (Número de recordatorios borrados, Lista de IDs de los recordatorios borrados).
    """
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Construimos la consulta SQL dinámicamente según el filtro
            if filtro == "pasados":
                sql_where = "WHERE chat_id = %s AND fecha_hora IS NOT NULL AND fecha_hora <= %s"
                params = (chat_id, datetime.now(pytz.utc))
            elif filtro == "hechos":
                sql_where = "WHERE chat_id = %s AND estado = 1"
                params = (chat_id,)
            else:
                # Si se pasa un filtro no válido, no hacemos nada.
                return 0, []

            # 1. Obtenemos los IDs de los recordatorios que vamos a borrar.
            cursor.execute(f"SELECT id {sql_where}", params)
            ids_a_borrar = [item[0] for item in cursor.fetchall()]

            if not ids_a_borrar:
                return 0, []

            # 2. Los borramos usando sus IDs.
            cursor.execute("DELETE FROM recordatorios WHERE id IN %s", (tuple(ids_a_borrar),))
            num_borrados = cursor.rowcount

    return num_borrados, ids_a_borrar

def resetear_base_de_datos():
    with get_connection() as conn:
        with conn.cursor() as cursor:
            # TRUNCATE es más rápido que DELETE para vaciar tablas grandes en PostgreSQL
            cursor.execute("TRUNCATE TABLE recordatorios")
    print("🧹 La tabla de recordatorios ha sido vaciada por completo.")