# AICS Report Hub - Project Explanation

The **AICS Report Hub** is a Django-based web application tailored for managing academic report submissions across multiple campuses (AICS centers). It handles the entire lifecycle of a student's final report—from student registration and supervisor assignment to report upload, preview generation, grading, and public browsing.

## 1. Project Architecture & Core Concepts

### Roles and Permissions
The platform uses a role-based access control system built on a custom user model:
- **Superadmin:** The Django `superuser`. Manages the entire platform and creates `AicsCenter` campuses via the Django Admin.
- **Campus Admin:** Assigned to a specific campus. They register students and supervisors for their campus, and can bulk-assign students to supervisors (up to 15 students per action).
- **Supervisor:** Mentors a group of assigned students. They generate one-time upload codes for their students, review the uploaded reports, grade them, and provide feedback.
- **Student:** Can log into the site. They require a generated one-time code from their supervisor to upload their final PDF report.

### Core Models (`core/models.py`)
- **`AicsCenter`**: Represents the physical campuses.
- **`CustomUser`**: Extends Django's AbstractUser to include a `role` and a link to a specific `center`.
- **Profiles (`SupervisorProfile`, `StudentProfile`)**: Stored separately to attach role-specific metadata like matricule (student ID), level, and specialization for a student.
- **`OneTimeCode`**: A security measure ensuring that students can only upload reports when authorized by their supervisor.
- **`Report`**: Stores the student's submission. The uploaded file is a PDF. When a report is saved, the application relies on `PyMuPDF` (`fitz`) to read the first page of the PDF and automatically generate a `.png` preview image.

### Technology Stack
- **Language/Framework:** Python 3.13 & Django 6.x
- **Dependency Management:** Pipenv
- **Database:** SQLite (default for quick local setup) or PostgreSQL (configured via environment variables `POSTGRES_DB`, `POSTGRES_USER`, etc.)
- **PDF Processing:** `pymupdf`

---

## 2. Command Guide (How to Execute the Project)

Follow these exact steps in your terminal (e.g., PowerShell) to set up and run the application locally.

### Step 1: Open the Project Root
Ensure you are in the directory containing the `Pipfile`.
```powershell
cd "c:\Users\nkeng\Desktop\BIG PROJECTS\IAI-Defense-report-management-\IAI-Defense-report-management-"
```

### Step 2: Install Virtual Environment & Dependencies
The project uses Pipenv. Install dependencies from the `Pipfile`.
```powershell
pipenv install
```

### Step 3: Activate the Virtual Environment
Activate the shell to ensure all Python commands use the installed packages.
```powershell
pipenv shell
```
*(Alternatively, you can prefix the database/django commands with `pipenv run` if you choose not to enter the shell).*

### Step 4: Database Setup & Migrations
Navigate into the Django app directory where `manage.py` is located and apply database migrations to create the required tables in SQLite.
```powershell
cd aics_school
python manage.py migrate
```

### Step 5: Initialize an Admin User
Create the initial Superadmin account to manage campuses. Follow the prompts for username, email, and password.
```powershell
python manage.py createsuperuser
```

### Step 6: Start the Development Server
Run the local server to launch the app.
```powershell
python manage.py runserver
```

### Application URLs:
- **Public & User App Flow:** `http://127.0.0.1:8000/`
- **Superadmin Campus Management:** `http://127.0.0.1:8000/admin/`

---

### Step 7: Initial App Setup (Post-launch Workflow)
Once the server is running:
1. Log in to `http://127.0.0.1:8000/admin/` using your superuser account.
2. Go to **Aics centers** and add a new campus.
3. Use the normal site dashboard (`http://127.0.0.1:8000/`) after setup to manage students, supervisors, and reports.
