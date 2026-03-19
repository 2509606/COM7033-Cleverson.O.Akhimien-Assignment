# Prescription management routes

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.auth.decorators import login_required, role_required
from app.extensions import prescriptions_collection
from app.db import get_db

prescriptions_bp = Blueprint("prescriptions_bp", __name__)


def generate_prescription_id():
    last = prescriptions_collection.find_one(
        {"prescription_id": {"$exists": True}},
        sort=[("prescription_id", -1)],
    )
    if last and last.get("prescription_id"):
        next_num = int(last["prescription_id"].replace("RX", "")) + 1
    else:
        next_num = 1
    return f"RX{str(next_num).zfill(4)}"


@prescriptions_bp.route("/prescriptions")
@login_required
def prescriptions():
    page = request.args.get("page", 1, type=int)
    per_page = 10
    skip = (page - 1) * per_page
    role = session.get("role")

    if role == "patient":
        query = {"patient_user_id": session["user_id"]}
    elif role in ("admin", "doctor", "nurse"):
        query = {}
    else:
        flash("You do not have permission to view prescriptions.", "error")
        return redirect(url_for("main.dashboard"))

    total = prescriptions_collection.count_documents(query)
    total_pages = (total + per_page - 1) // per_page
    rxs = list(
        prescriptions_collection.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    return render_template(
        "prescriptions.html",
        prescriptions=rxs,
        page=page,
        total_pages=total_pages,
        total=total,
    )


@prescriptions_bp.route("/prescription/create", methods=["GET", "POST"])
@login_required
@role_required("doctor")
def create_prescription():
    if request.method == "POST":
        patient_id = request.form.get("patient_user_id", "")
        notes = request.form.get("notes", "").strip()

        # Collect medications
        med_names = request.form.getlist("med_name")
        med_dosages = request.form.getlist("med_dosage")
        med_frequencies = request.form.getlist("med_frequency")
        med_durations = request.form.getlist("med_duration")

        medications = []
        for i in range(len(med_names)):
            name = med_names[i].strip() if i < len(med_names) else ""
            if name:
                medications.append({
                    "name": name,
                    "dosage": med_dosages[i].strip() if i < len(med_dosages) else "",
                    "frequency": med_frequencies[i].strip() if i < len(med_frequencies) else "",
                    "duration": med_durations[i].strip() if i < len(med_durations) else "",
                })

        if not patient_id or not medications:
            flash("Patient and at least one medication are required.", "error")
            return render_template("create_prescription.html", patients=_get_patient_users())

        # Get patient details
        db = get_db()
        patient_user = db.execute("SELECT id, username FROM users WHERE id = ? AND role = 'patient'", (patient_id,)).fetchone()
        if not patient_user:
            flash("Invalid patient selected.", "error")
            return render_template("create_prescription.html", patients=_get_patient_users())

        prescription = {
            "prescription_id": generate_prescription_id(),
            "patient_user_id": patient_user["id"],
            "patient_username": patient_user["username"],
            "doctor_user_id": session["user_id"],
            "doctor_username": session["username"],
            "medications": medications,
            "notes": notes,
            "status": "active",
            "created_at": datetime.now().isoformat(),
        }
        prescriptions_collection.insert_one(prescription)
        flash("Prescription created successfully.", "success")
        return redirect(url_for("prescriptions_bp.prescriptions"))

    return render_template("create_prescription.html", patients=_get_patient_users())


@prescriptions_bp.route("/prescription/<prescription_id>")
@login_required
def view_prescription(prescription_id):
    rx = prescriptions_collection.find_one({"prescription_id": prescription_id})
    if not rx:
        flash("Prescription not found.", "error")
        return redirect(url_for("prescriptions_bp.prescriptions"))

    role = session.get("role")
    if role == "patient" and rx["patient_user_id"] != session["user_id"]:
        flash("You can only view your own prescriptions.", "error")
        return redirect(url_for("prescriptions_bp.prescriptions"))

    return render_template("view_prescription.html", prescription=rx)


@prescriptions_bp.route("/prescription/<prescription_id>/cancel", methods=["POST"])
@login_required
@role_required("doctor", "admin")
def cancel_prescription(prescription_id):
    prescriptions_collection.update_one(
        {"prescription_id": prescription_id},
        {"$set": {"status": "cancelled"}}
    )
    flash("Prescription cancelled.", "success")
    return redirect(url_for("prescriptions_bp.view_prescription", prescription_id=prescription_id))


@prescriptions_bp.route("/prescription/<prescription_id>/complete", methods=["POST"])
@login_required
@role_required("doctor", "admin")
def complete_prescription(prescription_id):
    prescriptions_collection.update_one(
        {"prescription_id": prescription_id},
        {"$set": {"status": "completed"}}
    )
    flash("Prescription marked as completed.", "success")
    return redirect(url_for("prescriptions_bp.view_prescription", prescription_id=prescription_id))


def _get_patient_users():
    db = get_db()
    return db.execute("SELECT id, username FROM users WHERE role = 'patient' AND status = 'approved' ORDER BY username").fetchall()
