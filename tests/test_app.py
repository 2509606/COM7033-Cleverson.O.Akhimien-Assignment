# I need to test that the key features of my app work correctly
# I'll use Flask's built-in test client so I don't need a real server running
# Since MongoDB might not be running during tests, I'll mock the MongoDB calls

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock
import pytest

# I need to add the project root to the path so I can import app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# I need to mock MongoDB before importing the app so it doesn't try to connect
mock_patients = MagicMock()
mock_audit = MagicMock()
mock_patients.count_documents.return_value = 0


def _make_find_chain(data=None):
    """Build a mock chain for .find().sort().skip().limit() that returns data."""
    if data is None:
        data = []
    chain = MagicMock()
    chain.sort.return_value = chain
    chain.skip.return_value = chain
    chain.limit.return_value = data
    chain.__iter__ = lambda self: iter(data)
    return chain


mock_patients.find.return_value = _make_find_chain()

with patch("pymongo.MongoClient") as mock_mongo:
    mock_db = MagicMock()
    mock_mongo.return_value.__getitem__.return_value = mock_db
    mock_db.__getitem__.side_effect = lambda name: mock_patients if name == "patients" else mock_audit

    from app import app, get_db, init_db
    import app as app_module

from werkzeug.security import generate_password_hash

# I'll point the mock collections to the app module so routes use them
app_module.patients_collection = mock_patients
app_module.audit_collection = mock_audit


@pytest.fixture(autouse=True)
def reset_mocks():
    # I want to reset mock call counts between tests
    mock_patients.reset_mock()
    mock_audit.reset_mock()
    mock_patients.count_documents.return_value = 0
    mock_patients.find.return_value = _make_find_chain()
    mock_patients.find_one.return_value = None
    mock_patients.insert_one.return_value = MagicMock(inserted_id="fake_id")
    mock_patients.update_one.return_value = MagicMock(modified_count=1)


@pytest.fixture
def client():
    # I'll use a temporary database for testing so I don't mess up real data
    app.config["TESTING"] = True
    db_fd, db_path = tempfile.mkstemp()

    original_db = app_module.DATABASE
    app_module.DATABASE = db_path

    with app.test_client() as client:
        with app.app_context():
            init_db()
            # I'll create a test admin and clinician user
            db = get_db()
            db.execute(
                "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                ("testadmin", generate_password_hash("password123"), "admin", "2024-01-01"),
            )
            db.execute(
                "INSERT INTO users (username, password, role, created_at) VALUES (?, ?, ?, ?)",
                ("testclinician", generate_password_hash("password123"), "clinician", "2024-01-01"),
            )
            db.commit()
        yield client

    app_module.DATABASE = original_db
    os.close(db_fd)
    os.unlink(db_path)


def login(client, username, password):
    # I need a helper function to log in during tests
    # First get the login page to get a CSRF token
    response = client.get("/login")
    html = response.data.decode()
    token_start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    token_end = html.find('"', token_start)
    csrf_token = html[token_start:token_end]

    return client.post("/login", data={
        "username": username,
        "password": password,
        "csrf_token": csrf_token,
    }, follow_redirects=True)


def get_csrf(client):
    """Get a CSRF token from the session by hitting the add patient page."""
    response = client.get("/patient/add")
    html = response.data.decode()
    token_start = html.find('name="csrf_token" value="') + len('name="csrf_token" value="')
    token_end = html.find('"', token_start)
    return html[token_start:token_end]


# ========== Auth tests ==========

# Test 1: Home page should redirect to login when not logged in
def test_home_redirects_to_login(client):
    response = client.get("/")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Test 2: Login page should load successfully
def test_login_page_loads(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Login" in response.data


# Test 3: Register page should load when logged in as admin
def test_register_page_loads_for_admin(client):
    login(client, "testadmin", "password123")
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Register" in response.data


# Test 4: Login with valid credentials should work
def test_login_valid_credentials(client):
    response = login(client, "testadmin", "password123")
    assert response.status_code == 200
    assert b"Dashboard" in response.data


# Test 5: Login with invalid credentials should fail
def test_login_invalid_credentials(client):
    response = login(client, "testadmin", "wrongpassword")
    assert b"Invalid username or password" in response.data


# Test 6: Dashboard should require login
def test_dashboard_requires_login(client):
    response = client.get("/dashboard")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# Test 7: Logout should clear the session
def test_logout_clears_session(client):
    login(client, "testadmin", "password123")
    response = client.get("/logout", follow_redirects=True)
    assert b"Login" in response.data
    # I should verify that the dashboard is no longer accessible
    response = client.get("/dashboard")
    assert response.status_code == 302


# Test 8: Patient add page should require login
def test_add_patient_requires_login(client):
    response = client.get("/patient/add")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


# ========== Patient ID generation tests ==========

# Test 9: First patient should get ID "001"
def test_generate_patient_id_first(client):
    mock_patients.find_one.return_value = None
    with app.app_context():
        pid = app_module.generate_patient_id()
    assert pid == "001"


# Test 10: Sequential patient ID increments correctly
def test_generate_patient_id_increments(client):
    mock_patients.find_one.return_value = {"patient_id": "005"}
    with app.app_context():
        pid = app_module.generate_patient_id()
    assert pid == "006"


# Test 11: Patient ID is zero-padded to 3 digits
def test_generate_patient_id_zero_padded(client):
    mock_patients.find_one.return_value = {"patient_id": "099"}
    with app.app_context():
        pid = app_module.generate_patient_id()
    assert pid == "100"


# ========== Patient CRUD with short ID ==========

# Test 12: Adding a patient should store the short patient_id
def test_add_patient_stores_short_id(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = None  # no existing patients

    csrf = get_csrf(client)
    client.post("/patient/add", data={
        "csrf_token": csrf,
        "age": "45",
        "sex": "Male",
        "blood_pressure": "120/80",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
    }, follow_redirects=True)

    # Verify insert_one was called with patient_id "001"
    mock_patients.insert_one.assert_called_once()
    saved = mock_patients.insert_one.call_args[0][0]
    assert saved["patient_id"] == "001"
    assert saved["age"] == 45
    assert saved["status"] == "active"


# Test 13: View patient should look up by short patient_id
def test_view_patient_by_short_id(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = {
        "_id": "mongo_obj_id",
        "patient_id": "001",
        "age": 45,
        "sex": "Male",
        "blood_pressure": "120/80",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
        "created_by": 1,
        "created_by_name": "testadmin",
        "created_at": "2024-01-01T00:00:00",
        "status": "active",
    }

    response = client.get("/patient/001")
    assert response.status_code == 200
    assert b"001" in response.data
    # Verify it looked up by patient_id, not _id
    mock_patients.find_one.assert_called_with({"patient_id": "001"})


# Test 14: View patient with non-existent ID should redirect
def test_view_patient_not_found(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = None

    response = client.get("/patient/999")
    assert response.status_code == 302
    assert "/patients" in response.headers["Location"]


# Test 15: Edit patient should look up by short patient_id
def test_edit_patient_by_short_id(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = {
        "_id": "mongo_obj_id",
        "patient_id": "002",
        "age": 30,
        "sex": "Female",
        "blood_pressure": "110/70",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
        "created_by": 1,
        "created_by_name": "testadmin",
        "created_at": "2024-01-01T00:00:00",
        "status": "active",
    }

    response = client.get("/patient/002/edit")
    assert response.status_code == 200
    assert b"Edit Patient" in response.data
    mock_patients.find_one.assert_called_with({"patient_id": "002"})


# Test 16: Editing a patient should update by short patient_id
def test_edit_patient_post_updates(client):
    login(client, "testadmin", "password123")
    mock_patients.find_one.return_value = {
        "_id": "mongo_obj_id",
        "patient_id": "002",
        "age": 30,
        "sex": "Female",
        "blood_pressure": "110/70",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
        "created_by": 1,
        "created_by_name": "testadmin",
        "created_at": "2024-01-01T00:00:00",
        "status": "active",
    }

    csrf = get_csrf(client)
    response = client.post("/patient/002/edit", data={
        "csrf_token": csrf,
        "age": "31",
        "sex": "Female",
        "blood_pressure": "115/75",
        "cholesterol": "Normal",
        "fasting_blood_sugar": "No",
        "resting_ecg": "Normal",
        "exercise_angina": "No",
    }, follow_redirects=False)

    assert response.status_code == 302
    mock_patients.update_one.assert_called_once()
    call_args = mock_patients.update_one.call_args
    assert call_args[0][0] == {"patient_id": "002"}
    assert call_args[0][1]["$set"]["age"] == 31


# Test 17: Archive patient should use short patient_id
def test_archive_patient_by_short_id(client):
    login(client, "testadmin", "password123")

    csrf = get_csrf(client)
    response = client.post("/patient/003/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=False)

    assert response.status_code == 302
    mock_patients.update_one.assert_called_once_with(
        {"patient_id": "003"},
        {"$set": {"status": "archived"}},
    )


# Test 18: Archive should log the short patient_id in audit
def test_archive_logs_short_id(client):
    login(client, "testadmin", "password123")

    csrf = get_csrf(client)
    client.post("/patient/007/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=True)

    mock_audit.insert_one.assert_called_once()
    logged = mock_audit.insert_one.call_args[0][0]
    assert logged["patient_id"] == "007"
    assert logged["action"] == "archive"


# ========== Pagination tests ==========

# Test 19: Patients page should pass pagination params
def test_patients_pagination_params(client):
    login(client, "testadmin", "password123")
    mock_patients.count_documents.return_value = 25

    response = client.get("/patients?page=2")
    assert response.status_code == 200

    # Verify skip/limit were called for page 2
    find_chain = mock_patients.find.return_value
    find_chain.sort.return_value.skip.assert_called_with(10)
    find_chain.sort.return_value.skip.return_value.limit.assert_called_with(10)


# Test 20: Patients page defaults to page 1
def test_patients_defaults_to_page_one(client):
    login(client, "testadmin", "password123")
    mock_patients.count_documents.return_value = 5

    response = client.get("/patients")
    assert response.status_code == 200

    find_chain = mock_patients.find.return_value
    find_chain.sort.return_value.skip.assert_called_with(0)


# Test 21: Admin users page should paginate
def test_admin_users_pagination(client):
    login(client, "testadmin", "password123")

    response = client.get("/admin/users?page=1")
    assert response.status_code == 200
    # The page should contain user rows (testadmin, testclinician are in the DB)
    assert b"testadmin" in response.data


# Test 22: Audit log page should paginate
def test_audit_log_pagination(client):
    login(client, "testadmin", "password123")
    mock_audit.count_documents.return_value = 15
    mock_audit.find.return_value = _make_find_chain([])

    response = client.get("/audit?page=1")
    assert response.status_code == 200


# ========== Clinician access tests ==========

# Test 23: Clinician should not be able to archive patients
def test_clinician_cannot_archive(client):
    login(client, "testclinician", "password123")

    csrf = get_csrf(client)
    response = client.post("/patient/001/archive", data={
        "csrf_token": csrf,
    }, follow_redirects=False)

    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
    mock_patients.update_one.assert_not_called()


# Test 24: Clinician should not access admin users page
def test_clinician_cannot_access_admin_users(client):
    login(client, "testclinician", "password123")
    response = client.get("/admin/users")
    assert response.status_code == 302
    assert "/dashboard" in response.headers["Location"]
