"""
Daily Automated Background Engine & Scheduler
Executes automated discovery, deadline progression, user matching recalculation, and notification dispatch.
"""

import threading
import time
import json
from datetime import datetime, date, timedelta
from typing import Dict, Any

try:
    from .database import get_db_connection
    from .scraper_engine import scraper_engine
    from .matching_engine import evaluate_job_match
    from .notifications import check_and_generate_alerts_for_user, generate_daily_digest_for_all_users
except ImportError:
    from database import get_db_connection
    from scraper_engine import scraper_engine
    from matching_engine import evaluate_job_match
    from notifications import check_and_generate_alerts_for_user, generate_daily_digest_for_all_users


def match_user_against_all_jobs(user_id: int):
    """Computes and caches AI compatibility score between a user profile and all active jobs."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # Load user profile
    cursor.execute("SELECT * FROM user_profiles WHERE user_id = ?", (user_id,))
    profile_row = cursor.fetchone()
    if not profile_row:
        conn.close()
        return

    profile = dict(profile_row)

    # Load all verified non-closed jobs
    cursor.execute("SELECT * FROM jobs WHERE status != 'closed' AND verification_status = 'verified'")
    jobs = cursor.fetchall()

    for j_row in jobs:
        j = dict(j_row)
        res = evaluate_job_match(profile, j)

        cursor.execute("""
            INSERT INTO job_matches (
                user_id, job_id, compatibility_score, classification,
                is_eligible, eligibility_breakdown, match_reasons,
                disqualification_reasons, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, job_id) DO UPDATE SET
                compatibility_score = excluded.compatibility_score,
                classification = excluded.classification,
                is_eligible = excluded.is_eligible,
                eligibility_breakdown = excluded.eligibility_breakdown,
                match_reasons = excluded.match_reasons,
                disqualification_reasons = excluded.disqualification_reasons,
                updated_at = CURRENT_TIMESTAMP
        """, (
            user_id,
            j["id"],
            res["compatibility_score"],
            res["classification"],
            1 if res["is_eligible"] else 0,
            json.dumps(res["eligibility_breakdown"]),
            json.dumps(res["match_reasons"]),
            json.dumps(res["disqualification_reasons"])
        ))

    conn.commit()
    conn.close()

    # Trigger alerts for new high matches or deadlines
    check_and_generate_alerts_for_user(user_id)


def update_job_deadline_statuses():
    """Updates job statuses based on current date (open, closing_soon, closed)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    five_days_str = (date.today() + timedelta(days=5)).isoformat()

    # Mark expired jobs as closed
    cursor.execute("""
        UPDATE jobs SET status = 'closed'
        WHERE closing_date < ? AND status != 'closed'
    """, (today_str,))

    # Mark urgent jobs as closing_soon
    cursor.execute("""
        UPDATE jobs SET status = 'closing_soon'
        WHERE closing_date >= ? AND closing_date <= ? AND status = 'open'
    """, (today_str, five_days_str))

    conn.commit()
    conn.close()


def run_daily_automation_cycle() -> Dict[str, Any]:
    """
    Full automated pipeline:
    1. Scrapes recruitment sources
    2. Updates deadlines & statuses
    3. Re-evaluates matches for all registered users
    4. Generates daily digest & alerts
    """
    start_time = datetime.now()

    # Step 1: Scan all sources
    scrape_res = scraper_engine.scan_all_sources()

    # Step 2: Deadline progression
    update_job_deadline_statuses()

    # Step 3: Match against all registered users
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM user_profiles")
    user_rows = cursor.fetchall()
    conn.close()

    matched_users_count = 0
    for u in user_rows:
        match_user_against_all_jobs(u["user_id"])
        matched_users_count += 1

    # Step 4: Dispatch digests
    digests_sent = generate_daily_digest_for_all_users()

    duration = (datetime.now() - start_time).total_seconds()
    return {
        "status": "success",
        "scrape_results": scrape_res,
        "users_re_matched": matched_users_count,
        "daily_digests_dispatched": digests_sent,
        "duration_seconds": round(duration, 2),
        "executed_at": datetime.now().isoformat()
    }


class BackgroundWorker(threading.Thread):
    """Background daemon that runs the cycle periodically."""

    def __init__(self, interval_seconds: int = 86400):
        super().__init__(daemon=True)
        self.interval = interval_seconds
        self.running = True

    def run(self):
        # Initial wait of 10 seconds after server startup
        time.sleep(10)
        while self.running:
            try:
                run_daily_automation_cycle()
            except Exception as e:
                print(f"[Scheduler Exception]: {e}")
            time.sleep(self.interval)

    def stop(self):
        self.running = False


# Background worker instance
scheduler_daemon = BackgroundWorker(interval_seconds=86400)

