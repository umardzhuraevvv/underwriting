import sqlite3
import os
import bcrypt as _bcrypt

DB_PATH = os.environ.get("DATABASE_PATH", "underwriting.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT NOT NULL DEFAULT '',
            role TEXT NOT NULL CHECK(role IN ('admin', 'inspector')),
            is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)

    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()

    if not existing:
        pw_hash = _bcrypt.hashpw("admin123".encode("utf-8"), _bcrypt.gensalt()).decode("utf-8")
        conn.execute(
            "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
            ("admin", pw_hash, "Администратор", "admin"),
        )
        conn.commit()

    conn.close()
