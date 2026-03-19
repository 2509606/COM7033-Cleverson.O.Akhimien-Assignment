# Patient Record Management System

A web-based patient record management system built with Flask for the COM7033 Secure Software Development module at Leeds Trinity University.

## Features

- **User Authentication** - Secure login and signup with hashed passwords, role-based access
- **Role-Based Access Control** - Admin, Doctor, Nurse, and Patient roles with granular permissions
- **Patient Record CRUD** - Create, read, update, and archive patient records (MongoDB)
- **Appointments** - Book and manage appointments between patients and doctors
- **Prescriptions** - Create and view prescriptions linked to patients
- **Emergency Contacts** - Patients can manage their own emergency contacts
- **Payments** - Checkout, receipts, and payment history for patients
- **Medical File Uploads** - Upload and manage medical documents and images per patient
- **Admin Panel** - User management, account approvals, audit log, and login history
- **Audit Logging** - All patient actions are logged for accountability
- **CSRF Protection** - All forms protected against cross-site request forgery
- **Search and Pagination** - Dynamic search with input delay and paginated record lists
- **Database Interconnection** - Patient records in MongoDB reference user IDs from SQLite

## Tech Stack

- **Backend:** Flask (Python) with app factory pattern
- **User Database:** SQLite (authentication and user management)
- **Patient Database:** MongoDB (patient records, appointments, prescriptions, audit logs)
- **Frontend:** HTML templates with Jinja2, Tailwind CSS v4
- **Containerisation:** Docker Compose (for MongoDB)

## Project Structure

```
patient-record-management-system/
├── app/
│   ├── __init__.py               # App factory
│   ├── extensions.py             # Flask extensions and MongoDB collections
│   ├── db.py                     # Database configuration
│   ├── admin/                    # User management, approvals, audit log, login history
│   ├── auth/                     # Login, signup, role-based decorators
│   ├── main/                     # Dashboard and sidebar layout
│   ├── patients/                 # Patient CRUD and archive
│   ├── appointments/             # Booking and viewing appointments
│   ├── prescriptions/            # Create and view prescriptions
│   ├── emergency_contacts/       # Emergency contact CRUD
│   ├── payments/                 # Checkout, receipts, payment history
│   └── uploads/                  # Medical file upload and management
├── templates/
│   ├── base.html                 # Shared layout with sidebar navigation
│   ├── login.html                # Login page
│   ├── signup.html               # Self-service signup (pending approval)
│   ├── dashboard.html            # Role-based landing page
│   ├── patients.html             # Patient list with search and pagination
│   ├── add_patient.html          # Add patient form
│   ├── view_patient.html         # View patient details and medical files
│   ├── edit_patient.html         # Edit patient form
│   ├── archived_patients.html    # View and restore archived patients
│   ├── appointments.html         # Appointments list
│   ├── book_appointment.html     # Book appointment form
│   ├── view_appointment.html     # View appointment details
│   ├── prescriptions.html        # Prescriptions list
│   ├── create_prescription.html  # Create prescription form
│   ├── view_prescription.html    # View prescription details
│   ├── emergency_contacts.html   # Emergency contacts list
│   ├── add_contact.html          # Add emergency contact
│   ├── edit_contact.html         # Edit emergency contact
│   ├── payment_history.html      # Payment history
│   ├── checkout.html             # Payment checkout
│   ├── receipt.html              # Payment receipt
│   ├── admin_users.html          # Admin: manage users
│   ├── admin_approvals.html      # Admin: approve pending accounts
│   ├── login_history.html        # Admin: login history
│   ├── audit_log.html            # Admin: audit log
│   └── pagination.html           # Reusable pagination component
├── static/
│   ├── style.css                 # Stylesheet
│   └── logo-*.png                # Branding assets
├── tests/
│   └── test_app.py               # Unit tests
├── uploads/                      # Uploaded medical files (runtime)
├── app.py                        # Application entry point
├── seed_data.py                  # Database seeding script
├── requirements.txt              # Python dependencies
├── docker-compose.yml            # MongoDB container setup
├── .env.example                  # Environment variable template
├── README.md                     # This file
└── SECURITY.md                   # STRIDE threat model and security notes
```

## Installation

### Prerequisites

- Python 3.10+
- Docker and Docker Compose

### Setup

1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd patient-record-management-system
   ```

2. Start MongoDB using Docker:
   ```bash
   docker-compose up -d
   ```

3. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Copy the environment file and configure:
   ```bash
   cp .env.example .env
   ```

5. Run the application:
   ```bash
   python app.py
   ```

6. Open your browser and go to `http://localhost:5000`

### Default Admin Account

- **Username:** admin
- **Password:** admin123

## Running Tests

```bash
pytest tests/
```

## User Roles

| Role | Permissions |
|------|------------|
| **Admin** | Register users, manage users, approve accounts, view audit log, view login history, archive/restore patients, view/edit patients |
| **Doctor** | Add patients, view/edit patients, book appointments, create prescriptions, upload/delete medical files |
| **Nurse** | View patients, view appointments, view prescriptions, view medical files |
| **Patient** | View own appointments, view own prescriptions, manage emergency contacts, make payments, view payment history |

## Database Interconnection

The system uses two databases that work together:

- **SQLite** stores user accounts (id, username, hashed password, role, approval status)
- **MongoDB** stores patient records, appointments, prescriptions, emergency contacts, payments, medical files, and audit logs — each referencing the SQLite user ID via `created_by` or similar fields

This means every record is linked to the user who created it, connecting the two databases.
