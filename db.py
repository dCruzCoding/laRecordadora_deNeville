import sqlite3
from datetime import datetime
import pytz # Asegúrate de que pytz está instalado

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


        # --- Añadir columnas seguras (aviso_previo y chat_id) ---
        cursor.execute("PRAGMA table_info(recordatorios)")
        cols = [r[1] for r in cursor.fetchall()]
        if "aviso_previo" not in cols:
            cursor.execute("ALTER TABLE recordatorios ADD COLUMN aviso_previo INTEGER")
        if "chat_id" not in cols:
            cursor.execute("ALTER TABLE recordatorios ADD COLUMN chat_id INTEGER")

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

def actualizar_recordatorios_pasados():
    """
    Busca recordatorios pendientes cuya fecha ha pasado y los actualiza al estado 'pasado' (2).
    Esta función es clave para la nueva lógica automática.
    """
    # Usamos la misma zona horaria que el scheduler para consistencia
    now_aware = datetime.now(pytz.timezone('Europe/Madrid')) # <-- ¡Usa tu zona horaria!
    now_iso = now_aware.isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        # Cambiamos estado de 0 (pendiente) a 2 (pasado) si la fecha es anterior a ahora
        cursor.execute(
            """
            UPDATE recordatorios 
            SET estado = 2 
            WHERE estado = 0 AND fecha_hora IS NOT NULL AND fecha_hora < ?
            """,
            (now_iso,)
        )
        # Devolvemos el número de filas cambiadas, útil para depurar
        changed_rows = cursor.rowcount
        conn.commit()
    
    if changed_rows > 0:
        print(f"ℹ️ {changed_rows} recordatorio(s) actualizado(s) a 'pasado'.")


def resetear_base_de_datos():
    """Elimina TODOS los recordatorios de la base de datos."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM recordatorios")
        conn.commit()
    print("🧹 La tabla de recordatorios ha sido vaciada.")