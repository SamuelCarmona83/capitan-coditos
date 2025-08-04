import os
from datetime import datetime
from typing import List, Optional
from .db import get_connection

# Database file path (sqlite fallback)
DB_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')

def init_database():
    """Initialize the summoners database"""
    DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
    if DB_TYPE == "sqlite":
        import sqlite3
        with get_connection() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS summoners (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    riot_id TEXT UNIQUE NOT NULL,
                    game_name TEXT NOT NULL,
                    tag_line TEXT NOT NULL,
                    search_count INTEGER DEFAULT 1,
                    last_searched TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    elif DB_TYPE == "postgres":
        with get_connection() as conn:
            with conn.cursor() as cur:
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
                conn.commit()

def save_summoner(riot_id: str):
    """Save or update a summoner search"""
    try:
        # Parse riot_id to get game_name and tag_line
        if '#' not in riot_id:
            return
        
        game_name, tag_line = riot_id.split('#', 1)
        
        DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
        with get_connection() as conn:
            if DB_TYPE == "sqlite":
                # Try to update existing record
                cursor = conn.execute('''
                    UPDATE summoners 
                    SET search_count = search_count + 1, last_searched = CURRENT_TIMESTAMP
                    WHERE riot_id = ?
                ''', (riot_id,))
                
                # If no record was updated, insert new one
                if cursor.rowcount == 0:
                    conn.execute('''
                        INSERT INTO summoners (riot_id, game_name, tag_line)
                        VALUES (?, ?, ?)
                    ''', (riot_id, game_name, tag_line))
                
                conn.commit()
            else:
                with conn.cursor() as cur:
                    # Try to update existing record
                    cur.execute('''
                        UPDATE summoners 
                        SET search_count = search_count + 1, last_searched = CURRENT_TIMESTAMP
                        WHERE riot_id = %s
                    ''', (riot_id,))
                    
                    # If no record was updated, insert new one
                    if cur.rowcount == 0:
                        cur.execute('''
                            INSERT INTO summoners (riot_id, game_name, tag_line)
                            VALUES (%s, %s, %s)
                        ''', (riot_id, game_name, tag_line))
                    conn.commit()
    except Exception as e:
        print(f"Error saving summoner {riot_id}: {e}")

def get_summoners_for_autocomplete(query: str = "", limit: int = 10) -> List[str]:
    """Get summoners for autocomplete, ordered by search frequency and recency"""
    try:
        DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
        print(f"[DEBUG] get_summoners_for_autocomplete - DB_TYPE: {DB_TYPE}, query: '{query}', limit: {limit}")
        
        with get_connection() as conn:
            print(f"[DEBUG] get_summoners_for_autocomplete - Connection obtained: {type(conn)}")
            
            if DB_TYPE == "sqlite":
                if query:
                    # Search by game_name (case insensitive)
                    cursor = conn.execute('''
                        SELECT riot_id FROM summoners 
                        WHERE game_name LIKE ? 
                        ORDER BY search_count DESC, last_searched DESC 
                        LIMIT ?
                    ''', (f'%{query}%', limit))
                else:
                    # Get most searched summoners
                    cursor = conn.execute('''
                        SELECT riot_id FROM summoners 
                        ORDER BY search_count DESC, last_searched DESC 
                        LIMIT ?
                    ''', (limit,))
                
                results = [row[0] for row in cursor.fetchall()]
                print(f"[DEBUG] get_summoners_for_autocomplete - SQLite results: {results}")
                return results
            else:
                with conn.cursor() as cur:
                    if query:
                        print(f"[DEBUG] get_summoners_for_autocomplete - Executing PostgreSQL query with search")
                        cur.execute('''
                            SELECT riot_id FROM summoners 
                            WHERE game_name ILIKE %s 
                            ORDER BY search_count DESC, last_searched DESC 
                            LIMIT %s
                        ''', (f'%{query}%', limit))
                    else:
                        print(f"[DEBUG] get_summoners_for_autocomplete - Executing PostgreSQL query without search")
                        cur.execute('''
                            SELECT riot_id FROM summoners 
                            ORDER BY search_count DESC, last_searched DESC 
                            LIMIT %s
                        ''', (limit,))
                    
                    # With RealDictCursor, results are dictionaries, not tuples
                    results = [row['riot_id'] for row in cur.fetchall()]
                    print(f"[DEBUG] get_summoners_for_autocomplete - PostgreSQL results: {results}")
                    return results
    except Exception as e:
        print(f"Error getting summoners for autocomplete: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_summoner_stats() -> dict:
    """Get database statistics"""
    try:
        DB_TYPE = os.getenv("DB_TYPE", "sqlite").lower()
        print(f"[DEBUG] get_summoner_stats - DB_TYPE: {DB_TYPE}")
        
        with get_connection() as conn:
            print(f"[DEBUG] get_summoner_stats - Connection obtained: {type(conn)}")
            
            if DB_TYPE == "sqlite":
                cursor = conn.execute('SELECT COUNT(*), SUM(search_count) FROM summoners')
                result = cursor.fetchone()
                print(f"[DEBUG] get_summoner_stats - SQLite result: {result}")
                total_summoners, total_searches = result
            else:
                with conn.cursor() as cur:
                    cur.execute('SELECT COUNT(*), SUM(search_count) FROM summoners')
                    result = cur.fetchone()
                    print(f"[DEBUG] get_summoner_stats - PostgreSQL result: {result}")
                    # With RealDictCursor, results are dictionaries, not tuples
                    total_summoners, total_searches = result['count'], result['sum']
            
            print(f"[DEBUG] get_summoner_stats - Raw values: summoners={total_summoners}, searches={total_searches}")
            
            # Forzar a int para evitar errores si vienen como str
            try:
                total_summoners = int(total_summoners or 0)
            except Exception:
                total_summoners = 0
            try:
                total_searches = int(total_searches or 0)
            except Exception:
                total_searches = 0
            
            print(f"[DEBUG] get_summoner_stats - Final values: summoners={total_summoners}, searches={total_searches}")
            
            return {
                'total_summoners': total_summoners,
                'total_searches': total_searches
            }
    except Exception as e:
        print(f"Error getting summoner stats: {e}")
        import traceback
        traceback.print_exc()
        return {'total_summoners': 0, 'total_searches': 0}

# Initialize database when module is imported
init_database()
