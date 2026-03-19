# Emergency contacts management routes (patient-only)

from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, session, flash

from app.auth.decorators import login_required, role_required
from app.extensions import emergency_contacts_collection

emergency_contacts_bp = Blueprint("emergency_contacts_bp", __name__)

MAX_CONTACTS = 2


@emergency_contacts_bp.route("/emergency-contacts")
@login_required
@role_required("patient")
def emergency_contacts():
    contacts = list(
        emergency_contacts_collection.find({"patient_user_id": session["user_id"]})
        .sort("created_at", -1)
    )
    return render_template("emergency_contacts.html", contacts=contacts, max_contacts=MAX_CONTACTS)


@emergency_contacts_bp.route("/emergency-contact/add", methods=["GET", "POST"])
@login_required
@role_required("patient")
def add_contact():
    count = emergency_contacts_collection.count_documents({"patient_user_id": session["user_id"]})
    if count >= MAX_CONTACTS:
        flash(f"You can only have up to {MAX_CONTACTS} emergency contacts.", "error")
        return redirect(url_for("emergency_contacts_bp.emergency_contacts"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        relationship = request.form.get("relationship", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not relationship or not phone:
            flash("Name, relationship, and phone are required.", "error")
            return render_template("add_contact.html")

        emergency_contacts_collection.insert_one({
            "patient_user_id": session["user_id"],
            "name": name,
            "relationship": relationship,
            "phone": phone,
            "email": email,
            "created_at": datetime.now().isoformat(),
        })
        flash("Emergency contact added.", "success")
        return redirect(url_for("emergency_contacts_bp.emergency_contacts"))

    return render_template("add_contact.html")


@emergency_contacts_bp.route("/emergency-contact/<contact_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("patient")
def edit_contact(contact_id):
    from bson import ObjectId
    contact = emergency_contacts_collection.find_one({
        "_id": ObjectId(contact_id),
        "patient_user_id": session["user_id"],
    })
    if not contact:
        flash("Contact not found.", "error")
        return redirect(url_for("emergency_contacts_bp.emergency_contacts"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        relationship = request.form.get("relationship", "").strip()
        phone = request.form.get("phone", "").strip()
        email = request.form.get("email", "").strip()

        if not name or not relationship or not phone:
            flash("Name, relationship, and phone are required.", "error")
            return render_template("edit_contact.html", contact=contact)

        emergency_contacts_collection.update_one(
            {"_id": ObjectId(contact_id)},
            {"$set": {"name": name, "relationship": relationship, "phone": phone, "email": email}}
        )
        flash("Emergency contact updated.", "success")
        return redirect(url_for("emergency_contacts_bp.emergency_contacts"))

    return render_template("edit_contact.html", contact=contact)


@emergency_contacts_bp.route("/emergency-contact/<contact_id>/delete", methods=["POST"])
@login_required
@role_required("patient")
def delete_contact(contact_id):
    from bson import ObjectId
    emergency_contacts_collection.delete_one({
        "_id": ObjectId(contact_id),
        "patient_user_id": session["user_id"],
    })
    flash("Emergency contact removed.", "success")
    return redirect(url_for("emergency_contacts_bp.emergency_contacts"))
