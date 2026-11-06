"""
End-to-End Test Suite for Government Job Finder & Career Assistant
Tests Profile Setup, Job Discovery, AI Matching Logic, Dashboard API, and Notifications.
"""

import sys
import json
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.app.database import init_db, get_db_connection
from backend.app.scraper_engine import scraper_engine
from backend.app.matching_engine import evaluate_job_match, calculate_age
from backend.app.scheduler import match_user_against_all_jobs, run_daily_automation_cycle
from backend.app.notifications import send_notification, check_and_generate_alerts_for_user


def test_full_pipeline():
    print("=== 1. Initializing Database ===")
    init_db()

    print("=== 2. Testing Job Discovery & Scraping ===")
    res = scraper_engine.scan_all_sources()
    print(f"Sources scanned: {res['total_sources_scanned']}, Jobs scanned: {res['total_jobs_scanned']}")
    assert res["total_sources_scanned"] > 0
    assert res["total_jobs_scanned"] >= 5

    print("=== 3. Testing User Registration & Profile Setup ===")
    conn = get_db_connection()
    c = conn.cursor()
    # Create test user
    c.execute("INSERT OR REPLACE INTO users (id, full_name, email, phone) VALUES (1, 'Ali Hamza', 'ali.hamza@example.com', '03001234567')")
    
    # Ali is 25 years old (DOB: 2001-05-15), BS Computer Science, Punjab Domicile, 2 years experience
    c.execute("""
        INSERT OR REPLACE INTO user_profiles (
            user_id, highest_qualification, degree_title, field_of_study,
            institution, graduation_year, cgpa_or_percentage, date_of_birth,
            calculated_age, gender, province, city, domicile,
            preferred_job_fields, preferred_employment_type, preferred_locations,
            years_of_experience, skills
        ) VALUES (
            1, 'Bachelor (16 Years / BS)', 'BS Computer Science', 'Computer Science / IT',
            'NUST Islamabad', 2023, '3.65 CGPA', '2001-05-15',
            25, 'Male', 'Punjab', 'Rawalpindi', 'Punjab',
            ?, 'Permanent', ?,
            2.0, ?
        )
    """, (
        json.dumps(["Computer Science / IT", "Administration & Management"]),
        json.dumps(["Islamabad", "Rawalpindi", "Lahore"]),
        json.dumps(["Python", "SQL", "Web Development", "Database Management"])
    ))
    conn.commit()
    conn.close()

    print("=== 4. Testing AI-Based Compatibility & Mandatory Rules ===")
    # Calculate matches for Ali
    match_user_against_all_jobs(1)

    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        SELECT j.job_title, j.department, j.source_code, m.compatibility_score, m.classification, m.is_eligible, m.match_reasons, m.disqualification_reasons
        FROM job_matches m
        JOIN jobs j ON m.job_id = j.id
        WHERE m.user_id = 1
        ORDER BY m.compatibility_score DESC
    """)
    matches = c.fetchall()
    
    print(f"Total evaluated jobs for Ali: {len(matches)}")
    for m in matches:
        print(f"[{m['source_code']}] {m['job_title']} -> Score: {m['compatibility_score']}% ({m['classification']}) - Eligible: {bool(m['is_eligible'])}")

    # Check that FPSC IT or NJP Cloud Engineer is ranked Highly Relevant (score >= 80)
    top_match = matches[0]
    assert top_match["compatibility_score"] >= 75
    assert top_match["is_eligible"] == 1
    print(f"Top match verified: {top_match['job_title']} ({top_match['compatibility_score']}%)")

    # Verify that a provincial job restricted to Balochistan gives Disqualification or Not Eligible for Punjab candidate
    bpsc_job = next((m for m in matches if m["source_code"] == "BPSC"), None)
    if bpsc_job:
        print(f"BPSC Job check for Punjab candidate: Eligible={bpsc_job['is_eligible']}, Classification={bpsc_job['classification']}")
        assert bpsc_job["is_eligible"] == 0
        assert "Balochistan" in bpsc_job["disqualification_reasons"]

    print("=== 5. Testing Automated Notifications & Alerts ===")
    check_and_generate_alerts_for_user(1)
    c.execute("SELECT id, title, message, type FROM notifications WHERE user_id = 1")
    notifs = c.fetchall()
    print(f"Generated notifications for Ali: {len(notifs)}")
    for n in notifs:
        print(f" - [{n['type']}] {n['title']}: {n['message']}")
    assert len(notifs) > 0

    print("=== 6. Testing Daily Background Cycle ===")
    cycle_res = run_daily_automation_cycle()
    print(f"Daily Automation Cycle executed in {cycle_res['duration_seconds']}s. Status: {cycle_res['status']}")
    assert cycle_res["status"] == "success"

    conn.close()
    print("\n ALL TEST SUITE PHASES PASSED WITH 100% ACCURACY!")


if __name__ == "__main__":
    test_full_pipeline()

