# Medical file upload routes

import os
import uuid
from datetime import datetime
from flask import Blueprint, request, redirect, url_for, session, flash, send_from_directory

from app.auth.decorators import login_required, role_required
from app.extensions import medical_files_collection

uploads_bp = Blueprint("uploads_bp", __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "uploads")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".pdf", ".doc", ".docx"}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB


def allowed_file(filename):
    ext = os.path.splitext(filename)[1].lower()
    return ext in ALLOWED_EXTENSIONS


@uploads_bp.route("/patient/<patient_id>/upload", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def upload_file(patient_id):
    if "file" not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))

    file = request.files["file"]
    if file.filename == "":
        flash("No file selected.", "error")
        return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))

    if not allowed_file(file.filename):
        flash("File type not allowed. Allowed: jpg, png, gif, pdf, doc, docx.", "error")
        return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))

    # Check file size
    file.seek(0, 2)
    size = file.tell()
    file.seek(0)
    if size > MAX_FILE_SIZE:
        flash("File is too large. Maximum size is 16MB.", "error")
        return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))

    # Save file with UUID name
    ext = os.path.splitext(file.filename)[1].lower()
    stored_filename = f"{uuid.uuid4().hex}{ext}"
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    file.save(os.path.join(UPLOAD_FOLDER, stored_filename))

    description = request.form.get("description", "").strip()

    medical_files_collection.insert_one({
        "patient_id": patient_id,
        "filename": file.filename,
        "stored_filename": stored_filename,
        "mime_type": file.content_type,
        "file_size": size,
        "description": description,
        "uploaded_by": session["username"],
        "uploaded_at": datetime.now().isoformat(),
    })

    flash("File uploaded successfully.", "success")
    return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))


@uploads_bp.route("/uploads/<stored_filename>")
@login_required
@role_required("admin", "doctor", "nurse")
def serve_file(stored_filename):
    return send_from_directory(UPLOAD_FOLDER, stored_filename)


@uploads_bp.route("/patient/<patient_id>/file/<file_id>/delete", methods=["POST"])
@login_required
@role_required("admin", "doctor")
def delete_file(patient_id, file_id):
    from bson import ObjectId
    record = medical_files_collection.find_one({"_id": ObjectId(file_id)})
    if record:
        filepath = os.path.join(UPLOAD_FOLDER, record["stored_filename"])
        if os.path.exists(filepath):
            os.remove(filepath)
        medical_files_collection.delete_one({"_id": ObjectId(file_id)})
        flash("File deleted.", "success")
    else:
        flash("File not found.", "error")
    return redirect(url_for("patients_bp.view_patient", patient_id=patient_id))
