# Data seeding script — populates MongoDB with sample patient records
# Uses Faker for realistic names and the UCI Heart Disease dataset structure
# Run with: python seed_data.py

import os
import random
from datetime import datetime, timedelta

from dotenv import load_dotenv
from faker import Faker
from pymongo import MongoClient

load_dotenv()

fake = Faker()

mongo_client = MongoClient(os.environ.get("MONGO_URI", "mongodb://localhost:27017/"))
mongo_db = mongo_client[os.environ.get("MONGO_DB_NAME", "patient_records")]
patients_collection = mongo_db["patients"]

CHOLESTEROL_OPTIONS = ["Normal", "Above Normal", "High"]
ECG_OPTIONS = ["Normal", "Abnormal"]
YES_NO = ["Yes", "No"]
SEX_OPTIONS = ["Male", "Female"]

NUM_RECORDS = 50


def seed_patients():
    # Get the current highest patient_id
    last = patients_collection.find_one(
        {"patient_id": {"$exists": True}},
        sort=[("patient_id", -1)],
    )
    start_num = int(last["patient_id"]) + 1 if last and last.get("patient_id") else 1

    records = []
    for i in range(NUM_RECORDS):
        pid = str(start_num + i).zfill(3)
        age = random.randint(25, 85)
        systolic = random.randint(90, 180)
        diastolic = random.randint(60, 110)
        created_at = (datetime.now() - timedelta(days=random.randint(0, 365))).isoformat()

        records.append({
            "patient_id": pid,
            "age": age,
            "sex": random.choice(SEX_OPTIONS),
            "blood_pressure": f"{systolic}/{diastolic}",
            "cholesterol": random.choice(CHOLESTEROL_OPTIONS),
            "fasting_blood_sugar": random.choice(YES_NO),
            "resting_ecg": random.choice(ECG_OPTIONS),
            "exercise_angina": random.choice(YES_NO),
            "created_by": 1,
            "created_by_name": "admin",
            "created_at": created_at,
            "status": "active",
        })

    if records:
        patients_collection.insert_many(records)
        print(f"Seeded {len(records)} patient records (IDs {records[0]['patient_id']} - {records[-1]['patient_id']}).")
    else:
        print("No records to seed.")


if __name__ == "__main__":
    seed_patients()
