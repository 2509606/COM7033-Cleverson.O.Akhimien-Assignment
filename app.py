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
from pymongo import MongoClient, ASCENDING

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ["SECRET_KEY"]

mongo_client = MongoClient(os.environ["MONGO_URI"])
mongo_db = mongo_client[os.environ.get("MONGO_DB_NAME", "patient_records")]
patients_collection = mongo_db["patients"]
audit_collection = mongo_db["audit_log"]

# Create indexes for fast search
patients_collection.create_index([("patient_id", ASCENDING)])
patients_collection.create_index([("status", ASCENDING)])

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


# --- Auth decorators ---

# I need a way to check if the user is logged in before they can access certain pages
# I'll create a simple decorator that checks the session
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# I also need a decorator for admin-only pages
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "error")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function


# --- Patient validation helper ---

# I need to validate patient form data to make sure nothing invalid gets saved
def validate_patient_form(form):
    errors = []
    age = form.get("age", "").strip()
    blood_pressure = form.get("blood_pressure", "").strip()

    # I should check that age is a number within a reasonable range
    if not age:
        errors.append("Age is required.")
    else:
        try:
            age_int = int(age)
            if age_int < 0 or age_int > 150:
                errors.append("Age must be between 0 and 150.")
        except ValueError:
            errors.append("Age must be a number.")

    if not form.get("sex"):
        errors.append("Sex is required.")

    # I need to make sure blood pressure follows the format like 120/80
    if blood_pressure and not re.match(r"^\d{2,3}/\d{2,3}$", blood_pressure):
        errors.append("Blood pressure must be in the format 120/80.")

    return errors


# --- Patient ID helper ---

# I want a short, readable patient ID (3 digits) instead of exposing the MongoDB ObjectId
# This makes it easier for clinicians to reference patients
def generate_patient_id():
    last = patients_collection.find_one(
        {"patient_id": {"$exists": True}},
        sort=[("patient_id", -1)],
    )
    if last and last.get("patient_id"):
        next_num = int(last["patient_id"]) + 1
    else:
        next_num = 1
    return str(next_num).zfill(3)


# --- Audit log helper ---

# I want to keep track of who does what with patient records
# This helps with accountability and security auditing
def log_action(user_id, username, action, patient_id=None):
    audit_collection.insert_one({
        "user_id": user_id,
        "username": username,
        "action": action,
        "patient_id": str(patient_id) if patient_id else None,
        "timestamp": datetime.now().isoformat(),
    })


# --- Auth routes ---

# The home page should just redirect to the dashboard (or login if not authenticated)
@app.route("/")
def index():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        # I need to check both that the user exists and the password is correct
        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            flash("Logged in successfully.", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("login"))


# Only admins should be able to register new users
@app.route("/register", methods=["GET", "POST"])
@admin_required
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "clinician")

        # I should validate the input before creating a new user
        if not username or not password:
            flash("Username and password are required.", "error")
            return render_template("register.html")

        if role not in ("clinician", "admin"):
            flash("Invalid role selected.", "error")
            return render_template("register.html")

        db = get_db()
        # I need to check if the username already exists
        existing = db.execute(
            "SELECT id FROM users WHERE username = ?", (username,)
        ).fetchone()
        if existing:
            flash("Username already exists.", "error")
            return render_template("register.html")

        db.execute(
            "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
            (
                username,
                generate_password_hash(password),
                role,
                datetime.now().isoformat(),
            ),
        )
        db.commit()
        flash(f"User '{username}' registered successfully.", "success")
        return redirect(url_for("admin_users"))

    return render_template("register.html")


# --- Dashboard ---

@app.route("/dashboard")
@login_required
def dashboard():
    # I want to show different information depending on the user's role
    patient_count = patients_collection.count_documents({"status": "active"})
    return render_template("dashboard.html", patient_count=patient_count)


# --- Patient CRUD routes ---

@app.route("/patients")
@login_required
def patients():
    # I'll show active patients with pagination (10 per page)
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page
    search = request.args.get("search", "").strip()

    query = {"status": "active"}
    if search:
        query["patient_id"] = {"$regex": re.escape(search), "$options": "i"}

    total = patients_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    all_patients = list(
        patients_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )
    total_active = patients_collection.count_documents({"status": "active"})
    total_archived = patients_collection.count_documents({"status": "archived"})
    return render_template(
        "patients.html",
        patients=all_patients,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        total_active=total_active,
        total_archived=total_archived,
    )


@app.route("/patient/add", methods=["GET", "POST"])
@login_required
def add_patient():
    if request.method == "POST":
        # I need to collect all the patient data from the form
        patient = {
            "patient_id": generate_patient_id(),
            "age": request.form.get("age", "").strip(),
            "sex": request.form.get("sex", ""),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "cholesterol": request.form.get("cholesterol", ""),
            "fasting_blood_sugar": request.form.get("fasting_blood_sugar", ""),
            "resting_ecg": request.form.get("resting_ecg", ""),
            "exercise_angina": request.form.get("exercise_angina", ""),
            "created_by": session["user_id"],
            "created_by_name": session["username"],
            "created_at": datetime.now().isoformat(),
            "status": "active",
        }

        # I should validate the form data before saving
        errors = validate_patient_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("add_patient.html")

        patient["age"] = int(patient["age"])

        # Insert the patient record into the MongoDB Database
        patients_collection.insert_one(patient)

        # Log the action using the short readable patient ID
        log_action(session["user_id"], session["username"], "create", patient["patient_id"])
        flash("Patient record added successfully.", "success")
        return redirect(url_for("patients"))

    return render_template("add_patient.html")


@app.route("/patient/<patient_id>")
@login_required
def view_patient(patient_id):
    # I look up by the short readable patient_id field, not the MongoDB ObjectId
    patient = patients_collection.find_one({"patient_id": patient_id})

    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))

    log_action(session["user_id"], session["username"], "view", patient_id)
    return render_template("view_patient.html", patient=patient)


@app.route("/patient/<patient_id>/edit", methods=["GET", "POST"])
@login_required
def edit_patient(patient_id):
    patient = patients_collection.find_one({"patient_id": patient_id})

    if not patient:
        flash("Patient not found.", "error")
        return redirect(url_for("patients"))

    if request.method == "POST":
        # I'll update the patient with the new form data
        updated = {
            "age": request.form.get("age", "").strip(),
            "sex": request.form.get("sex", ""),
            "blood_pressure": request.form.get("blood_pressure", "").strip(),
            "cholesterol": request.form.get("cholesterol", ""),
            "fasting_blood_sugar": request.form.get("fasting_blood_sugar", ""),
            "resting_ecg": request.form.get("resting_ecg", ""),
            "exercise_angina": request.form.get("exercise_angina", ""),
        }

        # I should validate the form data before saving
        errors = validate_patient_form(request.form)
        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("edit_patient.html", patient=patient)

        updated["age"] = int(updated["age"])
        patients_collection.update_one(
            {"patient_id": patient_id},
            {"$set": updated}
        )
        log_action(session["user_id"], session["username"], "edit", patient_id)
        flash("Patient record updated successfully.", "success")
        return redirect(url_for("view_patient", patient_id=patient_id))

    return render_template("edit_patient.html", patient=patient)


# Only admins can archive patient records (soft delete)
@app.route("/patient/<patient_id>/archive", methods=["POST"])
@admin_required
def archive_patient(patient_id):
    result = patients_collection.update_one(
        {"patient_id": patient_id},
        {"$set": {"status": "archived"}}
    )

    if result.modified_count == 0:
        flash("Patient not found.", "error")
    else:
        log_action(session["user_id"], session["username"], "archive", patient_id)
        flash("Patient record archived.", "success")

    return redirect(url_for("patients"))


# --- Admin routes ---

@app.route("/admin/users")
@admin_required
def admin_users():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page
    search = request.args.get("search", "").strip()

    db = get_db()
    if search:
        total = db.execute(
            "SELECT COUNT(*) FROM users WHERE username LIKE ?",
            (f"%{search}%",),
        ).fetchone()[0]
        total_pages = (total + per_page - 1) // per_page
        users = db.execute(
            "SELECT id, username, role, created_at FROM users WHERE username LIKE ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (f"%{search}%", per_page, offset),
        ).fetchall()
    else:
        total = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_pages = (total + per_page - 1) // per_page
        users = db.execute(
            "SELECT id, username, role, created_at FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (per_page, offset),
        ).fetchall()
    total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_admins = db.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'").fetchone()[0]
    total_clinicians = db.execute("SELECT COUNT(*) FROM users WHERE role = 'clinician'").fetchone()[0]
    return render_template(
        "admin_users.html",
        users=users,
        page=page,
        total_pages=total_pages,
        total=total,
        search=search,
        total_users=total_users,
        total_admins=total_admins,
        total_clinicians=total_clinicians,
    )


@app.route("/audit")
@admin_required
def audit_log():
    # I'll show the most recent audit entries at the top with pagination
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page

    total = audit_collection.count_documents({})
    total_pages = (total + per_page - 1) // per_page
    logs = list(
        audit_collection.find()
        .sort("timestamp", -1)
        .skip(skip)
        .limit(per_page)
    )
    return render_template(
        "audit_log.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )


# --- App startup ---

# I need to initialise the database and create the default admin when the app starts
with app.app_context():
    init_db()
    seed_admin()

if __name__ == "__main__":
    app.run(debug=True, port=5001)
