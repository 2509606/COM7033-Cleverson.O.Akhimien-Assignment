# SQLite helpers for user authentication database

import os
import sqlite3
from datetime import datetime
from flask import g
from werkzeug.security import generate_password_hash

DATABASE = os.environ.get("DATABASE", "users.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'doctor',
            status TEXT NOT NULL DEFAULT 'approved',
            created_at TEXT NOT NULL
        )
    """)
    db.commit()

    # Migrate: add email and status columns if they don't exist
    columns = [row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()]
    if "email" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN email TEXT")
        db.commit()
    if "status" not in columns:
        db.execute("ALTER TABLE users ADD COLUMN status TEXT NOT NULL DEFAULT 'approved'")
        db.commit()

    # Migrate clinician role to doctor
    db.execute("UPDATE users SET role = 'doctor' WHERE role = 'clinician'")
    db.commit()


def seed_admin():
    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, email, password, role, status, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "admin",
                "admin@example.com",
                generate_password_hash("admin123"),
                "admin",
                "approved",
                datetime.now().isoformat(),
            ),
        )
        db.commit()
