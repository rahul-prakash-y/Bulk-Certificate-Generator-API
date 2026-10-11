# Bulk Certificate Generator API

A FastAPI backend that accepts bulk certificate generation requests, generates PDF certificates from a predefined template, tracks job status, and allows retrieval of generated certificates.

---

## Prerequisites

- Python 3.12+
- Windows PowerShell (commands below are Windows-native)

---

## Setup (Windows)

```powershell
# 1. Clone the repository
git clone https://github.com/rahul-prakash-y/Bulk-Certificate-Generator-API.git
cd Bulk-Certificate-Generator-API

# 2. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional — defaults work for local dev)
copy .env.example .env
# Edit .env if you want to change DATABASE_URL, port, etc.
```

---

## Run the Application

```powershell
# Activate venv if not already active
.venv\Scripts\Activate.ps1

# Start the development server with auto-reload
uvicorn bulk_cert_api.main:app --reload

# Or via the module entry point
python -m bulk_cert_api.main
```

The API will be available at:
- **API base:** `http://localhost:8000`
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`
- **Health check:** `http://localhost:8000/health`

---

## Run Tests

```powershell
.venv\Scripts\Activate.ps1
pytest -v
```

---

## API Usage

### Submit a certificate generation job

```http
POST /jobs
Content-Type: application/json

{
  "event_name": "Python Workshop 2025",
  "issued_date": "2025-10-11",
  "recipients": [
    { "name": "Alice Smith", "email": "alice@example.com" },
    { "name": "Bob Jones",   "email": "bob@example.com" }
  ]
}
```

Response `202 Accepted`:
```json
{ "job_id": "<uuid>", "status": "completed", "total": 2, "succeeded": 2, "failed": 0 }
```

### Check job status / progress

```http
GET /jobs/{job_id}
```

### Download a certificate PDF

```http
GET /certificates/{recipient_id}
```

Returns the PDF file as `application/pdf`.

### Download all certificates as a ZIP archive

```http
GET /jobs/{job_id}/archive
```

Returns a ZIP file containing all successfully generated certificates for the job.

---

## Design Decisions

### 1. Synchronous processing within the POST /jobs request
Generation is performed synchronously inside the request handler using a per-recipient `try/except` loop.

**Why:** Meets all mandatory requirements without infrastructure overhead (no Redis, no Celery, no message broker). The job-service layer is deliberately isolated so it can be moved to a `BackgroundTasks` callback or a Celery worker with zero schema changes.

**Trade-off:** Long-running jobs will hold the HTTP connection open. Acceptable for the scope of this assignment; noted for future improvement.

### 2. SQLite + SQLAlchemy (async)
SQLite is used for local development — zero configuration, file-based. Switching to PostgreSQL requires only a `DATABASE_URL` change in `.env`; no application code changes needed.

### 3. PDF generation via ReportLab
Pure-Python, no system dependencies (no Chromium, no LibreOffice). Produces production-quality PDFs. The single predefined certificate template is defined entirely in code.

### 4. Failure isolation
Each recipient is wrapped in its own `try/except`. A PDF generation failure records the error on the `Recipient` row and continues to the next recipient. The `Job` record tracks `succeeded` and `failed` counts.

### 5. Storage
Generated PDFs are stored in a local `generated_certificates/` directory (configurable via `CERTIFICATES_DIR` in `.env`). The directory is created automatically on startup.

---

## Project Structure

```
bulk_cert_api/
├── main.py                   # App factory, lifespan, startup
├── config.py                 # Settings (pydantic-settings / .env)
├── database.py               # SQLAlchemy engine + session factory
├── models/                   # ORM models (Job, Recipient)
├── schemas/                  # Pydantic request/response schemas
├── routers/                  # FastAPI route handlers
│   ├── health.py             # GET /health
│   ├── jobs.py               # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/archive
│   └── certificates.py       # GET /certificates/{recipient_id}
└── services/                 # Business logic
    ├── certificate_service.py # ReportLab PDF generator
    └── job_service.py        # Job orchestration & error isolation
tests/
├── conftest.py               # Shared fixtures & test database
├── test_certificates.py      # Unit tests for ReportLab PDF rendering
├── test_certificates_api.py  # Integration tests for certificate downloads
├── test_health.py            # Health check & documentation tests
├── test_jobs.py              # Job creation, polling, archive ZIP tests
├── test_security_boundary.py # Security & boundary condition tests
└── test_validation.py        # Pydantic schema validation tests
```
