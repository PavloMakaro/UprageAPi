import sqlite3
import os
import uuid
import hashlib
import secrets
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'jarvis.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        has_access BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Access codes table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS access_codes (
        code TEXT PRIMARY KEY,
        used BOOLEAN DEFAULT 0,
        used_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (used_by) REFERENCES users (id)
    )
    ''')

    # Sessions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Chats table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS chats (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        title TEXT DEFAULT 'New Chat',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Messages table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        chat_id TEXT NOT NULL,
        role TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (chat_id) REFERENCES chats (id)
    )
    ''')

    conn.commit()
    conn.close()

def generate_access_codes(count=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    codes = []
    for _ in range(count):
        code = secrets.token_hex(8)
        codes.append(code)
        cursor.execute("INSERT OR IGNORE INTO access_codes (code) VALUES (?)", (code,))

    conn.commit()
    conn.close()

    code_file_path = os.path.join(os.path.dirname(__file__), 'коды_доступа.txt')
    with open(code_file_path, 'a') as f:
        for code in codes:
            f.write(f"{code}\n")

    return codes

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Init DB when module is loaded
init_db()
