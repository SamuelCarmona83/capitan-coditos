import os
import sqlite3
import psycopg2
from psycopg2.extras import execute_values

# Configuración
SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')
POSTGRES_URL = os.getenv("POSTGRES_URL", "postgresql://postgres:postgres@localhost:5432/discbot")

# Lee todos los datos de SQLite
def fetch_sqlite_data():
    conn = sqlite3.connect(SQLITE_PATH)
    cursor = conn.execute('SELECT riot_id, game_name, tag_line, search_count, last_searched, created_at FROM summoners')
    rows = []
    for row in cursor.fetchall():
        riot_id, game_name, tag_line, search_count, last_searched, created_at = row
        # Si las fechas son vacías, ponlas en None
        last_searched = last_searched if last_searched else None
        created_at = created_at if created_at else None
        # Si search_count es string, conviértelo a int
        if isinstance(search_count, str):
            try:
                search_count = int(search_count)
            except Exception:
                search_count = 1
        rows.append((riot_id, game_name, tag_line, search_count, last_searched, created_at))
    conn.close()
    return rows

# Inserta los datos en PostgreSQL
def insert_postgres_data(rows):
    conn = psycopg2.connect(POSTGRES_URL)
    with conn, conn.cursor() as cur:
        cur.execute('''
            CREATE TABLE IF NOT EXISTS summoners (
                id SERIAL PRIMARY KEY,
                riot_id TEXT UNIQUE NOT NULL,
                game_name TEXT NOT NULL,
                tag_line TEXT NOT NULL,
                search_count INTEGER DEFAULT 1,
                last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        execute_values(cur, '''
            INSERT INTO summoners (riot_id, game_name, tag_line, search_count, last_searched, created_at)
            VALUES %s
            ON CONFLICT (riot_id) DO UPDATE SET
                search_count = EXCLUDED.search_count,
                last_searched = EXCLUDED.last_searched,
                created_at = EXCLUDED.created_at
        ''', rows)
    conn.close()

if __name__ == "__main__":
    data = fetch_sqlite_data()
    print(f"Migrando {len(data)} registros de SQLite a PostgreSQL...")
    insert_postgres_data(data)
    print("¡Migración completada!")
