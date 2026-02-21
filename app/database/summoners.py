import os
from datetime import datetime
from typing import List, Optional, Tuple
from .db import database_connection

# Database file path (sqlite fallback)
DB_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')

def init_database():
    """Initialize the summoners database and apply migrations."""
    with database_connection() as (conn, is_pg):
        if is_pg:
            with conn.cursor() as cur:
                # Base table
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
                # Migrations: add columns if they don't exist yet
                cur.execute("ALTER TABLE summoners ADD COLUMN IF NOT EXISTS puuid TEXT")
                cur.execute("ALTER TABLE summoners ADD COLUMN IF NOT EXISTS region TEXT DEFAULT 'LAN'")
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
            # SQLite: ADD COLUMN fails if it already exists, so wrap in try/except
            for col_def in ("puuid TEXT", "region TEXT DEFAULT 'LAN'"):
                try:
                    conn.execute(f"ALTER TABLE summoners ADD COLUMN {col_def}")
                    conn.commit()
                except Exception:
                    pass  # Column already exists


def save_summoner(riot_id: str, region: str = None, puuid: str = None):
    """Save or update a summoner search, storing region and PUUID when available."""
    try:
        if '#' not in riot_id:
            return

        game_name, tag_line = riot_id.split('#', 1)
        # Normalise region to uppercase; keep None so we only overwrite when we know it
        region_val = region.upper() if region else None

        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT id FROM summoners WHERE riot_id = %s', (riot_id,)
                    )
                    exists = cur.fetchone()
                    if exists:
                        # Update search stats; only overwrite region/puuid when provided
                        if puuid and region_val:
                            cur.execute('''
                                UPDATE summoners
                                SET search_count = search_count + 1,
                                    last_searched = CURRENT_TIMESTAMP,
                                    game_name = %s,
                                    tag_line = %s,
                                    puuid = %s,
                                    region = %s
                                WHERE riot_id = %s
                            ''', (game_name, tag_line, puuid, region_val, riot_id))
                        elif region_val:
                            cur.execute('''
                                UPDATE summoners
                                SET search_count = search_count + 1,
                                    last_searched = CURRENT_TIMESTAMP,
                                    game_name = %s,
                                    tag_line = %s,
                                    region = %s
                                WHERE riot_id = %s
                            ''', (game_name, tag_line, region_val, riot_id))
                        else:
                            cur.execute('''
                                UPDATE summoners
                                SET search_count = search_count + 1,
                                    last_searched = CURRENT_TIMESTAMP,
                                    game_name = %s,
                                    tag_line = %s
                                WHERE riot_id = %s
                            ''', (game_name, tag_line, riot_id))
                    else:
                        cur.execute('''
                            INSERT INTO summoners (riot_id, game_name, tag_line, puuid, region)
                            VALUES (%s, %s, %s, %s, %s)
                        ''', (riot_id, game_name, tag_line, puuid, region_val or 'LAN'))
                    conn.commit()
            else:
                cursor = conn.execute(
                    'SELECT id FROM summoners WHERE riot_id = ?', (riot_id,)
                )
                exists = cursor.fetchone()
                if exists:
                    if puuid and region_val:
                        conn.execute('''
                            UPDATE summoners
                            SET search_count = search_count + 1,
                                last_searched = CURRENT_TIMESTAMP,
                                game_name = ?,
                                tag_line = ?,
                                puuid = ?,
                                region = ?
                            WHERE riot_id = ?
                        ''', (game_name, tag_line, puuid, region_val, riot_id))
                    elif region_val:
                        conn.execute('''
                            UPDATE summoners
                            SET search_count = search_count + 1,
                                last_searched = CURRENT_TIMESTAMP,
                                game_name = ?,
                                tag_line = ?,
                                region = ?
                            WHERE riot_id = ?
                        ''', (game_name, tag_line, region_val, riot_id))
                    else:
                        conn.execute('''
                            UPDATE summoners
                            SET search_count = search_count + 1,
                                last_searched = CURRENT_TIMESTAMP,
                                game_name = ?,
                                tag_line = ?
                            WHERE riot_id = ?
                        ''', (game_name, tag_line, riot_id))
                else:
                    conn.execute('''
                        INSERT INTO summoners (riot_id, game_name, tag_line, puuid, region)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (riot_id, game_name, tag_line, puuid, region_val or 'LAN'))
                conn.commit()
    except Exception as e:
        print(f"Error saving summoner {riot_id}: {e}")


def get_summoner_region(riot_id: str) -> Optional[str]:
    """Return the stored region for a riot_id, or None if not found."""
    try:
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT region FROM summoners WHERE riot_id = %s', (riot_id,)
                    )
                    row = cur.fetchone()
                    return row['region'] if row else None
            else:
                cursor = conn.execute(
                    'SELECT region FROM summoners WHERE riot_id = ?', (riot_id,)
                )
                row = cursor.fetchone()
                return row[0] if row else None
    except Exception as e:
        print(f"Error getting region for {riot_id}: {e}")
        return None


def get_summoner_by_puuid(puuid: str) -> Optional[dict]:
    """Return summoner record by PUUID (stable across name changes)."""
    try:
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute(
                        'SELECT riot_id, game_name, tag_line, region FROM summoners WHERE puuid = %s',
                        (puuid,)
                    )
                    row = cur.fetchone()
                    return dict(row) if row else None
            else:
                cursor = conn.execute(
                    'SELECT riot_id, game_name, tag_line, region FROM summoners WHERE puuid = ?',
                    (puuid,)
                )
                row = cursor.fetchone()
                if row:
                    return {'riot_id': row[0], 'game_name': row[1], 'tag_line': row[2], 'region': row[3]}
                return None
    except Exception as e:
        print(f"Error getting summoner by PUUID: {e}")
        return None


def get_summoners_with_region(limit: int = 100) -> List[Tuple[str, str]]:
    """Return list of (riot_id, region) for all stored summoners, ordered by recency."""
    try:
        with database_connection() as (conn, is_pg):
            if is_pg:
                with conn.cursor() as cur:
                    cur.execute('''
                        SELECT riot_id, COALESCE(region, 'LAN') AS region
                        FROM summoners
                        ORDER BY last_searched DESC
                        LIMIT %s
                    ''', (limit,))
                    return [(row['riot_id'], row['region']) for row in cur.fetchall()]
            else:
                cursor = conn.execute('''
                    SELECT riot_id, COALESCE(region, 'LAN') AS region
                    FROM summoners
                    ORDER BY last_searched DESC
                    LIMIT ?
                ''', (limit,))
                return [(row[0], row[1]) for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting summoners with region: {e}")
        return []

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
