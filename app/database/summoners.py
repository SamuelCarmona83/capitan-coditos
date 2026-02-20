import os
from datetime import datetime
from typing import List, Optional
from .db import database_connection

# Database file path (sqlite fallback)
DB_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')

def init_database():
    """Initialize the summoners database"""
    with database_connection() as (conn, is_pg):
        if is_pg:
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
        else:
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

def save_summoner(riot_id: str):
    """Save or update a summoner search"""
    try:
        # Parse riot_id to get game_name and tag_line
        if '#' not in riot_id:
            return
        
        game_name, tag_line = riot_id.split('#', 1)
        
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute('''
                        UPDATE summoners 
                        SET search_count = search_count + 1, last_searched = CURRENT_TIMESTAMP
                        WHERE riot_id = %s
                    ''', (riot_id,))
                    
                    if cur.rowcount == 0:
                        cur.execute('''
                            INSERT INTO summoners (riot_id, game_name, tag_line)
                            VALUES (%s, %s, %s)
                        ''', (riot_id, game_name, tag_line))
                    conn.commit()
            else:
                cursor = conn.execute('''
                    UPDATE summoners 
                    SET search_count = search_count + 1, last_searched = CURRENT_TIMESTAMP
                    WHERE riot_id = ?
                ''', (riot_id,))
                
                if cursor.rowcount == 0:
                    conn.execute('''
                        INSERT INTO summoners (riot_id, game_name, tag_line)
                        VALUES (?, ?, ?)
                    ''', (riot_id, game_name, tag_line))
                
                conn.commit()
    except Exception as e:
        print(f"Error saving summoner {riot_id}: {e}")

def get_summoners_for_autocomplete(query: str = "", limit: int = 10) -> List[str]:
    """Get summoners for autocomplete, ordered by search frequency and recency"""
    try:
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    if query:
                        cur.execute('''
                            SELECT riot_id FROM summoners 
                            WHERE game_name ILIKE %s 
                            ORDER BY search_count DESC, last_searched DESC 
                            LIMIT %s
                        ''', (f'%{query}%', limit))
                    else:
                        cur.execute('''
                            SELECT riot_id FROM summoners 
                            ORDER BY search_count DESC, last_searched DESC 
                            LIMIT %s
                        ''', (limit,))
                    
                    results = [row['riot_id'] for row in cur.fetchall()]
                    return results
            else:
                if query:
                    cursor = conn.execute('''
                        SELECT riot_id FROM summoners 
                        WHERE game_name LIKE ? 
                        ORDER BY search_count DESC, last_searched DESC 
                        LIMIT ?
                    ''', (f'%{query}%', limit))
                else:
                    cursor = conn.execute('''
                        SELECT riot_id FROM summoners 
                        ORDER BY search_count DESC, last_searched DESC 
                        LIMIT ?
                    ''', (limit,))
                
                results = [row[0] for row in cursor.fetchall()]
                return results
    except Exception as e:
        print(f"Error getting summoners for autocomplete: {e}")
        import traceback
        traceback.print_exc()
        return []

def get_summoner_stats() -> dict:
    """Get database statistics"""
    try:
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute('SELECT COUNT(*), SUM(search_count) FROM summoners')
                    result = cur.fetchone()
                    total_summoners, total_searches = result['count'], result['sum']
            else:
                cursor = conn.execute('SELECT COUNT(*), SUM(search_count) FROM summoners')
                result = cursor.fetchone()
                total_summoners, total_searches = result
        
        # Forzar a int para evitar errores si vienen como str
        try:
            total_summoners = int(total_summoners or 0)
        except Exception:
            total_summoners = 0
        try:
            total_searches = int(total_searches or 0)
        except Exception:
            total_searches = 0
        
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
