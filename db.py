import sqlite3

DB_PATH = "la_recordadora.db"

def get_connection():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

def crear_tablas():
    with get_connection() as conn:
        cursor = conn.cursor()

        # Tabla de recordatorios
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS recordatorios (
            id TEXT PRIMARY KEY,
            texto TEXT,
            fecha_hora TEXT,
            estado INTEGER
        )
        """)

        # Tabla de configuración
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS configuracion (
            clave TEXT PRIMARY KEY,
            valor TEXT
        )
        """)

        # Valor por defecto de modo_seguro
        cursor.execute("""
        INSERT OR IGNORE INTO configuracion (clave, valor) VALUES ('modo_seguro', '0')
        """)

        conn.commit()

def get_config(key: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT valor FROM configuracion WHERE clave = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else None

def set_config(key: str, value: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO configuracion (clave, valor) VALUES (?, ?)", (key, value))
        conn.commit()
