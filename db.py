import sqlite3
from datetime import datetime
import pytz
from config import OWNER_ID # Necesitaremos el OWNER_ID para la migración

DB_PATH = "la_recordadora.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# --- FUNCIÓN DE MIGRACIÓN PARA LA TABLA 'configuracion' ---
def _migrar_config_a_multi_usuario(conn):
    """
    Reestructura la tabla de configuración para soportar múltiples usuarios si es necesario.
    Esta es la función a la que te referías.
    """
    cursor = conn.cursor()
    try:
        # Hacemos una prueba para ver si la tabla ya tiene el formato nuevo (con chat_id)
        cursor.execute("SELECT chat_id FROM configuracion LIMIT 1")
    except sqlite3.OperationalError:
        # Si la consulta falla, es porque la columna chat_id no existe. Procedemos a migrar.
        print("MIGRANDO DB: Reestructurando la tabla 'configuracion' para multi-usuario...")
        
        # 1. Renombramos la tabla vieja para no perder los datos
        cursor.execute("ALTER TABLE configuracion RENAME TO config_old")
        
        # 2. Creamos la nueva tabla con la estructura correcta (clave primaria compuesta)
        cursor.execute("""
            CREATE TABLE configuracion (
                chat_id INTEGER NOT NULL,
                clave TEXT NOT NULL,
                valor TEXT,
                PRIMARY KEY (chat_id, clave)
            )
        """)
        
        # 3. Movemos los datos viejos a la nueva tabla, asignándolos al OWNER_ID
        cursor.execute("INSERT INTO configuracion (chat_id, clave, valor) SELECT ?, clave, valor FROM config_old", (OWNER_ID,))
        
        # 4. Borramos la tabla vieja
        cursor.execute("DROP TABLE config_old")
        
        conn.commit()
        print("MIGRACIÓN DE 'configuracion' COMPLETA.")

# --- FUNCIÓN DE MIGRACIÓN PARA LA TABLA 'recordatorios' ---
def _migrar_db_a_ids_secuenciales(conn):
    """
    Reestructura la tabla de recordatorios para usar un ID numérico autoincremental
    y un ID secuencial por usuario.
    """
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT user_id FROM recordatorios LIMIT 1")
    except sqlite3.OperationalError:
        print("MIGRANDO DB: Reestructurando 'recordatorios' para IDs secuenciales por usuario...")
        cursor.execute("ALTER TABLE recordatorios RENAME TO recordatorios_old")
        cursor.execute("""
            CREATE TABLE recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                texto TEXT,
                fecha_hora TEXT,
                estado INTEGER,
                aviso_previo INTEGER
            )
        """)
        
        # Migramos los datos viejos, generando los nuevos user_id
        cursor.execute("SELECT DISTINCT chat_id FROM recordatorios_old")
        chat_ids = cursor.fetchall()
        for chat_id_tuple in chat_ids:
            chat_id = chat_id_tuple[0]
            cursor.execute("SELECT texto, fecha_hora, estado, aviso_previo FROM recordatorios_old WHERE chat_id = ?", (chat_id,))
            old_reminders = cursor.fetchall()
            for i, reminder_data in enumerate(old_reminders, 1):
                texto, fecha, estado, aviso = reminder_data
                cursor.execute(
                    "INSERT INTO recordatorios (user_id, chat_id, texto, fecha_hora, estado, aviso_previo) VALUES (?, ?, ?, ?, ?, ?)",
                    (i, chat_id, texto, fecha, estado, aviso)
                )
        cursor.execute("DROP TABLE recordatorios_old")
        conn.commit()
        print("MIGRACIÓN DE 'recordatorios' COMPLETA.")

# --- FUNCIÓN PRINCIPAL DE CREACIÓN DE TABLAS ---
def crear_tablas():
    """Se asegura de que todas las tablas existan y tengan la estructura correcta."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # Creamos las tablas con la estructura final si no existen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recordatorios (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, chat_id INTEGER NOT NULL,
                texto TEXT, fecha_hora TEXT, estado INTEGER, aviso_previo INTEGER
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS configuracion (
                chat_id INTEGER NOT NULL, clave TEXT NOT NULL, valor TEXT,
                PRIMARY KEY (chat_id, clave)
            )
        """)
        
        # Llamamos a las funciones de migración. Solo actuarán si detectan tablas "viejas".
        _migrar_config_a_multi_usuario(conn)
        _migrar_db_a_ids_secuenciales(conn)

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

def actualizar_recordatorios_pasados():
    """
    Busca recordatorios pendientes cuya fecha ha pasado y los actualiza al estado 'pasado' (2).
    Esta función es clave para la nueva lógica automática.
    """
    # Usamos la misma zona horaria que el scheduler para consistencia
    now_utc = datetime.now(pytz.utc)
    now_utc_iso = now_utc.isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        # Cambiamos estado de 0 (pendiente) a 2 (pasado) si la fecha es anterior a ahora
        cursor.execute(
            """
            UPDATE recordatorios 
            SET estado = 2 
            WHERE estado = 0 AND fecha_hora IS NOT NULL AND fecha_hora < ?
            """,
            (now_utc_iso,)
        )
        # Devolvemos el número de filas cambiadas, útil para depurar
        changed_rows = cursor.rowcount
        conn.commit()
    
    if changed_rows > 0:
        print(f"ℹ️  {changed_rows} recordatorio(s) actualizado(s) a 'pasado'.")


def resetear_base_de_datos():
    """Elimina TODOS los recordatorios de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada.")