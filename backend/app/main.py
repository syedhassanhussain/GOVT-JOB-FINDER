"""
FastAPI Server & REST API for AI-Powered Government Job Finder & Personalized Career Assistant
"""

import json
import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime, date

from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from .database import get_db_connection, init_db
from .models import (
    UserRegister, UserProfileCreate, UserProfileUpdate,
    AdminJobVerify
)
from .matching_engine import evaluate_job_match, calculate_age
from .scraper_engine import scraper_engine
from .scheduler import (
    match_user_against_all_jobs,
    run_daily_automation_cycle,
    scheduler_daemon
)
from .notifications import send_notification

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

app = FastAPI(
    title="AI Government Job Finder API",
    description="Automated discovery, personalized matching, and step-by-step application guidance for Pakistani public sector jobs",
    version="1.0.0"
)

# CORS configuration
cors_origins_env = os.getenv("CORS_ORIGINS", "")
if cors_origins_env:
    origins = [o.strip().rstrip("/") for o in cors_origins_env.split(",") if o.strip()]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event():
    """Initializes database and seeds baseline active verified vacancies."""
    try:
        init_db()
    except Exception as e:
        print(f"[Startup Warning]: init_db error: {e}")

    # Serverless functions may be suspended between requests; use an external
    # scheduler for recurring work instead of a process-local daemon.
    try:
        from .database import is_serverless
        serverless = is_serverless()
    except Exception:
        serverless = bool(os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

    if not serverless and not scheduler_daemon.is_alive():
        try:
            scheduler_daemon.start()
        except Exception:
            pass


# --------------------------------------------------------------------------
# USER REGISTRATION & PROFILE ENDPOINTS (Phase 1)
# --------------------------------------------------------------------------
@app.post("/api/users/register")
def register_user(user: UserRegister):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, full_name, email, phone FROM users WHERE email = ?", (user.email,))
        existing = cursor.fetchone()
        if existing:
            conn.close()
            return {"user": dict(existing), "status": "existing"}

        cursor.execute("""
            INSERT INTO users (full_name, email, phone)
            VALUES (?, ?, ?)
        """, (user.full_name, user.email, user.phone))
        user_id = cursor.lastrowid
        conn.commit()

        cursor.execute("SELECT id, full_name, email, phone FROM users WHERE id = ?", (user_id,))
        new_user = cursor.fetchone()
        conn.close()
        return {"user": dict(new_user), "status": "created"}
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/users")
def list_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT u.id, u.full_name, u.email, u.phone, 
               p.degree_title, p.domicile, p.highest_qualification
        FROM users u
        LEFT JOIN user_profiles p ON u.id = p.user_id
        ORDER BY u.id DESC
    """)
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return {"users": users}


@app.get("/api/users/{user_id}/profile")
def get_user_profile(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    profile = cursor.fetchone()
    conn.close()

    if not profile:
        return {"profile": None}

    data = dict(profile)
    for field in ["preferred_job_fields", "preferred_locations", "skills"]:
        if isinstance(data.get(field), str):
            try:
                data[field] = json.loads(data[field])
            except Exception:
                data[field] = []

    return {"profile": data}


@app.post("/api/users/{user_id}/profile")
def create_or_update_profile(user_id: int, profile: UserProfileCreate):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Check user existence
    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail="User not found")

    calc_age = calculate_age(profile.date_of_birth)

    cursor.execute("""
        INSERT INTO user_profiles (
            user_id, highest_qualification, degree_title, field_of_study,
            institution, graduation_year, cgpa_or_percentage, date_of_birth,
            calculated_age, gender, province, city, domicile,
            preferred_job_fields, preferred_employment_type, preferred_locations,
            years_of_experience, skills, updated_at
        ) VALUES (
            ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, CURRENT_TIMESTAMP
        )
        ON CONFLICT(user_id) DO UPDATE SET
            highest_qualification = excluded.highest_qualification,
            degree_title = excluded.degree_title,
            field_of_study = excluded.field_of_study,
            institution = excluded.institution,
            graduation_year = excluded.graduation_year,
            cgpa_or_percentage = excluded.cgpa_or_percentage,
            date_of_birth = excluded.date_of_birth,
            calculated_age = excluded.calculated_age,
            gender = excluded.gender,
            province = excluded.province,
            city = excluded.city,
            domicile = excluded.domicile,
            preferred_job_fields = excluded.preferred_job_fields,
            preferred_employment_type = excluded.preferred_employment_type,
            preferred_locations = excluded.preferred_locations,
            years_of_experience = excluded.years_of_experience,
            skills = excluded.skills,
            updated_at = CURRENT_TIMESTAMP
    """, (
        user_id, profile.highest_qualification, profile.degree_title, profile.field_of_study,
        profile.institution, profile.graduation_year, profile.cgpa_or_percentage, profile.date_of_birth,
        calc_age, profile.gender, profile.province, profile.city, profile.domicile,
        json.dumps(profile.preferred_job_fields), profile.preferred_employment_type, json.dumps(profile.preferred_locations),
        profile.years_of_experience, json.dumps(profile.skills)
    ))

    conn.commit()
    conn.close()

    # Automatically recompute all matches for this user profile (Phase 3 integration)
    match_user_against_all_jobs(user_id)

    return {"status": "success", "message": "Profile saved and matches updated.", "calculated_age": calc_age}


@app.get("/api/jobs/public-feed")
def get_public_feed(
    source: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM jobs WHERE verification_status = 'verified'"
    params = []
    if source:
        query += " AND source_code = ?"
        params.append(source)
    if search:
        query += " AND (job_title LIKE ? OR department LIKE ? OR field_of_study LIKE ?)"
        wild = f"%{search}%"
        params.extend([wild, wild, wild])
    query += " ORDER BY closing_date ASC"
    cursor.execute(query, params)
    raw_jobs = cursor.fetchall()
    
    today = date.today()
    processed = []
    approaching = []
    for r in raw_jobs:
        job = dict(r)
        for json_col in ["allowed_domiciles", "required_documents", "step_by_step_instructions"]:
            if isinstance(job.get(json_col), str):
                try:
                    job[json_col] = json.loads(job[json_col])
                except Exception:
                    job[json_col] = []
        job["compatibility_score"] = None
        job["classification"] = "Setup Profile to Match"
        job["is_eligible"] = True
        job["match_reasons"] = ["Complete your profile to calculate exact AI compatibility score"]
        job["disqualification_reasons"] = []
        job["is_saved"] = False
        processed.append(job)

        try:
            c_date = datetime.strptime(job["closing_date"], "%Y-%m-%d").date()
            if 0 <= (c_date - today).days <= 7 and job["status"] in ["open", "closing_soon"]:
                approaching.append(job)
        except Exception:
            pass

    conn.close()
    return {
        "stats": {
            "total_vacancies": len(processed),
            "eligible_matches": len(processed),
            "highly_relevant_count": 0,
            "approaching_deadline_count": len(approaching),
            "saved_count": 0
        },
        "profile": None,
        "all_jobs": processed,
        "highly_relevant": [],
        "relevant": [],
        "potentially_eligible": [],
        "not_eligible": [],
        "approaching_deadlines": approaching,
        "saved_jobs": [],
        "newly_discovered": processed
    }


# --------------------------------------------------------------------------
# PERSONALIZED DASHBOARD & MATCHING (Phase 3 & Phase 4)
# --------------------------------------------------------------------------
@app.get("/api/users/{user_id}/dashboard")
def get_user_dashboard(
    user_id: int,
    source: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    domicile: Optional[str] = Query(None),
    search: Optional[str] = Query(None)
):
    if user_id <= 0:
        return get_public_feed(source, search)

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
    if not cursor.fetchone():
        conn.close()
        return get_public_feed(source, search)

    # Check if user has completed a profile
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    p_row = cursor.fetchone()
    if not p_row:
        conn.close()
        return get_public_feed(source, search)

    # Ensure matches are computed
    cursor.execute("SELECT COUNT(*) as count FROM job_matches WHERE user_id = ?", (user_id,))
    if cursor.fetchone()["count"] == 0:
        match_user_against_all_jobs(user_id)

    # Base query for all matched jobs for this user
    query = """
        SELECT 
            j.*,
            m.compatibility_score,
            m.classification,
            m.is_eligible,
            m.eligibility_breakdown,
            m.match_reasons,
            m.disqualification_reasons,
            CASE WHEN s.id IS NOT NULL THEN 1 ELSE 0 END as is_saved,
            s.status as application_status
        FROM jobs j
        JOIN job_matches m ON j.id = m.job_id AND m.user_id = ?
        LEFT JOIN user_saved_jobs s ON j.id = s.job_id AND s.user_id = ?
        WHERE j.verification_status = 'verified'
    """
    params = [user_id, user_id]

    if source:
        query += " AND j.source_code = ?"
        params.append(source)

    if classification:
        query += " AND m.classification = ?"
        params.append(classification)

    if search:
        query += " AND (j.job_title LIKE ? OR j.department LIKE ? OR j.field_of_study LIKE ?)"
        wild = f"%{search}%"
        params.extend([wild, wild, wild])

    query += " ORDER BY m.compatibility_score DESC, j.closing_date ASC"

    cursor.execute(query, params)
    raw_jobs = cursor.fetchall()

    processed_jobs = []
    for row in raw_jobs:
        job = dict(row)
        for json_col in ["allowed_domiciles", "required_documents", "step_by_step_instructions",
                         "eligibility_breakdown", "match_reasons", "disqualification_reasons"]:
            if isinstance(job.get(json_col), str):
                try:
                    job[json_col] = json.loads(job[json_col])
                except Exception:
                    job[json_col] = []
        processed_jobs.append(job)

    # Groupings
    highly_relevant = [j for j in processed_jobs if j["classification"] == "Highly Relevant"]
    relevant = [j for j in processed_jobs if j["classification"] == "Relevant"]
    potentially_eligible = [j for j in processed_jobs if j["classification"] == "Potentially Eligible"]
    not_eligible = [j for j in processed_jobs if not j["is_eligible"]]
    saved_jobs = [j for j in processed_jobs if j["is_saved"] == 1]

    # Approaching deadlines (within 7 days and open)
    today = date.today()
    approaching_deadlines = []
    for j in processed_jobs:
        try:
            c_date = datetime.strptime(j["closing_date"], "%Y-%m-%d").date()
            if 0 <= (c_date - today).days <= 7 and j["status"] in ["open", "closing_soon"]:
                approaching_deadlines.append(j)
        except Exception:
            pass

    # Newly discovered in last 7 days
    newly_discovered = [j for j in processed_jobs if j["status"] in ["open", "announced"]]

    # User Profile snapshot
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    p_row = cursor.fetchone()
    profile_summary = dict(p_row) if p_row else None

    # Stats
    stats = {
        "total_vacancies": len(processed_jobs),
        "eligible_matches": len([j for j in processed_jobs if j["is_eligible"]]),
        "highly_relevant_count": len(highly_relevant),
        "approaching_deadline_count": len(approaching_deadlines),
        "saved_count": len(saved_jobs)
    }

    conn.close()

    return {
        "stats": stats,
        "profile": profile_summary,
        "all_jobs": processed_jobs,
        "highly_relevant": highly_relevant,
        "relevant": relevant,
        "potentially_eligible": potentially_eligible,
        "not_eligible": not_eligible,
        "approaching_deadlines": approaching_deadlines,
        "saved_jobs": saved_jobs,
        "newly_discovered": newly_discovered
    }


# --------------------------------------------------------------------------
# JOB DETAILS & EXPLAINABILITY (Phase 4 & Phase 5)
# --------------------------------------------------------------------------
@app.get("/api/jobs/{job_id}")
def get_job_detail(job_id: int, user_id: Optional[int] = Query(None)):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()
    if not job_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    job = dict(job_row)
    for json_col in ["allowed_domiciles", "required_documents", "step_by_step_instructions"]:
        if isinstance(job.get(json_col), str):
            try:
                job[json_col] = json.loads(job[json_col])
            except Exception:
                job[json_col] = []

    # If user_id provided, fetch compatibility match info and bookmark status
    match_info = None
    is_saved = False
    if user_id:
        cursor.execute("SELECT * FROM job_matches WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        m_row = cursor.fetchone()
        if m_row:
            match_info = dict(m_row)
            for m_json in ["eligibility_breakdown", "match_reasons", "disqualification_reasons"]:
                if isinstance(match_info.get(m_json), str):
                    try:
                        match_info[m_json] = json.loads(match_info[m_json])
                    except Exception:
                        match_info[m_json] = []

        cursor.execute("SELECT 1 FROM user_saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        is_saved = bool(cursor.fetchone())

    conn.close()
    return {
        "job": job,
        "match": match_info,
        "is_saved": is_saved
    }


# --------------------------------------------------------------------------
# BOOKMARKS & SAVED JOBS (Phase 4)
# --------------------------------------------------------------------------
@app.post("/api/users/{user_id}/jobs/{job_id}/save")
def toggle_save_job(user_id: int, job_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM user_saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
    existing = cursor.fetchone()

    if existing:
        cursor.execute("DELETE FROM user_saved_jobs WHERE user_id = ? AND job_id = ?", (user_id, job_id))
        conn.commit()
        conn.close()
        return {"is_saved": False, "message": "Job removed from saved list."}
    else:
        cursor.execute("""
            INSERT INTO user_saved_jobs (user_id, job_id, status)
            VALUES (?, ?, 'saved')
        """, (user_id, job_id))
        conn.commit()
        conn.close()
        return {"is_saved": True, "message": "Job bookmarked successfully."}


# --------------------------------------------------------------------------
# NOTIFICATIONS (Phase 6)
# --------------------------------------------------------------------------
@app.get("/api/users/{user_id}/notifications")
def get_user_notifications(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT 50
    """, (user_id,))
    notifs = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) as unread_count FROM notifications WHERE user_id = ? AND is_read = 0", (user_id,))
    unread = cursor.fetchone()["unread_count"]
    conn.close()

    return {"notifications": notifs, "unread_count": unread}


@app.post("/api/users/{user_id}/notifications/{notif_id}/read")
def mark_notification_read(user_id: int, notif_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?", (notif_id, user_id))
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.post("/api/users/{user_id}/notifications/read-all")
def mark_all_notifications_read(user_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE notifications SET is_read = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return {"status": "success"}


# --------------------------------------------------------------------------
# ADMIN OPERATIONS & AUDIT (Phase 7 & Phase 8)
# --------------------------------------------------------------------------
@app.get("/api/admin/sources")
def get_sources_status():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM government_sources ORDER BY id ASC")
    sources = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"sources": sources}


@app.post("/api/admin/sources/scan")
def trigger_source_scan(source_code: Optional[str] = Query(None)):
    """Triggers manual job discovery crawl for all sources or a specific source."""
    if source_code:
        res = scraper_engine.scan_source(source_code)
    else:
        res = scraper_engine.scan_all_sources()
    return {"status": "completed", "result": res}


@app.post("/api/admin/trigger-daily-cycle")
def trigger_full_daily_cycle():
    """Triggers automated daily background cycle immediately."""
    result = run_daily_automation_cycle()
    return result


@app.get("/api/admin/jobs")
def get_all_jobs_for_admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT j.*, s.name as source_name
        FROM jobs j
        LEFT JOIN government_sources s ON j.source_code = s.code
        ORDER BY j.id DESC
    """)
    jobs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"jobs": jobs, "total": len(jobs)}


@app.put("/api/admin/jobs/{job_id}/verify")
def verify_job_admin(job_id: int, payload: AdminJobVerify):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE jobs SET 
            verification_status = ?,
            status = COALESCE(?, status),
            last_verified_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (payload.verification_status, payload.status, job_id))
    conn.commit()
    conn.close()
    return {"status": "updated", "job_id": job_id, "verification_status": payload.verification_status}


@app.get("/api/admin/logs")
def get_scrape_logs():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scrape_logs ORDER BY scanned_at DESC LIMIT 50")
    logs = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return {"logs": logs}


@app.get("/api/health")
def health_check():
    from .database import is_mongo_active, resolve_db_path, is_serverless
    mongo_connected = is_mongo_active()
    return {
        "status": "healthy",
        "service": "AI Government Job Finder API",
        "environment": "vercel_serverless" if is_serverless() else "standard",
        "database_type": "cloud_mongodb_atlas" if mongo_connected else "sqlite",
        "database_path": "cloud_mongodb" if mongo_connected else str(resolve_db_path()),
        "timestamp": datetime.now().isoformat()
    }


# --------------------------------------------------------------------------
# FRONTEND STATIC FILES & SPA SERVING
# --------------------------------------------------------------------------
STATIC_DIR = FRONTEND_DIR if FRONTEND_DIR.exists() else (BASE_DIR / "public")

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
@app.get("/index.html")
def serve_index():
    if STATIC_DIR.exists():
        index_file = STATIC_DIR / "index.html"
        if index_file.exists():
            return FileResponse(index_file)
    return {"message": "Government Job Finder Backend API is running. Access /docs for API documentation."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
