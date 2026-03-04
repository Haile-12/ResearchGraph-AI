import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Optional, Any

DB_PATH = os.path.join(os.getcwd(), "data", "history.db")

def _connect():
    """Return a connection with foreign key enforcement enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    """Initialise the SQLite database and create tables if they don't exist."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _connect()
    cursor = conn.cursor()
    
    # Tables for sessions and messages
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            role TEXT, -- 'human' or 'ai'
            content TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions (session_id) ON DELETE CASCADE
        )
    ''')
    
    conn.commit()
    conn.close()

def save_session(session_id: str, title: str):
    """Save or update a session title."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sessions (session_id, title) 
        VALUES (?, ?)
        ON CONFLICT(session_id) DO UPDATE SET 
            title = excluded.title,
            updated_at = CURRENT_TIMESTAMP
    ''', (session_id, title))
    conn.commit()
    conn.close()

def get_session(session_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve session metadata."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM sessions WHERE session_id = ?', (session_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_all_sessions() -> List[Dict[str, Any]]:
    """Get all sessions ordered by most recent."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    # Format updated_at as ISO string for frontend compatibility
    cursor.execute('''
        SELECT 
            session_id, 
            title, 
            strftime('%Y-%m-%dT%H:%M:%SZ', created_at) as created_at,
            strftime('%Y-%m-%dT%H:%M:%SZ', updated_at) as updated_at
        FROM sessions 
        ORDER BY updated_at DESC
    ''')
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_message(session_id: str, role: str, content: str):
    """Store a single message in a session."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (session_id, role, content)
        VALUES (?, ?, ?)
    ''', (session_id, role, content))
    
    # Update updated_at for the session
    cursor.execute('UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE session_id = ?', (session_id,))
    
    conn.commit()
    conn.close()

def get_messages(session_id: str) -> List[Dict[str, Any]]:
    """Retrieve all messages for a session."""
    conn = _connect()
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute('''
        SELECT 
            id, 
            session_id, 
            role, 
            content, 
            strftime('%Y-%m-%dT%H:%M:%SZ', timestamp) as timestamp
        FROM messages 
        WHERE session_id = ? 
        ORDER BY timestamp ASC, id ASC
    ''', (session_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_session_db(session_id: str):
    """Delete a session and all its messages."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
    cursor.execute('DELETE FROM sessions WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()

def clear_messages(session_id: str):
    """Clear messages for a session but keep the session itself."""
    conn = _connect()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE session_id = ?', (session_id,))
    conn.commit()
    conn.close()
