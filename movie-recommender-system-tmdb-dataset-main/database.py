"""
database.py
Local SQLite persistence for Netflix profiles, watch history, search history, watchlist, and TMDB cache.
"""

import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "netflix.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Profiles Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS profiles (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        avatar TEXT NOT NULL,
        is_active INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Seed default profiles if empty
    cursor.execute("SELECT COUNT(*) FROM profiles")
    if cursor.fetchone()[0] == 0:
        cursor.executemany("""
        INSERT INTO profiles (id, name, avatar, is_active) VALUES (?, ?, ?, ?)
        """, [
            (1, "Default User", "netflix-red", 1),
            (2, "Film Buff", "netflix-blue", 0),
            (3, "Sci-Fi Fan", "netflix-purple", 0),
            (4, "Guest", "netflix-green", 0),
        ])

    # Watch History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watch_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        movie_title TEXT NOT NULL,
        poster_path TEXT,
        progress_pct INTEGER DEFAULT 15,
        duration_watched TEXT DEFAULT '25m',
        last_watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(profile_id, movie_id)
    )
    """)

    # Search History Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS search_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        query TEXT NOT NULL,
        result_count INTEGER DEFAULT 0,
        searched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Watchlist Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watchlist (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        profile_id INTEGER NOT NULL,
        movie_id INTEGER NOT NULL,
        movie_title TEXT NOT NULL,
        poster_path TEXT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(profile_id, movie_id)
    )
    """)

    # TMDB Cache Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tmdb_cache (
        movie_id INTEGER PRIMARY KEY,
        poster_path TEXT,
        backdrop_path TEXT,
        trailer_key TEXT,
        cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    conn.commit()
    conn.close()

# Profile Management
def get_profiles():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, avatar, is_active FROM profiles ORDER BY id ASC")
    profiles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return profiles

def get_active_profile():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, avatar, is_active FROM profiles WHERE is_active = 1 LIMIT 1")
    row = cursor.fetchone()
    if not row:
        cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = 1")
        conn.commit()
        cursor.execute("SELECT id, name, avatar, is_active FROM profiles WHERE id = 1")
        row = cursor.fetchone()
    profile = dict(row)
    conn.close()
    return profile

def set_active_profile(profile_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET is_active = 0")
    cursor.execute("UPDATE profiles SET is_active = 1 WHERE id = ?", (profile_id,))
    conn.commit()
    conn.close()
    return get_active_profile()

# Watch History
def record_watch(profile_id: int, movie_id: int, movie_title: str, poster_path: str = None, progress_pct: int = 25, duration_watched: str = "30m"):
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO watch_history (profile_id, movie_id, movie_title, poster_path, progress_pct, duration_watched, last_watched_at)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(profile_id, movie_id) DO UPDATE SET
        progress_pct = excluded.progress_pct,
        duration_watched = excluded.duration_watched,
        last_watched_at = excluded.last_watched_at,
        poster_path = COALESCE(excluded.poster_path, watch_history.poster_path)
    """, (profile_id, movie_id, movie_title, poster_path, progress_pct, duration_watched, now))
    conn.commit()
    conn.close()

def get_watch_history(profile_id: int, limit: int = 50):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, movie_id, movie_title, poster_path, progress_pct, duration_watched, last_watched_at
    FROM watch_history
    WHERE profile_id = ?
    ORDER BY last_watched_at DESC
    LIMIT ?
    """, (profile_id, limit))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history

def delete_watch_history_item(profile_id: int, movie_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watch_history WHERE profile_id = ? AND movie_id = ?", (profile_id, movie_id))
    conn.commit()
    conn.close()

def clear_watch_history(profile_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watch_history WHERE profile_id = ?", (profile_id,))
    conn.commit()
    conn.close()

# Search History
def record_search(profile_id: int, query: str, result_count: int = 0):
    clean_q = query.strip()
    if not clean_q:
        return
    conn = get_connection()
    cursor = conn.cursor()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO search_history (profile_id, query, result_count, searched_at)
    VALUES (?, ?, ?, ?)
    """, (profile_id, clean_q, result_count, now))
    conn.commit()
    conn.close()

def get_search_history(profile_id: int, limit: int = 30):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT id, query, result_count, searched_at
    FROM search_history
    WHERE profile_id = ?
    ORDER BY searched_at DESC
    LIMIT ?
    """, (profile_id, limit))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def delete_search_history_item(profile_id: int, item_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM search_history WHERE profile_id = ? AND id = ?", (profile_id, item_id))
    conn.commit()
    conn.close()

def clear_search_history(profile_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM search_history WHERE profile_id = ?", (profile_id,))
    conn.commit()
    conn.close()

# Watchlist Management
def toggle_watchlist(profile_id: int, movie_id: int, movie_title: str, poster_path: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM watchlist WHERE profile_id = ? AND movie_id = ?", (profile_id, movie_id))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM watchlist WHERE profile_id = ? AND movie_id = ?", (profile_id, movie_id))
        is_in = False
    else:
        cursor.execute("""
        INSERT INTO watchlist (profile_id, movie_id, movie_title, poster_path)
        VALUES (?, ?, ?, ?)
        """, (profile_id, movie_id, movie_title, poster_path))
        is_in = True
    conn.commit()
    conn.close()
    return is_in

def get_watchlist(profile_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT movie_id, movie_title, poster_path, added_at
    FROM watchlist
    WHERE profile_id = ?
    ORDER BY added_at DESC
    """, (profile_id,))
    items = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return items

def is_in_watchlist(profile_id: int, movie_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM watchlist WHERE profile_id = ? AND movie_id = ?", (profile_id, movie_id))
    res = cursor.fetchone() is not None
    conn.close()
    return res

# TMDB Cache
def get_tmdb_cache(movie_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT poster_path, backdrop_path, trailer_key FROM tmdb_cache WHERE movie_id = ?", (movie_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def set_tmdb_cache(movie_id: int, poster_path: str = None, backdrop_path: str = None, trailer_key: str = None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO tmdb_cache (movie_id, poster_path, backdrop_path, trailer_key)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(movie_id) DO UPDATE SET
        poster_path = COALESCE(excluded.poster_path, tmdb_cache.poster_path),
        backdrop_path = COALESCE(excluded.backdrop_path, tmdb_cache.backdrop_path),
        trailer_key = COALESCE(excluded.trailer_key, tmdb_cache.trailer_key),
        cached_at = CURRENT_TIMESTAMP
    """, (movie_id, poster_path, backdrop_path, trailer_key))
    conn.commit()
    conn.close()

# Initialize DB on load
init_db()
