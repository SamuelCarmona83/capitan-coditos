import sqlite3
import os
from datetime import datetime
from typing import List, Optional

# Database file path
DB_PATH = os.path.join(os.path.dirname(__file__), 'summoners.db')

def init_database():
    """Initialize the summoners database"""
    with sqlite3.connect(DB_PATH) as conn:
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
        
        with sqlite3.connect(DB_PATH) as conn:
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
    except Exception as e:
        print(f"Error saving summoner {riot_id}: {e}")

def get_summoners_for_autocomplete(query: str = "", limit: int = 10) -> List[str]:
    """Get summoners for autocomplete, ordered by search frequency and recency"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
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
            
            return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"Error getting summoners for autocomplete: {e}")
        return []

def get_summoner_stats() -> dict:
    """Get database statistics"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.execute('SELECT COUNT(*), SUM(search_count) FROM summoners')
            total_summoners, total_searches = cursor.fetchone()
            return {
                'total_summoners': total_summoners or 0,
                'total_searches': total_searches or 0
            }
    except Exception as e:
        print(f"Error getting summoner stats: {e}")
        return {'total_summoners': 0, 'total_searches': 0}

# Initialize database when module is imported
init_database()
