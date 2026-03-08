# I'm building a Patient Record Management System for my COM7033 module
# I'll keep everything in one file following the pattern from the Week 6 Flask slides
# The app uses SQLite for user authentication and MongoDB for patient records

import os
import sqlite3
import secrets
import re
from datetime import datetime
from functools import wraps

from dotenv import load_dotenv
from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, g
)
from werkzeug.security import generate_password_hash, check_password_hash
from pymongo import MongoClient
from bson.objectid import ObjectId

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

mongo_client = MongoClient(os.environ["MONGO_URI"])
mongo_db = mongo_client[os.environ.get("MONGO_DB_NAME", "patient_records")]
patients_collection = mongo_db["patients"]
audit_collection = mongo_db["audit_log"]

DATABASE = os.environ.get("DATABASE")


# I want timestamps to be readable in the templates instead of raw ISO format
@app.template_filter("datetimeformat")
def datetimeformat(value):
    try:
        dt = datetime.fromisoformat(value)
        return dt.strftime("%d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return value


# --- SQLite helpers (following Week 6 slides) ---

# I need a way to get a database connection that stays open for the whole request
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
    return g.db


# I should close the database connection when the request is done
@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# I need to create the users table if it doesn't exist yet
def init_db():
    db = get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'clinician',
            created_at TEXT NOT NULL
        )
    """)
    db.commit()


# I want a default admin account so I can log in the first time I run the app
def seed_admin():
    db = get_db()
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", ("admin",)
    ).fetchone()
    if not existing:
        db.execute(
            "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
            (
                "admin",
                generate_password_hash("admin123"),
                "admin",
                datetime.now().isoformat(),
            ),
        )
        db.commit()


# --- CSRF protection ---

# I need to protect my forms against Cross-Site Request Forgery attacks
# I'll generate a random token and store it in the session, then check it on every POST
def generate_csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)
    return session["csrf_token"]


# I'll make the CSRF token available in all templates so I can add it to forms
@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf_token())


# I need to check the CSRF token on every POST request to make sure it's valid
@app.before_request
def check_csrf():
    if request.method == "POST":
        token = session.get("csrf_token")
        form_token = request.form.get("csrf_token")
        if not token or token != form_token:
            flash("Invalid form submission. Please try again.", "error")
            return redirect(request.url)

