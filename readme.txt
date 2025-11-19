===========================================================
 Project Management & HRMS Backend (FastAPI + MSSQL)
===========================================================

This repository contains the backend services for the 
Project Management System (PMS) and lightweight HRMS module.
The system is built on FastAPI with SQL Server as the data
store, using SQLAlchemy ORM and highly modular API routers.

The backend exposes secure, role-driven endpoints for:
 - User authentication (JWT + Refresh Tokens)
 - Organization structure management 
   (Departments, Sub-Departments, Designations)
 - Project and Sub-Project management
 - Project member assignment
 - Health-check and basic diagnostic utilities

The solution is designed for extensibility, containerization,
and integration with CI/CD pipelines (GitHub / Jenkins).

-----------------------------------------------------------
 1. Technology Stack
-----------------------------------------------------------
• FastAPI  
• Python 3.11+  
• SQLAlchemy 2.0 ORM  
• MSSQL via pyodbc + ODBC Driver 18  
• Pydantic v2  
• JWT Auth (Access + Refresh Tokens)  
• Docker-ready structure  
• Modular Router-based architecture

-----------------------------------------------------------
 2. Directory Structure
-----------------------------------------------------------

/config.py               → Environment configuration loader
/db.py                   → DB engine, ODBC URL builder, SessionLocal

/models/                 → SQLAlchemy models
    auth_user.py
    employee_list.py
    org.py
    projects.py
    sub_projects.py
    project_members.py
    refresh_tokens.py

/schemas/                → Pydantic models (Request/Response DTOs)
    org.py
    projects.py
    sub_projects.py
    project_members.py

/routes/                 → API routers
    auth_router.py
    org_router.py
    projects_router.py
    subprojects_router.py
    api_router.py (misc utilities)

/utils/                 
    security.py          → Hashing, JWT, refresh token utilities
    org_helpers.py       → CRUD helper utilities
    seed.py              → Optional DB seed for SUPER-ADMIN user

/main.py                 → FastAPI app creation, router registration,
                           server startup hooks, health endpoints

.env.example             → Template for environment variables

-----------------------------------------------------------
 3. Core Features
-----------------------------------------------------------

[1] Authentication & Authorization
----------------------------------
• Email/password login with bcrypt_sha256 hashing  
• JWT Access Tokens  
• Rolling Refresh Token mechanism  
• Role-based endpoint access (SUPER-ADMIN, ADMIN, MANAGER, EMPLOYEE)  
• "AUTH_DISABLED" mode for running without security in development  

[2] Organization Management APIs
--------------------------------
• Departments
• Sub-Departments
• Designations
• Tree structure endpoint with designation counts  
• Update + soft validation (name uniqueness, hierarchy constraints)  
• Safe deletes with dependency protection  

[3] Project Management APIs
---------------------------
• Create, update, list, delete projects  
• IST-formatted timestamps via Pydantic field serializers  
• Project members management (add/remove/list)  

[4] Sub-Project Management APIs
-------------------------------
• Fully independent sub-project module  
• CRUD endpoints with project-level filtering  
• Automatic UTC → IST formatting  
• Soft guarded role-based writes  

[5] Diagnostics & Utilities
---------------------------
• /health – system heartbeat  
• /db/ping – DB connectivity check  
• /example-now – MSSQL datetime offset sample  
• Startup logs and database check-in  

-----------------------------------------------------------
 4. Environment Configuration (.env)
-----------------------------------------------------------

Create a `.env` file in the root directory:

DB_DRIVER=ODBC Driver 18 for SQL Server
DB_HOST=localhost
DB_PORT=1433
DB_USER=sa
DB_PASSWORD=YourPassword
DB_NAME=pms
DB_ENCRYPT=true
DB_TRUST_SERVER_CERT=true

JWT_SECRET=your-secret-key
ACCESS_MIN=15
REFRESH_DAYS=15

AUTH_DISABLED=true

USERS_ENDPOINT_ALLOWED=SUPER-ADMIN,ADMIN
USER_GET_ENDPOINT_ALLOWED=SUPER-ADMIN,ADMIN,MANAGER

-----------------------------------------------------------
 5. Running the Server (Local)
-----------------------------------------------------------

1. Create a virtual environment:
   python -m venv .venv
   .venv\Scripts\activate

2. Install dependencies:
   pip install -r requirements.txt

3. Start the API:
   uvicorn main:app --reload --host 0.0.0.0 --port 5000

API will be available at:
http://localhost:5000

Swagger Docs:
http://localhost:5000/docs

-----------------------------------------------------------
 6. Docker Usage
-----------------------------------------------------------

Build:
  docker build -t your-image-name .

Run:
  docker run -d --name pms-backend \
      --env-file .env \
      -p 5000:5000 \
      your-image-name

-----------------------------------------------------------
 7. Database Requirements
-----------------------------------------------------------

• SQL Server 2019+  
• "ODBC Driver 18 for SQL Server" installed on host / container  
• Proper login credentials in `.env`  
• The backend auto-creates ORM tables on startup (metadata.create_all)

-----------------------------------------------------------
 8. Developer Notes
-----------------------------------------------------------

• All datetime fields are stored in UTC at DB level  
• JSON responses return timestamps in IST (+05:30)  
• ORM defaults + DB defaults ensure consistent timestamps  
• Composite primary keys used in project-members table  
• Organization module enforces hierarchical uniqueness  
• Refresh token table supports multiple sessions/devices  

-----------------------------------------------------------
 9. License
-----------------------------------------------------------
Proprietary — internal use only.

-----------------------------------------------------------
 End of README
===========================================================
