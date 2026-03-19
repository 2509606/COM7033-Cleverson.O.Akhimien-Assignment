# Appointment booking and management routes

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.auth.decorators import login_required, role_required
from app.extensions import appointments_collection
from app.db import get_db

appointments_bp = Blueprint("appointments_bp", __name__)


def generate_appointment_id():
    last = appointments_collection.find_one(
        {"appointment_id": {"$exists": True}},
        sort=[("appointment_id", -1)],
    )
    if last and last.get("appointment_id"):
        next_num = int(last["appointment_id"].replace("APT", "")) + 1
    else:
        next_num = 1
    return f"APT{str(next_num).zfill(4)}"


@appointments_bp.route("/appointments")
@login_required
def appointments():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page
    role = session.get("role")

    if role == "patient":
        query = {"patient_user_id": session["user_id"]}
    elif role in ("doctor", "nurse"):
        query = {}
    elif role == "admin":
        query = {}
    else:
        flash("You do not have permission to view appointments.", "error")
        return redirect(url_for("main.dashboard"))

    total = appointments_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    appts = list(
        appointments_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    return render_template(
        "appointments.html",
        appointments=appts,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@appointments_bp.route("/appointment/book", methods=["GET", "POST"])
@login_required
@role_required("patient")
def book_appointment():
    if request.method == "POST":
        date = request.form.get("date", "").strip()
        time = request.form.get("time", "").strip()
        reason = request.form.get("reason", "").strip()
        clinician_id = request.form.get("clinician_id", "")

        if not date or not time or not reason:
            flash("Date, time, and reason are required.", "error")
            return render_template("book_appointment.html", doctors=_get_doctors())

        # Get clinician details
        db = get_db()
        clinician = db.execute("SELECT id, username FROM users WHERE id = ? AND role = 'doctor'", (clinician_id,)).fetchone()
        if not clinician:
            flash("Invalid doctor selected.", "error")
            return render_template("book_appointment.html", doctors=_get_doctors())

        appointment = {
            "appointment_id": generate_appointment_id(),
            "patient_user_id": session["user_id"],
            "patient_username": session["username"],
            "clinician_user_id": clinician["id"],
            "clinician_username": clinician["username"],
            "date": date,
            "time": time,
            "reason": reason,
            "status": "pending",
            "notes": "",
            "created_at": datetime.now().isoformat(),
        }
        appointments_collection.insert_one(appointment)
        flash("Appointment booked successfully.", "success")
        return redirect(url_for("appointments_bp.appointments"))

    return render_template("book_appointment.html", doctors=_get_doctors())


@appointments_bp.route("/appointment/<appointment_id>")
@login_required
def view_appointment(appointment_id):
    appt = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appt:
        flash("Appointment not found.", "error")
        return redirect(url_for("appointments_bp.appointments"))

    role = session.get("role")
    if role == "patient" and appt["patient_user_id"] != session["user_id"]:
        flash("You can only view your own appointments.", "error")
        return redirect(url_for("appointments_bp.appointments"))

    return render_template("view_appointment.html", appointment=appt)


@appointments_bp.route("/appointment/<appointment_id>/confirm", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def confirm_appointment(appointment_id):
    appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"status": "confirmed"}}
    )
    flash("Appointment confirmed.", "success")
    return redirect(url_for("appointments_bp.view_appointment", appointment_id=appointment_id))


@appointments_bp.route("/appointment/<appointment_id>/complete", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def complete_appointment(appointment_id):
    notes = request.form.get("notes", "").strip()
    update = {"status": "completed"}
    if notes:
        update["notes"] = notes
    appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": update}
    )
    flash("Appointment marked as completed.", "success")
    return redirect(url_for("appointments_bp.view_appointment", appointment_id=appointment_id))


@appointments_bp.route("/appointment/<appointment_id>/cancel", methods=["POST"])
@login_required
def cancel_appointment(appointment_id):
    appt = appointments_collection.find_one({"appointment_id": appointment_id})
    if not appt:
        flash("Appointment not found.", "error")
        return redirect(url_for("appointments_bp.appointments"))

    role = session.get("role")
    if role == "patient" and appt["patient_user_id"] != session["user_id"]:
        flash("You can only cancel your own appointments.", "error")
        return redirect(url_for("appointments_bp.appointments"))

    appointments_collection.update_one(
        {"appointment_id": appointment_id},
        {"$set": {"status": "cancelled"}}
    )
    flash("Appointment cancelled.", "success")
    return redirect(url_for("appointments_bp.appointments"))


def _get_doctors():
    db = get_db()
    return db.execute("SELECT id, username FROM users WHERE role = 'doctor' AND status = 'approved' ORDER BY username").fetchall()
