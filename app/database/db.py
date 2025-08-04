import os
import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor

DB_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')

def get_connection():
    # Get environment variables at runtime, not at import time
    DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
    POSTGRES_URL = os.getenv("POSTGRES_URL")
    
    print(f"[DEBUG] DB_TYPE: {DB_TYPE}, POSTGRES_URL: {POSTGRES_URL}")
    if DB_TYPE == "postgres" and POSTGRES_URL:
        try:
            conn = psycopg2.connect(POSTGRES_URL, cursor_factory=RealDictCursor)
            print("[DEBUG] PostgreSQL connection successful")
            return conn
        except Exception as e:
            print(f"[DEBUG] PostgreSQL connection failed: {e}")
            print("[DEBUG] Falling back to SQLite")
            return sqlite3.connect(DB_PATH)
    else:
        print("[DEBUG] Using SQLite")
        return sqlite3.connect(DB_PATH)

def dict_from_row(row, cursor):
    # Get DB_TYPE at runtime
    DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
    if DB_TYPE == "postgres":
        return dict(row)
    else:
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}
