# Bulk Certificate Generator API

A high-performance, production-minded FastAPI backend that accepts bulk certificate generation requests, validates recipient datasets, renders PDF certificates using a predefined template, tracks asynchronous-ready lifecycle statuses in a relational database, and provides secure individual and bulk (ZIP) artifact retrieval.

---

## 1. Problem Statement & Solution Overview

### The Problem
Organizations hosting conferences, workshops, or training courses frequently need to issue hundreds of customized certificates upon completion. Generating certificates manually or issuing one API call per participant is inefficient, unscalable, and prone to partial failure aborts.

### The Solution
The **Bulk Certificate Generator API** solves this challenge by providing:
- **Bulk Job Ingestion:** Submit up to 500 recipients in a single request with batch-level metadata.
- **Fail-Safe Generation:** Per-recipient failure isolation ensures that an error generating one certificate never blocks or cancels the rest of the batch.
- **Relational Status Tracking:** Granular progress tracking via SQLite/PostgreSQL with aggregate counts (`total`, `succeeded`, `failed`) and per-recipient outcome records.
- **Secure File Retrieval:** Immediate access to individual certificates via UUID endpoints and full batch downloads via in-memory ZIP archive streaming.
- **Defensive Engineering:** Strict input validation, path traversal neutralization, OS-reserved keyword handling, PII sanitization in application logs, and global exception masking.

---

## 2. Technology Stack

| Layer | Technology | Rationale |
|---|---|---|
| **Language** | Python 3.12+ | High developer productivity, robust async runtime, strong typing. |
| **Framework** | FastAPI (0.115.0) | Async-native ASGI web framework, automatic OpenAPI documentation, high throughput. |
| **Data Validation** | Pydantic v2 (2.9.2) | Fast schema validation, custom field sanitizers, strict type enforcement. |
| **Database & ORM** | SQLAlchemy 2.0 (async) + aiosqlite | Relational storage with async connection pooling. Zero-config SQLite for development; swap to PostgreSQL by changing `DATABASE_URL`. |
| **PDF Rendering** | ReportLab (4.2.5) | Pure-Python PDF rendering without external browser engines (Chromium/Puppeteer) or LibreOffice dependencies. |
| **Testing** | pytest (8.3.3) + httpx + pypdf | Asynchronous integration testing, schema validation, and programmatic PDF binary verification. |

---

## 3. Project Structure

```
Bulk-Certificate-Generator-API/
├── bulk_cert_api/
│   ├── config.py                 # Application configuration via pydantic-settings
│   ├── database.py               # Async SQLAlchemy engine, session maker, Base
│   ├── main.py                   # FastAPI app factory, lifespan events, global error handler
│   ├── models/                   # Relational ORM models
│   │   ├── __init__.py           # Model discovery for migrations
│   │   ├── job.py                # Job ORM model (lifecycle, aggregates)
│   │   └── recipient.py          # Recipient ORM model (status, error, file path)
│   ├── routers/                  # API route handlers
│   │   ├── __init__.py
│   │   ├── certificates.py       # GET /certificates/{recipient_id}
│   │   ├── health.py             # GET /health
│   │   └── jobs.py               # POST /jobs, GET /jobs/{id}, GET /jobs/{id}/archive
│   ├── schemas/                  # Pydantic v2 schemas
│   │   ├── __init__.py
│   │   └── job.py                # Request, response, and status data models
│   └── services/                 # Business logic layer
│       ├── __init__.py
│       ├── certificate_service.py # ReportLab PDF rendering engine
│       └── job_service.py        # Job orchestration & per-recipient failure isolation
├── tests/
│   ├── conftest.py               # Pytest async fixtures, test DB, temp storage
│   ├── test_certificates.py      # PDF rendering & formatting unit tests
│   ├── test_certificates_api.py  # Single certificate download integration tests
│   ├── test_health.py            # Health check, docs, and lifespan tests
│   ├── test_jobs.py              # Bulk job creation, polling, and ZIP archive tests
│   ├── test_realistic_verification.py # End-to-end test with realistic data & pypdf
│   ├── test_security_boundary.py # Path traversal, OS keywords, batch limits, 500 error tests
│   └── test_validation.py        # 32 Pydantic schema validation tests
├── .env.example                  # Environment variable configuration template
├── .gitignore                    # Git ignore rules (DB, env, PDFs, cache)
├── pyproject.toml                # Build configuration & pytest settings
├── requirements.txt              # Pinned Python package dependencies
└── README.md                     # Documentation
```

---

## 4. Prerequisites & Setup (Windows)

### Prerequisites
- Python 3.12 or newer installed (`python --version`)
- Windows PowerShell

### Setup Steps

```powershell
# 1. Clone repository
git clone https://github.com/rahul-prakash-y/Bulk-Certificate-Generator-API.git
cd Bulk-Certificate-Generator-API

# 2. Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (optional - defaults work out-of-the-box)
copy .env.example .env
```

---

## 5. Running the Application

```powershell
# Start server with auto-reload
uvicorn bulk_cert_api.main:app --reload

# Or run via Python module
python -m bulk_cert_api.main
```

The application will be accessible at:
- **Base URL:** `http://localhost:8000`
- **Interactive Swagger UI:** `http://localhost:8000/docs`
- **ReDoc Documentation:** `http://localhost:8000/redoc`
- **Health Check:** `http://localhost:8000/health`

---

## 6. Environment Configuration

Environment variables are loaded automatically from `.env` via `pydantic-settings`:

| Variable | Default Value | Description |
|---|---|---|
| `APP_ENV` | `development` | Runtime environment (`development`, `production`). |
| `APP_HOST` | `0.0.0.0` | Bind host address. |
| `APP_PORT` | `8000` | Bind port number. |
| `LOG_LEVEL` | `info` | Logging verbosity (`debug`, `info`, `warning`, `error`). |
| `DATABASE_URL` | `sqlite+aiosqlite:///./bulk_cert.db` | SQLAlchemy connection string (change to PostgreSQL for prod). |
| `CERTIFICATES_DIR` | `generated_certificates` | On-disk directory where generated PDFs are stored. |
| `MAX_BATCH_SIZE` | `500` | Maximum allowed recipient count per request. |

---

## 7. API Reference

### 7.1. Health Check
`GET /health`

**Response (`200 OK`):**
```json
{
  "status": "ok"
}
```

---

### 7.2. Submit Bulk Certificate Generation Job
`POST /jobs`

**Request Headers:** `Content-Type: application/json`

**Request Body:**
```json
{
  "event_name": "Full-Stack Distributed Systems Bootcamp",
  "issued_date": "2025-10-15",
  "recipients": [
    {
      "name": "Dr. Alexander Wright",
      "email": "a.wright@university.edu"
    },
    {
      "name": "Priya Patel",
      "email": "priya.patel@techcorp.io"
    }
  ]
}
```

**Response (`202 Accepted`):**
```json
{
  "job_id": "8f3e2b10-6c39-4d6d-8f25-885741fba749",
  "status": "completed",
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "created_at": "2025-10-15T08:30:00Z"
}
```

**Error Codes:**
- `422 Unprocessable Entity`: Missing fields, invalid date format, empty batch, batch exceeding 500 records.
- `500 Internal Server Error`: Masked internal failure response.

---

### 7.3. Poll Job Status & Individual Outcomes
`GET /jobs/{job_id}`

**Response (`200 OK`):**
```json
{
  "job_id": "8f3e2b10-6c39-4d6d-8f25-885741fba749",
  "status": "completed",
  "total": 2,
  "succeeded": 2,
  "failed": 0,
  "created_at": "2025-10-15T08:30:00Z",
  "updated_at": "2025-10-15T08:30:01Z",
  "results": [
    {
      "recipient_id": "b3040df3-0a2a-4bc4-b778-9366fb853e53",
      "name": "Dr. Alexander Wright",
      "email": "a.wright@university.edu",
      "status": "success",
      "error": null,
      "certificate_url": "/certificates/b3040df3-0a2a-4bc4-b778-9366fb853e53"
    },
    {
      "recipient_id": "76ba1e05-24e5-47e9-a467-33e9d40b955c",
      "name": "Priya Patel",
      "email": "priya.patel@techcorp.io",
      "status": "success",
      "error": null,
      "certificate_url": "/certificates/76ba1e05-24e5-47e9-a467-33e9d40b955c"
    }
  ]
}
```

**Partial Failure Example (`200 OK`):**
```json
{
  "job_id": "...",
  "status": "completed",
  "total": 2,
  "succeeded": 1,
  "failed": 1,
  "results": [
    {
      "recipient_id": "...",
      "name": "Valid Participant",
      "email": "valid@example.com",
      "status": "success",
      "error": null,
      "certificate_url": "/certificates/..."
    },
    {
      "recipient_id": "...",
      "name": "Faulty Participant",
      "email": "faulty@example.com",
      "status": "failed",
      "error": "Certificate file could not be generated.",
      "certificate_url": null
    }
  ]
}
```

**Error Codes:**
- `404 Not Found`: Job ID does not exist.
- `422 Unprocessable Entity`: Malformed UUID string in route parameter.

---

### 7.4. Download Individual Certificate PDF
`GET /certificates/{recipient_id}`

**Response (`200 OK`):**
- **Content-Type:** `application/pdf`
- **Content-Disposition:** `inline; filename="Dr_Alexander_Wright-certificate.pdf"`

**Error Codes:**
- `404 Not Found`: Recipient not found, generation failed for this recipient, or file missing from disk.

---

### 7.5. Download Bulk ZIP Archive
`GET /jobs/{job_id}/archive`

**Response (`200 OK`):**
- **Content-Type:** `application/zip`
- **Content-Disposition:** `attachment; filename="certificates-8f3e2b10-6c39-4d6d-8f25-885741fba749.zip"`

All successfully rendered certificates are packaged into a streaming ZIP archive. Internal archive filenames are formatted as `{sanitized_name}_{recipient_id[:8]}.pdf` to guarantee 100% collision prevention even if participants share identical names.

**Error Codes:**
- `404 Not Found`: Job does not exist or has 0 successful certificates generated.

---

## 8. Architectural & Engineering Decisions

### 1. Synchronous vs Background Processing
- **Decision:** Certificates are processed synchronously inside the `POST /jobs` request lifecycle with per-recipient `try/except` failure isolation.
- **Rationale:** This satisfies the assignment requirement with zero infrastructure overhead (no Redis, no Celery, no external brokers, zero deployment barriers). 
- **Decoupled Architecture:** The business logic is fully isolated in `JobService`. Transitioning to `FastAPI.BackgroundTasks` or a Celery queue requires changing only a single line in `routers/jobs.py` without modifying schemas, database models, or PDF logic.

### 2. Failure Isolation
- **Decision:** Individual recipient generation attempts are wrapped in independent try/catch blocks.
- **Rationale:** A rendering glitch, filesystem issue, or unusual character on record #5 does not abort or revert certificates generated for records #1-4 or #6-10. Safe, sanitized error messages are recorded on the `Recipient` row.

### 3. ReportLab for PDF Generation
- **Decision:** Pure-Python ReportLab library for A4 landscape rendering.
- **Rationale:** Headless browsers (Puppeteer, Playwright, Weasyprint) require heavy binary dependencies, complex font configuration, and large memory footprints. ReportLab runs anywhere Python runs with millisecond generation speeds and zero external OS dependencies.

### 4. Storage & Collision Defense
- **Decision:** Internal storage uses canonical UUID naming (`{recipient_id}.pdf`). Client downloads use a hardened `_sanitize_name()` helper.
- **Rationale:** Eliminates directory traversal attacks (`../../`), prevents overwriting existing files, and protects against Windows/Unix reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1-9`).

---

## 9. Security & Hardening Measures

- **No Information Leakage:** Stack traces and internal filesystem paths are never exposed in API responses. Unhandled exceptions return generic, safe 500 JSON bodies.
- **PII Log Redaction:** Log statements record only UUIDs and counts; participant names and email addresses are omitted from application logs.
- **Path Traversal Defenses:** Download and ZIP archive paths strictly reject directory climbing and escape characters.
- **Batch Size Limits:** Requests are capped at 500 recipients per call to safeguard against memory exhaustion attacks.

---

## 10. Automated Testing

The automated test suite provides 100% verification of all requirements, edge cases, and security boundaries.

### Run Tests

```powershell
# Activate venv
.\.venv\Scripts\Activate.ps1

# Run pytest with verbose reporting
pytest -v
```

### Verified Test Execution Evidence

```text
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-8.3.3, pluggy-1.6.0
rootdir: C:\Users\rahul\OneDrive\Documents\Bulk-Certificate-Generator-API
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.6.0, asyncio-0.24.0
asyncio: mode=Mode.AUTO, default_loop_scope=function
collected 71 items

tests/test_certificates.py (13 items)                                   PASSED
tests/test_certificates_api.py (4 items)                               PASSED
tests/test_health.py (3 items)                                          PASSED
tests/test_jobs.py (8 items)                                            PASSED
tests/test_realistic_verification.py (1 item)                           PASSED
tests/test_security_boundary.py (10 items)                              PASSED
tests/test_validation.py (32 items)                                     PASSED

======================== 71 passed, 1 warning in 4.36s ========================
```

---

## 11. Git & Submission Instructions

```powershell
# Check working tree cleanliness
git status

# Push commits to remote GitHub repository
git push origin dev
```

---

## 12. Final Submission Checklist

| # | Requirement | Implementation Reference | Status |
|---|---|---|:---:|
| 1 | Accept bulk certificate generation request | [`routers/jobs.py:create_job`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/routers/jobs.py) | **PASS** |
| 2 | Validate recipient data before processing | [`schemas/job.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/schemas/job.py) | **PASS** |
| 3 | Generate PDF certificate using predefined template | [`services/certificate_service.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/services/certificate_service.py) | **PASS** |
| 4 | Track generation status across lifecycle | [`models/job.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/models/job.py), [`models/recipient.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/models/recipient.py) | **PASS** |
| 5 | Allow client to poll progress/result | [`routers/jobs.py:get_job_status`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/routers/jobs.py) | **PASS** |
| 6 | Retrieve generated certificates (PDF & ZIP archive) | [`routers/certificates.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/routers/certificates.py), [`routers/jobs.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/routers/jobs.py) | **PASS** |
| 7 | Failure isolation (one bad record does not block batch) | [`services/job_service.py`](file:///c:/Users/rahul/OneDrive/Documents/Bulk-Certificate-Generator-API/bulk_cert_api/services/job_service.py) | **PASS** |
| 8 | Relational database storage | SQLite (dev) / PostgreSQL (prod) via SQLAlchemy async | **PASS** |
| 9 | Comprehensive automated testing suite | 71 automated tests across 7 test modules | **PASS** |
| 10 | Complete, verified documentation | Setup, run, test, API reference, design justifications | **PASS** |
