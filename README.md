# TenderAI — AI-Powered Government Tender Evaluation System

Hackathon Submission | Built for automating CRPF/Government procurement evaluation with explainable AI, immutable audit trails, and GSTN/PAN compliance verification.

Live Demo: http://3.108.40.103/

## Table of Contents

- [How to Use the Live Prototype (AWS Link)](#how-to-use-the-live-prototype-aws-link)
- [Instructions to Run Locally (Local Sandbox)](#instructions-to-run-locally-local-sandbox)
- [Key Technical Features](#key-technical-features)
- [What Is TenderAI?](#what-is-tenderai)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Quick Setup (Local)](#quick-setup-local)
- [Running the Application](#running-the-application)
- [Environment Variables](#environment-variables)
- [API Reference](#api-reference)
- [How to Use the App](#how-to-use-the-app)
- [Architecture Overview](#architecture-overview)
- [Troubleshooting](#troubleshooting)
- [Test Data (Quick Demo)](#test-data-quick-demo)
- [Contact / Credits](#contact--credits)

## How to Use the Live Prototype (AWS Link)

You can access the functional dashboard directly at:

- http://3.108.40.103/

Step 1 — Create a Tender:

- Click "+ New Tender" in the sidebar.
- Fill in the reference (e.g., `CRPF-2026-TEST`), organization, and thresholds (Min Turnover in ₹ Cr, EMD, etc.).
- Optionally upload a Tender PDF to see the AI extract criteria.

Step 2 — Register Bidders:

- Select your tender and click "Add Bidder".
- Enter mock financial data (Turnover, GSTIN, PAN) and list supporting documents.

Step 3 — Run Evaluation:

- Click "Evaluate".
- The system will compare bidder data against the tender requirements, assigning a status of Eligible, Ineligible, or Review Required.

Step 4 — Verify Audit Trail:

- Click the "Audit" tab to see the immutable SHA-256 event chain.
- Click "Verify Chain" to confirm that no data has been tampered with.

Step 5 — Export Report:

- Click "Download Report" to generate a professionally formatted DOCX evaluation sheet.

## Instructions to Run Locally (Local Sandbox)

If you have the source code (zip file) and want to run a local instance of the same system, follow these steps.

Prerequisites:

- Python: 3.10 or higher
- OS: Windows (CMD/PowerShell) or Linux/macOS

Step-by-Step Setup:

Extract and Navigate:

```bash
unzip tenderai.zip
cd tenderai
```

Create Virtual Environment:

```text
Windows:
  python -m venv venv
  venv\Scripts\activate

Linux/macOS:
  python3 -m venv venv
  source venv/bin/activate
```

Install Dependencies:

```bash
pip install -r requirements.txt
```

Create Required Folders:

```bash
# Linux/macOS
mkdir -p backend/uploads/tenders backend/uploads/bidders reports

# Windows
mkdir backend\uploads\tenders
mkdir backend\uploads\bidders
mkdir reports
```

Run the Application:

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Access:

- Frontend: http://localhost:8000
- API Documentation: http://localhost:8000/docs

## Key Technical Features

- Immutable Audit Trail: Uses SHA-256 hashing to link every event (Tender Create → Bidder Add → Evaluate), preventing administrative tampering.
- Grounded Verification: Includes a fallback GSTIN/PAN validator that follows official 15-character Indian tax formats.
- Confidence Scoring: Automatically flags bidders for manual review if data is extracted from low-quality scans or is borderline against thresholds.

## What Is TenderAI?

TenderAI is an AI-driven platform that automates the eligibility evaluation of bidders for Government of India tender procurements (CRPF, MHA, and similar organizations). It replaces error-prone manual evaluation with:

- Automated criteria extraction from tender documents (PDF/DOCX/TXT)
- Criterion-by-criterion AI evaluation of each bidder against mandatory and optional requirements
- Real-time GSTIN & PAN validation via Government APIs
- Confidence scoring with human-in-the-loop flagging for borderline cases
- Immutable SHA-256 audit chain — every event is cryptographically linked
- One-click DOCX evaluation report generation for procurement officers

## Project Structure

```text
tenderai/
  backend/
    main.py                   # FastAPI app — all REST API endpoints
    models/
      database.py             # SQLAlchemy ORM models (SQLite)
    services/
      evaluator.py            # AI evaluation engine + GSTN verifier
      report_generator.py     # DOCX report generator (python-docx)
    uploads/
      tenders/                # Uploaded tender documents (auto-created)
      bidders/                # Uploaded bidder documents (auto-created)
    tenderai.db               # SQLite database (auto-created on first run)
  frontend/
    index.html                # Single-file React-like SPA (vanilla JS)
  reports/                    # Generated DOCX reports (auto-created)
  requirements.txt            # Python dependencies
  start.sh                    # Production startup script
  README.md                   # This file
```

## Tech Stack

| Layer | Technology |
| --- | --- |
| Backend API | Python 3.10+, FastAPI 0.111 |
| Database | SQLite (via SQLAlchemy 2.0) |
| Document Parsing | pdfplumber, python-docx |
| Report Generation | python-docx |
| External Verification | GSTN REST API (with format-validation fallback) |
| Frontend | Single-file HTML/CSS/Vanilla JS SPA |
| Server | Uvicorn (ASGI) |

## Prerequisites

Make sure the following are installed on your system before setup:

- Windows users: Use Git Bash or WSL2 for the shell commands below.
- macOS users: You may need `python3` and `pip3` instead of `python` and `pip`.

| Requirement | Minimum Version | Check Command |
| --- | --- | --- |
| Python | 3.10+ | `python3 --version` |
| pip | 22+ | `pip --version` |
| git | any | `git --version` |

## Quick Setup (Local)

### Step 1 — Clone / Unzip the Project

If you received the zip file:

```bash
unzip tenderai.zip
cd tenderai
```

If cloning from Git:

```bash
git clone <repo-url>
cd tenderai
```

### Step 2 — Create a Virtual Environment

```bash
# Linux / macOS
python3 -m venv venv
source venv/bin/activate

# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate

# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1
```

You should see `(venv)` prefix in your terminal after activation.

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

This installs:

```text
fastapi==0.111.0
uvicorn==0.30.1
sqlalchemy==2.0.30
python-multipart==0.0.9
aiofiles==23.2.1
pdfplumber==0.11.0
python-docx==1.1.2
requests==2.32.3
```

Note: No GPU required.

### Step 4 — Create Required Folders

```bash
mkdir -p backend/uploads/tenders
mkdir -p backend/uploads/bidders
mkdir -p reports
```

On Windows (Command Prompt):

```bat
mkdir backend\uploads\tenders
mkdir backend\uploads\bidders
mkdir reports
```

## Running the Application

### Option A — Direct Run (Recommended for Reviewers)

```bash
# Make sure you are inside the tenderai/ project folder
# and the virtual environment is activated

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

Then open your browser and visit:

```text
http://localhost:8000
```

The API docs are also auto-generated at:

```text
http://localhost:8000/docs
```

### Option B — Using the Startup Script (Linux/macOS)

```bash
chmod +x start.sh
./start.sh
```

Note: `start.sh` is configured for the production server path `/home/ubuntu/TenderAI`. For local use, Option A is recommended.

### Option C — With Auto-Reload (Development)

```bash
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

## Environment Variables

The application runs without any `.env` file by default — it uses SQLite and GSTN format-validation fallback automatically.

To enable real GSTN API verification (optional):

Create a `.env` file in the project root:

```bash
GSTN_CLIENT_ID=your_gstn_client_id
GSTN_AUTH_TOKEN=your_gstn_auth_token
```

Then update `backend/services/evaluator.py`:

```python
GSTN_HEADERS = {
    "clientid": os.getenv("GSTN_CLIENT_ID", ""),
    "Authorization": os.getenv("GSTN_AUTH_TOKEN", ""),
}
```

Without real GSTN credentials, the system falls back to format-only validation (checks the 15-character regex pattern). This is sufficient for demo and testing purposes.

## API Reference

All endpoints are available at `http://localhost:8000`. Full interactive docs at `/docs`.

### Health Check

```text
GET /api/health
```

Returns:

```json
{ "status": "ok", "version": "2.0" }
```

### Tenders

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /api/tenders | List all tenders |
| POST | /api/tenders | Create tender (form-data, optional file upload) |
| GET | /api/tenders/{id} | Get single tender |
| DELETE | /api/tenders/{id} | Delete tender |

### Bidders

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /api/tenders/{tid}/bidders | List bidders for a tender |
| POST | /api/tenders/{tid}/bidders | Add bidder (form-data, optional file uploads) |
| GET | /api/bidders/{bid} | Get single bidder |
| DELETE | /api/bidders/{bid} | Delete bidder |

### Evaluation

| Method | Endpoint | Description |
| --- | --- | --- |
| POST | /api/tenders/{tid}/evaluate | Run AI evaluation for all bidders |
| GET | /api/tenders/{tid}/evaluation | Fetch evaluation results |

### Reports

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /api/tenders/{tid}/report/docx | Download DOCX evaluation report |

### Audit & Compliance

| Method | Endpoint | Description |
| --- | --- | --- |
| GET | /api/audit | Get audit log (last 100 events) |
| GET | /api/audit/verify | Verify SHA-256 audit chain integrity |
| GET | /api/verify/gstin/{gstin} | Verify a GSTIN number |

## How to Use the App

### Step 1 — Create a Tender

- Open http://localhost:8000 in your browser
- Click "+ New Tender" in the left sidebar
- Fill in tender details:
  - Tender Reference (e.g. CRPF-OTE-2026-001)
  - Tender Name, Organization
  - Contract Value, Min Turnover (₹ Crore)
  - Minimum Similar Projects required
  - EMD Amount
  - Optionally upload the tender PDF/DOCX — the system will auto-extract eligibility criteria
- Click "Create Tender"

The AI will automatically extract and display criteria like:

- Financial thresholds (turnover, net worth, EMD)
- Compliance requirements (GSTIN, PAN, NSIC)
- Experience requirements (similar projects)
- Legal declarations (integrity pact, blacklisting)

### Step 2 — Register Bidders

- Select the tender from the sidebar
- Click "Add Bidder"
- Fill in company details:
  - Company Name, GSTIN, PAN, CIN
  - Turnover figures for last 3 financial years
  - Number of similar projects completed
  - Document list (comma-separated, e.g. PAN Card, GSTIN Certificate, EMD DD, Experience Cert)
  - Optionally upload supporting documents
- Repeat for each bidder

### Step 3 — Run Evaluation

- Click "Evaluate" button on the tender
- The AI engine evaluates every bidder against every criterion
- Results show:
  - Eligible — all mandatory criteria met
  - Ineligible — one or more mandatory criteria failed
  - Review Required — borderline cases flagged for human review
- Each criterion shows: bidder value vs. required value, confidence score, reasoning

### Step 4 — Download Report

- Click "Download Report" to get a professionally formatted DOCX
- The report includes:
  - Tender summary and evaluation metadata
  - Per-bidder eligibility verdict with full reasoning
  - Criterion-level breakdown with confidence scores
  - Audit trail summary

### Step 5 — View Audit Log

- Click the "Audit" tab in the navigation
- View the complete event chain: tender creation → bidder registration → evaluation → report generation
- Click "Verify Chain" to validate the SHA-256 hash integrity

## Architecture Overview

```text
Browser (index.html)
        |
        | HTTP REST
        v
FastAPI (main.py)
        |
        +-- CriteriaExtractor      : NLP-based criteria detection from tender docs
        +-- evaluate_bidder_full   : Rule + semantic matching engine
        +-- verify_gstin_real      : GSTN API / format fallback
        +-- generate_docx_report   : python-docx report builder
        +-- AuditLog (SHA-256)     : Immutable event chain
        |
        v
SQLite (tenderai.db)
  [Tender | Bidder | Evaluation | AuditLog]
```

Evaluation Logic Flow:

```text
Tender Text
    |
    v
CriteriaExtractor (regex + mandatory marker NLP)
Structured Criteria List
    |
    v
evaluate_criterion() per criterion per bidder
  - Financial:   avg_turnover >= threshold
  - Experience:  semantic_similarity(exp_text, tender_kw) + project count
  - GSTIN:       verify_gstin_real() -> format or API check
  - PAN:         regex ^[A-Z]{5}\\d{4}[A-Z]$
  - EMD:         docs_list contains DD/BG or NSIC exempt
  - Legal:       docs_list contains declaration/affidavit keywords
    |
    v
Confidence Score + Overall Verdict (eligible / ineligible / review_required)
```

## Troubleshooting

### Port Already in Use

```bash
# Kill the existing process on port 8000
# Linux/macOS:
lsof -ti:8000 | xargs kill -9

# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F
```

### ModuleNotFoundError

Make sure your virtual environment is activated before running:

```bash
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
```

### Permission denied on start.sh

```bash
chmod +x start.sh
```

### SQLite Database Issues

Delete and let it auto-recreate:

```bash
rm backend/tenderai.db
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### PDF Extraction Fails

Ensure pdfplumber is installed:

```bash
pip install pdfplumber==0.11.0
```

### Frontend Shows "API Offline"

The frontend connects to the API at the same host/port. Make sure the backend is running and visit `http://localhost:8000/api/health` to verify.

## Test Data (Quick Demo)

Use these values to quickly test the system without real documents:

Tender:

- Ref: CRPF-OTE-2026-TEST
- Name: Supply of Night Vision Equipment
- Org: CRPF HQ
- Value: 500
- Min Turnover: 5
- Min Projects: 3
- EMD: 200000

Bidder 1 (Should pass):

- Company: TechVision Defence Pvt Ltd
- GSTIN: 27AABCT3518Q1ZO
- PAN: AABCT3518Q
- Turnover 21-22: 8, 22-23: 9, 23-24: 10
- Projects: 5
- Docs: PAN Card, GSTIN Certificate, EMD DD, Experience Cert, Integrity Pact

Bidder 2 (Should fail — low turnover):

- Company: Small Optics Vendor
- GSTIN: 07AABCB4421R1Z3
- PAN: AABCB4421R
- Turnover 21-22: 2, 22-23: 2.5, 23-24: 3
- Projects: 2
- Docs: PAN Card, GSTIN Certificate

## Contact / Credits

Built for the AI for Government Procurement Hackathon.

- Author: Inova (mohammedsulaiman.scs25@bmsce.ac.in & revantl.scs25@bmsce.ac.in)
- Live Deployment: http://3.108.40.103/

This system is designed to assist procurement officers — all final decisions remain with authorized human personnel per GFR 2017 and CVC guidelines.
