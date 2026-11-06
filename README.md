# GOVT-JOB-FINDER
An intelligent mobile and web application that automatically discovers official government job vacancies across Pakistan, evaluates them against a user's qualifications, age, domicile, and career preferences, and provides a daily personalized shortlist with official application links and step-by-step instructions.

# AI-Powered Government Job Finder & Personalized Career Assistant

An intelligent mobile and web application that automatically discovers official government job vacancies across Pakistan, evaluates them against a user's qualifications, age, domicile, and career preferences, and provides a daily personalized shortlist with official application links and step-by-step instructions.

---

## 🌟 Key Features

1. **User Profile & Qualifications Wizard**:
   - Captures qualification level (Matric to PhD), exact degree title, field of study, date of birth (exact age calculation), province, district domicile, career interests, employment preference (Permanent/Contract), and experience.
   - User only sets up their profile once; subsequent jobs are continuously matched automatically.

2. **Automated Discovery Engine (Pakistani Public Sector)**:
   - Covers official recruitment portals:
     - **FPSC** (Federal Public Service Commission)
     - **PPSC** (Punjab Public Service Commission)
     - **SPSC** (Sindh Public Service Commission)
     - **KPPSC** (Khyber Pakhtunkhwa Public Service Commission)
     - **BPSC** (Balochistan Public Service Commission)
     - **NJP** (National Job Portal - Federal Ministries)
     - **NTS** (National Testing Service)
     - **PTS / OTS** (Pakistan & Open Testing Service)
   - Real-time probe resilience, SHA-256 deduplication, and gazette status tracking (open, closing soon, closed, extended).

3. **AI-Based Eligibility & Compatibility Engine**:
   - **Hard Disqualifiers**: Mandatory checks for qualification rank, domicile quota (e.g. Punjab candidate cannot apply for Balochistan-reserved quota), government age limit (factoring in general 5-year federal/provincial age relaxation), and gender restrictions.
   - **Compatibility Scoring (0–100%)**: Multi-factor weighting for degree title match, career preference, location, and relevant experience.
   - **Explainability**: Clear bullet-point explanations of *why* a candidate qualifies or fails mandatory requirements.

4. **Personalized Daily Feed & Filter Dashboard**:
   - Match categories: All Matches, Highly Relevant (80–100%), Relevant (60–79%), Potentially Eligible (40–59%), Closing Soon (<= 7 days), and Saved Vacancies.
   - Filter by recruitment commission, qualification, scale (BPS-16, BPS-17, PPS-08), and keyword search.

5. **Step-by-Step Application Instructions & Challan Guide**:
   - Dedicated modal with official gazette reference, bank challan instructions (National Bank of Pakistan, 1Link PSID), required documents checklist, test syllabus breakdown, and direct official application URL.

6. **Daily Automated Updates & Notifications**:
   - Automated background scheduler continuously monitors deadlines, re-evaluates registered users against new vacancies, and generates daily career digests and approaching deadline alerts.

7. **Admin Operations & Scraper Monitor**:
   - Monitor live status of commission portals, review extracted vacancies, inspect scrape logs, and trigger manual or scheduled discovery cycles.

---

## 🚀 Quick Start Guide

### 1. Requirements
- Python 3.10+ (Tested on Python 3.15)
- Standard web browser (Chrome, Edge, Firefox, Safari)

### 2. Installation
Open a terminal in the project directory and install dependencies:
```bash
py -m pip install -r requirements.txt
```

### 3. Run the Application
Start the application server:
```bash
py main.py
```
Or directly with uvicorn:
```bash
py -m uvicorn main:app --reload
```

### 4. Access the App
- **Web App / Mobile Experience**: Open [http://localhost:8000](http://localhost:8000)
- **Interactive REST API Docs**: Open [http://localhost:8000/docs](http://localhost:8000/docs)
- **API Health Check**: Open [http://localhost:8000/api/health](http://localhost:8000/api/health)

---

## 📂 Project Structure

```
d:\GOVT JOB FINDER\
├── api\
│   └── index.py                 # Vercel Serverless Function entrypoint
├── backend\
│   ├── __init__.py
│   └── app\
│       ├── __init__.py
│       ├── main.py              # FastAPI endpoints & static file router
│       ├── database.py          # SQLite & MongoDB Atlas integration
│       ├── models.py            # Pydantic schemas & validation
│       ├── matching_engine.py   # AI eligibility rules & 0-100% scorer
│       ├── scraper_engine.py    # Harvester for FPSC, PPSC, SPSC, KPPSC, BPSC, NJP, NTS
│       ├── scheduler.py         # Daily automated background worker
│       └── notifications.py     # In-app alerts & digest generator
├── frontend\
│   ├── index.html               # Responsive Mobile & Desktop Web App
│   ├── css\style.css            # Custom government styling & animations
│   └── js\app.js                # State management, API calls, and modals
├── tests\
│   └── test_api_and_matching.py # Automated test suite (100% pass)
├── main.py                      # Root FastAPI entrypoint
├── pyproject.toml               # Vercel FastAPI framework configuration
├── vercel.json                  # Vercel Edge rewrite routing rules
├── requirements.txt             # Python dependencies
├── .gitignore                   # Clean repository exclusions
└── README.md
```

---

## 🧪 Running Automated Tests

Run the test suite anytime:
```bash
py tests\test_api_and_matching.py
```

---

## Deploying on Vercel

The FastAPI application and static frontend are served from the same origin. Vercel uses
`pyproject.toml` to load `backend.app.main:app`; Python packages are installed from
`requirements.txt`. There is no separate frontend build step or `vercel.json` routing
configuration.

1. Import this GitHub repository as a Vercel project and keep the **Root Directory** at
   the repository root.
2. Leave the Build Command and Output Directory at their defaults; Vercel detects the
   Python runtime and installs `requirements.txt`.
3. Configure the environment variables below only if needed, then deploy.

| Variable | Required | Purpose |
| --- | --- | --- |
| `CORS_ORIGINS` | No | Comma-separated allowed origins, only if a separate frontend origin will call the API. Same-origin deployment needs no CORS setting. |
| `DATABASE_PATH` | No | Optional SQLite file path override. On Vercel, the default is `/tmp/govt_job_finder.db`. |

Vercel sets `VERCEL=1` automatically. The application currently uses SQLite and does
**not** connect to MongoDB. Vercel's `/tmp` storage is temporary and instance-local, so
user profiles, saved jobs, and notifications are not durable across restarts or function
instances. Use a persistent shared database before relying on this deployment for real
users; configuring a MongoDB URI alone will not work without migrating the SQLite-based
queries. The process-local daily background scheduler is disabled on Vercel; schedule
the existing admin automation endpoint externally if daily automation is required.
