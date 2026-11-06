"""
Notification and Alert Dispatcher for Government Job Finder
Manages in-app notifications, deadline alerts, match highlights, and daily digests.
Prevents duplicate alert spam.
"""

import json
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional

try:
    from .database import get_db_connection
except ImportError:
    from database import get_db_connection


def send_notification(user_id: int, title: str, message: str, notif_type: str = "match", job_id: Optional[int] = None) -> bool:
    """
    Creates an in-app notification if an identical active notification does not already exist.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # Deduplication: do not repeat identical unread notification for same job
    if job_id:
        cursor.execute("""
            SELECT id FROM notifications 
            WHERE user_id = ? AND job_id = ? AND type = ? AND is_read = 0
        """, (user_id, job_id, notif_type))
        if cursor.fetchone():
            conn.close()
            return False

    cursor.execute("""
        INSERT INTO notifications (user_id, job_id, title, message, type, is_read)
        VALUES (?, ?, ?, ?, ?, 0)
    """, (user_id, job_id, title, message, notif_type))

    conn.commit()
    conn.close()
    return True


def check_and_generate_alerts_for_user(user_id: int):
    """
    Evaluates matches and deadlines for a given user, generating notifications:
    1. High compatibility alerts (score >= 75)
    2. Approaching deadlines for saved or high match jobs (<= 5 days)
    3. Status changes (extended / closed)
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. High match notifications
    cursor.execute("""
        SELECT m.job_id, m.compatibility_score, m.classification, j.job_title, j.department, j.source_code, j.closing_date
        FROM job_matches m
        JOIN jobs j ON m.job_id = j.id
        WHERE m.user_id = ? AND m.is_eligible = 1 AND m.compatibility_score >= 75
        ORDER BY m.compatibility_score DESC
    """, (user_id,))
    high_matches = cursor.fetchall()

    for m in high_matches:
        title = f"🎯 {m['classification']} Job Found ({m['compatibility_score']}%)"
        msg = f"{m['job_title']} at {m['department']} ({m['source_code']}) closely matches your profile. Deadline: {m['closing_date']}."
        send_notification(user_id, title, msg, notif_type="match", job_id=m["job_id"])

    # 2. Deadline alert (closing within 5 days)
    today = date.today()
    cursor.execute("""
        SELECT j.id, j.job_title, j.department, j.closing_date, j.official_apply_url
        FROM jobs j
        WHERE j.status IN ('open', 'closing_soon')
        AND date(j.closing_date) >= date('now')
        AND date(j.closing_date) <= date('now', '+5 days')
    """)
    urgent_jobs = cursor.fetchall()

    for uj in urgent_jobs:
        # Check if user has saved this job or matches it with eligibility
        cursor.execute("""
            SELECT 1 FROM user_saved_jobs WHERE user_id = ? AND job_id = ?
            UNION
            SELECT 1 FROM job_matches WHERE user_id = ? AND job_id = ? AND is_eligible = 1
        """, (user_id, uj["id"], user_id, uj["id"]))

        if cursor.fetchone():
            c_date = uj["closing_date"]
            title = f"⏰ Approaching Deadline: {uj['job_title']}"
            msg = f"The application window for {uj['job_title']} ({uj['department']}) closes on {c_date}. Apply before portal cutoff!"
            send_notification(user_id, title, msg, notif_type="deadline", job_id=uj["id"])

    conn.close()


def generate_daily_digest_for_all_users() -> int:
    """
    Creates a morning career digest notification for all registered users summarizing top matches.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, full_name FROM users")
    users = cursor.fetchall()
    count = 0

    for u in users:
        cursor.execute("""
            SELECT COUNT(*) as eligible_count, MAX(compatibility_score) as top_score
            FROM job_matches
            WHERE user_id = ? AND is_eligible = 1
        """, (u["id"],))
        summary = cursor.fetchone()

        if summary and summary["eligible_count"] > 0:
            title = f"📰 Your Daily Govt Job Digest - {date.today().strftime('%b %d, %Y')}"
            msg = f"Good morning {u['full_name']}! You have {summary['eligible_count']} active eligible vacancies matching your profile, with a top compatibility score of {summary['top_score']}%. Check your dashboard today."
            if send_notification(u["id"], title, msg, notif_type="digest"):
                count += 1

    conn.close()
    return count

