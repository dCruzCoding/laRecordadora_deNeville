import sqlite3
from config import OWNER_ID # Necesitaremos el OWNER_ID para la migración

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

def resetear_base_de_datos():
    """Elimina TODOS los recordatorios de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada.")