# Shared MongoDB collections and helpers used across blueprints

import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING

mongo_client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
mongo_db = mongo_client[os.environ.get("MONGO_DB_NAME", "patient_records")]

patients_collection = mongo_db["patients"]
audit_collection = mongo_db["audit_log"]
login_history_collection = mongo_db["login_history"]
appointments_collection = mongo_db["appointments"]
prescriptions_collection = mongo_db["prescriptions"]
emergency_contacts_collection = mongo_db["emergency_contacts"]
medical_files_collection = mongo_db["medical_files"]
payments_collection = mongo_db["payments"]

# Create indexes for fast lookups
patients_collection.create_index([("patient_id", ASCENDING)])
patients_collection.create_index([("status", ASCENDING)])
appointments_collection.create_index([("patient_user_id", ASCENDING)])
appointments_collection.create_index([("clinician_user_id", ASCENDING)])
prescriptions_collection.create_index([("patient_user_id", ASCENDING)])
emergency_contacts_collection.create_index([("patient_user_id", ASCENDING)])
payments_collection.create_index([("patient_user_id", ASCENDING)])
login_history_collection.create_index([("user_id", ASCENDING)])


def log_action(user_id, username, action, patient_id=None):
    audit_collection.insert_one({
        "user_id": user_id,
        "username": username,
        "action": action,
        "patient_id": str(patient_id) if patient_id else None,
        "timestamp": datetime.now().isoformat(),
    })
