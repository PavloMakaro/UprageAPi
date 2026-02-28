import sqlite3
import uuid
import hashlib
import secrets
from database import get_db

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def register_user(username, password):
    conn = get_db()
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return False, "Username already exists"

    user_id = str(uuid.uuid4())
    pw_hash = hash_password(password)

    cursor.execute(
        "INSERT INTO users (id, username, password_hash, has_access) VALUES (?, ?, ?, 0)",
        (user_id, username, pw_hash)
    )
    conn.commit()
    conn.close()

    return True, "User registered successfully"

def login_user(username, password):
    conn = get_db()
    cursor = conn.cursor()

    pw_hash = hash_password(password)

    cursor.execute(
        "SELECT id, has_access FROM users WHERE username = ? AND password_hash = ?",
        (username, pw_hash)
    )
    user = cursor.fetchone()

    if not user:
        conn.close()
        return False, "Invalid credentials", None, None

    user_id = user['id']
    has_access = bool(user['has_access'])

    token = secrets.token_hex(32)
    cursor.execute(
        "INSERT INTO sessions (token, user_id) VALUES (?, ?)",
        (token, user_id)
    )
    conn.commit()
    conn.close()

    return True, "Login successful", token, has_access

def link_access_code(token, code):
    conn = get_db()
    cursor = conn.cursor()

    # Get user_id from token
    cursor.execute("SELECT user_id FROM sessions WHERE token = ?", (token,))
    session = cursor.fetchone()
    if not session:
        return False, "Invalid session"

    user_id = session['user_id']

    # Check code validity
    cursor.execute("SELECT used FROM access_codes WHERE code = ?", (code,))
    code_row = cursor.fetchone()

    if not code_row:
        return False, "Invalid access code"

    if code_row['used']:
        return False, "Access code already used"

    # Link code and grant access
    cursor.execute(
        "UPDATE access_codes SET used = 1, used_by = ? WHERE code = ?",
        (user_id, code)
    )
    cursor.execute(
        "UPDATE users SET has_access = 1 WHERE id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    return True, "Access granted"

def verify_token(token):
    if not token:
        return False, None

    conn = get_db()
    cursor = conn.cursor()

    # Get user info associated with session
    cursor.execute('''
        SELECT u.id, u.username, u.has_access
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        WHERE s.token = ?
    ''', (token,))

    user = cursor.fetchone()
    conn.close()

    if user:
        return True, dict(user)
    return False, None

def get_user_chats(user_id):
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, title, created_at, updated_at
        FROM chats
        WHERE user_id = ?
        ORDER BY updated_at DESC
    ''', (user_id,))

    chats = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return chats

def create_chat(user_id, title="New Chat"):
    conn = get_db()
    cursor = conn.cursor()

    chat_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO chats (id, user_id, title) VALUES (?, ?, ?)",
        (chat_id, user_id, title)
    )
    conn.commit()
    conn.close()
    return chat_id

def get_chat_history(chat_id, user_id):
    conn = get_db()
    cursor = conn.cursor()

    # Verify chat belongs to user
    cursor.execute("SELECT id FROM chats WHERE id = ? AND user_id = ?", (chat_id, user_id))
    if not cursor.fetchone():
        return None

    cursor.execute('''
        SELECT id, role, content, created_at
        FROM messages
        WHERE chat_id = ?
        ORDER BY created_at ASC
    ''', (chat_id,))

    messages = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return messages

def add_message(chat_id, role, content):
    conn = get_db()
    cursor = conn.cursor()

    msg_id = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO messages (id, chat_id, role, content) VALUES (?, ?, ?, ?)",
        (msg_id, chat_id, role, content)
    )
    cursor.execute(
        "UPDATE chats SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (chat_id,)
    )

    conn.commit()
    conn.close()
    return msg_id
