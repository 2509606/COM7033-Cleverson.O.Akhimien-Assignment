# Application factory — creates and configures the Flask app

import os
import secrets
from datetime import datetime
from flask import Flask, session, request, redirect, flash

from dotenv import load_dotenv
load_dotenv()


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")

    # --- Template filter ---
    @app.template_filter("datetimeformat")
    def datetimeformat(value):
        try:
            dt = datetime.fromisoformat(value)
            return dt.strftime("%d %b %Y, %H:%M")
        except (ValueError, TypeError):
            return value

    # --- CSRF protection ---
    def generate_csrf_token():
        if "csrf_token" not in session:
            session["csrf_token"] = secrets.token_hex(16)
        return session["csrf_token"]

    @app.context_processor
    def inject_csrf_token():
        return dict(csrf_token=generate_csrf_token())

    @app.context_processor
    def inject_pending_count():
        """Make pending approval count available to all templates for sidebar badge."""
        count = 0
        if session.get("role") == "admin":
            from app.db import get_db
            try:
                db = get_db()
                count = db.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
            except Exception:
                pass
        return dict(pending_approval_count=count)

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            token = session.get("csrf_token")
            form_token = request.form.get("csrf_token")
            if not token or token != form_token:
                flash("Invalid form submission. Please try again.", "error")
                return redirect(request.url)

    # --- Database teardown ---
    from app.db import close_db, init_db, seed_admin
    app.teardown_appcontext(close_db)

    # --- Register blueprints ---
    from app.auth.routes import auth_bp
    from app.main.routes import main_bp
    from app.patients.routes import patients_bp
    from app.admin.routes import admin_bp
    from app.appointments.routes import appointments_bp
    from app.prescriptions.routes import prescriptions_bp
    from app.emergency_contacts.routes import emergency_contacts_bp
    from app.payments.routes import payments_bp
    from app.uploads.routes import uploads_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(patients_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(appointments_bp)
    app.register_blueprint(prescriptions_bp)
    app.register_blueprint(emergency_contacts_bp)
    app.register_blueprint(payments_bp)
    app.register_blueprint(uploads_bp)

    # --- Initialize database ---
    with app.app_context():
        init_db()
        seed_admin()

    return app
