"""
Database layer for Government Job Finder & Career Assistant
SQLite implementation with full schema initialization, indexes, and transaction utilities.
"""

import sqlite3
import os
import json
from datetime import datetime, date
from pathlib import Path

# Database path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH = BASE_DIR / "data" / "govt_job_finder.db"


def get_db_connection():
    """Returns a SQLite connection with dict-like row factory and FK support."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=20.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


def init_db():
    """Initializes tables, indexes, and initial government source configurations."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        phone TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. User Profiles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_profiles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        highest_qualification TEXT NOT NULL,
        degree_title TEXT NOT NULL,
        field_of_study TEXT NOT NULL,
        institution TEXT,
        graduation_year INTEGER,
        cgpa_or_percentage TEXT,
        date_of_birth DATE NOT NULL,
        calculated_age INTEGER NOT NULL,
        gender TEXT NOT NULL,
        province TEXT NOT NULL,
        city TEXT NOT NULL,
        domicile TEXT NOT NULL,
        preferred_job_fields TEXT NOT NULL,  -- JSON list
        preferred_employment_type TEXT NOT NULL,
        preferred_locations TEXT NOT NULL,   -- JSON list
        years_of_experience REAL DEFAULT 0.0,
        skills TEXT NOT NULL,                -- JSON list
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    """)

    # 3. Government Recruitment Sources
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS government_sources (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,               -- Federal, Provincial, Testing Agency
        portal_url TEXT NOT NULL,
        official_jobs_url TEXT NOT NULL,
        status TEXT DEFAULT 'active',         -- active, degraded, maintenance
        last_scanned_at DATETIME,
        total_jobs_found INTEGER DEFAULT 0,
        reliability_notes TEXT
    );
    """)

    # 4. Jobs table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id INTEGER,
        source_code TEXT NOT NULL,           -- FPSC, PPSC, SPSC, KPPSC, BPSC, NJP, NTS, PTS, OTS, etc.
        case_or_ad_no TEXT,                  -- Case No or Ad Reference
        job_title TEXT NOT NULL,
        department TEXT NOT NULL,
        ministry_or_provincial_dept TEXT,
        bps_scale TEXT,                      -- BPS-16, BPS-17, etc.
        min_qualification_level TEXT NOT NULL, -- Matric, Intermediate, Bachelor (14Y), Bachelor (16Y), Master, MPhil, PhD
        required_degree TEXT NOT NULL,
        field_of_study TEXT NOT NULL,
        min_experience_years REAL DEFAULT 0.0,
        min_age INTEGER DEFAULT 18,
        max_age INTEGER DEFAULT 30,
        age_relaxation_years INTEGER DEFAULT 5,
        allowed_domiciles TEXT NOT NULL,     -- JSON list e.g. ["Punjab", "Merit"]
        gender_eligibility TEXT DEFAULT 'Both', -- Male, Female, Both
        location TEXT NOT NULL,
        employment_type TEXT DEFAULT 'Permanent', -- Permanent, Contract
        vacancies_count INTEGER DEFAULT 1,
        salary_or_scale TEXT,
        ad_date DATE,
        closing_date DATE NOT NULL,
        application_fee TEXT,
        required_documents TEXT NOT NULL,    -- JSON list
        step_by_step_instructions TEXT NOT NULL, -- JSON list of numbered steps
        official_ad_url TEXT NOT NULL,
        official_apply_url TEXT NOT NULL,
        syllabus_or_test_info TEXT,
        status TEXT DEFAULT 'open',          -- announced, open, closing_soon, closed, extended
        verification_status TEXT DEFAULT 'verified', -- verified, pending_review, rejected
        content_hash TEXT UNIQUE NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_verified_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (source_id) REFERENCES government_sources(id) ON DELETE SET NULL
    );
    """)

    # 5. Job Matches table (Precomputed compatibility)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        compatibility_score INTEGER NOT NULL,
        classification TEXT NOT NULL,        -- Highly Relevant, Relevant, Potentially Eligible, Not Eligible
        is_eligible BOOLEAN NOT NULL,
        eligibility_breakdown TEXT NOT NULL, -- JSON detailed checklist
        match_reasons TEXT NOT NULL,         -- JSON list
        disqualification_reasons TEXT NOT NULL, -- JSON list
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        UNIQUE(user_id, job_id)
    );
    """)

    # 6. User Saved Jobs / Applications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_saved_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER NOT NULL,
        status TEXT DEFAULT 'saved',         -- saved, applied, dismissed
        notes TEXT,
        saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        applied_at DATETIME,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE,
        UNIQUE(user_id, job_id)
    );
    """)

    # 7. In-App Notifications
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        job_id INTEGER,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        type TEXT DEFAULT 'match',           -- match, deadline, digest, system
        is_read BOOLEAN DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE SET NULL
    );
    """)

    # 8. Scrape Audit Logs
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scrape_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_code TEXT NOT NULL,
        status TEXT NOT NULL,                -- success, partial, failed
        jobs_scanned INTEGER DEFAULT 0,
        new_jobs_added INTEGER DEFAULT 0,
        updated_jobs INTEGER DEFAULT 0,
        error_message TEXT,
        duration_seconds REAL DEFAULT 0.0,
        scanned_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Create Indexes for fast querying & filtering
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_closing ON jobs(closing_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source_code);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_matches_user_score ON job_matches(user_id, compatibility_score DESC);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_saved_user ON user_saved_jobs(user_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications(user_id, is_read);")

    # Seed official sources if not present
    seed_sources(cursor)

    conn.commit()
    conn.close()


def seed_sources(cursor):
    """Initializes primary Pakistani public sector recruitment sources."""
    sources = [
        (
            "FPSC",
            "Federal Public Service Commission",
            "Federal",
            "https://www.fpsc.gov.pk",
            "https://online.fpsc.gov.pk",
            "Official federal commission for BPS-16 and above posts in all ministries."
        ),
        (
            "PPSC",
            "Punjab Public Service Commission",
            "Provincial (Punjab)",
            "https://www.ppsc.gop.pk",
            "https://www.ppsc.gop.pk/(S(1))/Jobs.aspx",
            "Official recruitment agency for Government of the Punjab departments."
        ),
        (
            "SPSC",
            "Sindh Public Service Commission",
            "Provincial (Sindh)",
            "https://spsc.gos.pk",
            "https://spsc.gos.pk/advertisement",
            "Recruitment body for Sindh Civil Services and public departments."
        ),
        (
            "KPPSC",
            "Khyber Pakhtunkhwa Public Service Commission",
            "Provincial (KP)",
            "https://kppsc.gov.pk",
            "https://kppsc.gov.pk/advertisement",
            "Official recruitment commission for KP provincial posts."
        ),
        (
            "BPSC",
            "Balochistan Public Service Commission",
            "Provincial (Balochistan)",
            "https://bpsc.gob.pk",
            "https://bpsc.gob.pk/advertisements",
            "Official recruitment commission for Balochistan government vacancies."
        ),
        (
            "NJP",
            "National Job Portal (Government of Pakistan)",
            "Federal",
            "https://njp.gov.pk",
            "https://njp.gov.pk",
            "Unified federal recruitment portal for federal ministries and attached departments."
        ),
        (
            "NTS",
            "National Testing Service Pakistan",
            "Testing Agency",
            "https://www.nts.org.pk",
            "https://www.nts.org.pk/new/projects.php",
            "Conducts recruitment screenings for various federal & provincial government departments."
        ),
        (
            "PTS",
            "Pakistan Testing Service",
            "Testing Agency",
            "https://www.pts.org.pk",
            "https://www.pts.org.pk/Projects",
            "Recruitment tests for police, security forces, and administrative departments."
        ),
        (
            "OTS",
            "Open Testing Service",
            "Testing Agency",
            "https://ots.org.pk",
            "https://ots.org.pk/project.php",
            "Public sector recruitment tests for WAPDA, ministries, and autonomous organizations."
        ),
    ]

    for code, name, category, portal_url, jobs_url, notes in sources:
        cursor.execute("""
            INSERT OR IGNORE INTO government_sources 
            (code, name, category, portal_url, official_jobs_url, status, reliability_notes)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
        """, (code, name, category, portal_url, jobs_url, notes))


if __name__ == "__main__":
    init_db()
    print("Database schema successfully initialized.")

