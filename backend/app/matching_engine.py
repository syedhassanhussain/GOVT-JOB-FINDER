"""
AI-Based Job Matching & Eligibility Engine for Pakistani Government Vacancies
Performs two-stage evaluation:
1. Hard Mandatory Eligibility Gate (Qualification level, Age relaxation limits, Domicile quota, Gender)
2. Weighted Multi-Factor Compatibility Scoring (Degree relevance, Experience, Career interests, Location, Skills)
"""

import json
from datetime import datetime, date
from typing import Dict, Any, List, Tuple

# Qualification hierarchy rank (Pakistan HEC standard)
QUALIFICATION_RANKS = {
    "Matric": 10,
    "Matriculation": 10,
    "Intermediate": 12,
    "FA": 12,
    "FSc": 12,
    "A-Level": 12,
    "Bachelor (14 Years)": 14,
    "BA": 14,
    "BSc": 14,
    "Bachelor (16 Years)": 16,
    "Bachelor (16 Years / BS)": 16,
    "BS": 16,
    "Master (16 Years)": 16,
    "MA": 16,
    "MSc": 16,
    "MPhil / MS (18 Years)": 18,
    "MS": 18,
    "MPhil": 18,
    "PhD": 20,
    "Doctorate": 20
}

# Domain & subject matter compatibility clusters
FIELD_SYNONYMS = {
    "Computer Science / IT": [
        "computer science", "software engineering", "information technology", "data science",
        "cyber security", "artificial intelligence", "cs", "it", "se", "computer engineering",
        "telecommunication", "network administration"
    ],
    "Administration & Management": [
        "administration", "management", "public administration", "business administration",
        "mpa", "mba", "bba", "human resource", "hr", "general administration", "management sciences"
    ],
    "Accounting & Finance": [
        "accounting", "finance", "commerce", "b.com", "m.com", "acca", "ca", "cma",
        "banking", "economics", "audit", "accounts"
    ],
    "Education & Academia": [
        "education", "b.ed", "m.ed", "teaching", "english", "mathematics", "urdu",
        "islamiyat", "pakistan studies", "physics", "chemistry", "biology", "lecturer"
    ],
    "Engineering": [
        "engineering", "electrical engineering", "civil engineering", "mechanical engineering",
        "chemical engineering", "electronics", "telecom engineering", "pec"
    ],
    "Law & Judiciary": [
        "law", "llb", "llm", "legal", "advocate", "bar", "judiciary", "prosecution"
    ],
    "Medical & Healthcare": [
        "medical", "mbbs", "bds", "pharm-d", "nursing", "pharmacy", "public health",
        "allied health", "doctor"
    ],
    "Police & Law Enforcement": [
        "police", "security", "law enforcement", "criminology", "investigation", "armed forces",
        "asi", "sub-inspector", "inspector", "constable"
    ]
}


def calculate_age(dob_str: str, reference_date: date = None) -> int:
    """Calculates exact age in years from YYYY-MM-DD."""
    if not reference_date:
        reference_date = date.today()
    try:
        dob = datetime.strptime(dob_str, "%Y-%m-%d").date()
        age = reference_date.year - dob.year - ((reference_date.month, reference_date.day) < (dob.month, dob.day))
        return max(0, age)
    except Exception:
        return 25  # default fallback


def normalize_qualification_rank(qual_str: str) -> int:
    """Returns numeric rank (10, 12, 14, 16, 18, 20) for qualification comparison."""
    qual_lower = qual_str.lower()
    for key, rank in QUALIFICATION_RANKS.items():
        if key.lower() in qual_lower:
            return rank
    if "phd" in qual_lower or "doctor" in qual_lower:
        return 20
    if "mphil" in qual_lower or "ms" in qual_lower:
        return 18
    if "master" in qual_lower or "bs" in qual_lower or "16" in qual_lower or "bachelor" in qual_lower:
        return 16
    if "inter" in qual_lower or "fsc" in qual_lower or "fa" in qual_lower:
        return 12
    if "matric" in qual_lower:
        return 10
    return 14


def evaluate_field_match(user_field: str, user_degree: str, job_field: str, job_degree: str) -> Tuple[float, str]:
    """
    Evaluates degree and field of study compatibility.
    Returns (match_ratio 0.0 to 1.0, reason_description).
    """
    u_field_l = user_field.lower()
    u_deg_l = user_degree.lower()
    j_field_l = job_field.lower()
    j_deg_l = job_degree.lower()

    # Open / General degree positions (e.g. CSS, PMS, Inspector, Executive Assistant)
    if any(phrase in j_deg_l for phrase in ["any discipline", "any subject", "general", "recognized university", "second division bachelor"]):
        return 1.0, f"Degree open to any discipline ({user_degree} fully qualifies)"

    # Direct substring exact match
    if u_deg_l in j_deg_l or j_deg_l in u_deg_l:
        return 1.0, f"Direct degree match: {user_degree} corresponds to required {job_degree}"

    # Cluster synonym matching
    for cluster, terms in FIELD_SYNONYMS.items():
        user_in_cluster = any(term in u_field_l or term in u_deg_l for term in terms)
        job_in_cluster = any(term in j_field_l or term in j_deg_l for term in terms)
        if user_in_cluster and job_in_cluster:
            return 0.95, f"Domain match in {cluster} ({user_degree} aligns with {job_degree})"

    # Cross discipline partial match
    words_user = set(u_deg_l.replace("/", " ").replace("-", " ").split())
    words_job = set(j_deg_l.replace("/", " ").replace("-", " ").split())
    common = words_user.intersection(words_job) - {"in", "and", "of", "or", "bs", "ms", "degree", "the"}
    if common:
        return 0.70, f"Related academic specialization in {', '.join(common)}"

    return 0.20, f"Degree field ({user_field}) differs from specified requirement ({job_field})"


def evaluate_job_match(user_profile: Dict[str, Any], job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates a candidate's profile against a government job vacancy.
    Enforces mandatory government rules and generates compatibility score (0-100%).
    """
    match_reasons: List[str] = []
    disqualification_reasons: List[str] = []
    eligibility_breakdown: Dict[str, Any] = {}

    # User Attributes
    user_qual_rank = normalize_qualification_rank(user_profile.get("highest_qualification", ""))
    job_qual_rank = normalize_qualification_rank(job.get("min_qualification_level", ""))
    
    # User Age
    user_dob = user_profile.get("date_of_birth", "2000-01-01")
    user_age = calculate_age(user_dob)
    
    # Government Age Limits (Including General 5-Year Age Relaxation)
    min_age = job.get("min_age", 18)
    max_age = job.get("max_age", 30)
    relaxation = job.get("age_relaxation_years", 5)
    effective_max_age = max_age + relaxation

    # Domicile / Quota
    user_domicile = user_profile.get("domicile", "").strip().lower()
    user_province = user_profile.get("province", "").strip().lower()
    
    # Parse allowed domiciles
    raw_domiciles = job.get("allowed_domiciles", "[]")
    if isinstance(raw_domiciles, str):
        try:
            allowed_domiciles = json.loads(raw_domiciles)
        except Exception:
            allowed_domiciles = [d.strip() for d in raw_domiciles.split(",") if d.strip()]
    else:
        allowed_domiciles = list(raw_domiciles)
    
    allowed_dom_lower = [d.lower() for d in allowed_domiciles]

    # Gender Check
    user_gender = user_profile.get("gender", "Both").strip().lower()
    job_gender = job.get("gender_eligibility", "Both").strip().lower()

    # User Experience
    user_exp = float(user_profile.get("years_of_experience", 0.0) or 0.0)
    job_exp = float(job.get("min_experience_years", 0.0) or 0.0)

    # -------------------------------------------------------------
    # 1. MANDATORY ELIGIBILITY GATES
    # -------------------------------------------------------------
    is_eligible = True

    # 1a. Qualification Rank Check
    if user_qual_rank < job_qual_rank:
        is_eligible = False
        reason = f"Requires at least {job.get('min_qualification_level')}; user holds {user_profile.get('highest_qualification')}."
        disqualification_reasons.append(reason)
        eligibility_breakdown["qualification"] = {"status": "FAIL", "message": reason}
    else:
        eligibility_breakdown["qualification"] = {
            "status": "PASS",
            "message": f"Qualification requirement satisfied ({user_profile.get('highest_qualification')} >= {job.get('min_qualification_level')})"
        }
        match_reasons.append(f"Meets or exceeds qualification level ({user_profile.get('highest_qualification')})")

    # 1b. Age Limit Check (Strict Government Rule)
    if user_age < min_age:
        is_eligible = False
        reason = f"Candidate age ({user_age} yrs) is below minimum age limit of {min_age} years."
        disqualification_reasons.append(reason)
        eligibility_breakdown["age"] = {"status": "FAIL", "message": reason}
    elif user_age > effective_max_age:
        is_eligible = False
        reason = f"Candidate age ({user_age} yrs) exceeds maximum limit of {effective_max_age} years ({max_age} + {relaxation} yrs general relaxation)."
        disqualification_reasons.append(reason)
        eligibility_breakdown["age"] = {"status": "FAIL", "message": reason}
    else:
        eligibility_breakdown["age"] = {
            "status": "PASS",
            "message": f"Age ({user_age} yrs) is within official government bracket ({min_age} - {effective_max_age} yrs with relaxation)"
        }
        match_reasons.append(f"Eligible age ({user_age} years old; limit is {effective_max_age})")

    # 1c. Domicile & Provincial Quota Check
    is_merit = any("merit" in d or "all pakistan" in d or "open" in d for d in allowed_dom_lower)
    matches_domicile = any(
        user_domicile in d or d in user_domicile or user_province in d or d in user_province
        for d in allowed_dom_lower
    )

    if not is_merit and not matches_domicile and len(allowed_domiciles) > 0:
        is_eligible = False
        reason = f"Seat quota allocated for {', '.join(allowed_domiciles)}; candidate domicile is {user_profile.get('domicile')} ({user_profile.get('province')})."
        disqualification_reasons.append(reason)
        eligibility_breakdown["domicile"] = {"status": "FAIL", "message": reason}
    else:
        matched_quota = "Open Merit / All Pakistan" if is_merit else user_profile.get("domicile")
        eligibility_breakdown["domicile"] = {
            "status": "PASS",
            "message": f"Domicile verified for quota ({matched_quota})"
        }
        match_reasons.append(f"Domicile ({user_profile.get('domicile')}) qualifies for post quota")

    # 1d. Gender Check
    if job_gender not in ["both", "all", "any", ""] and user_gender != "both":
        if job_gender != user_gender:
            is_eligible = False
            reason = f"Position reserved for {job.get('gender_eligibility')} applicants only."
            disqualification_reasons.append(reason)
            eligibility_breakdown["gender"] = {"status": "FAIL", "message": reason}
        else:
            eligibility_breakdown["gender"] = {"status": "PASS", "message": f"Gender eligibility met ({job.get('gender_eligibility')})"}
    else:
        eligibility_breakdown["gender"] = {"status": "PASS", "message": "Open to all genders"}

    # 1e. Experience Check
    if user_exp < job_exp:
        shortfall = job_exp - user_exp
        eligibility_breakdown["experience"] = {
            "status": "WARNING",
            "message": f"Requires {job_exp} years experience; candidate has {user_exp} years (short by {shortfall:.1f} yr)"
        }
        # If job strictly demands > 3 years and user has 0, flag as non-competitive
        if job_exp >= 3.0 and user_exp == 0:
            is_eligible = False
            reason = f"Requires mandatory {int(job_exp)} years professional experience (candidate has {user_exp} years)."
            disqualification_reasons.append(reason)
    else:
        eligibility_breakdown["experience"] = {
            "status": "PASS",
            "message": f"Experience criteria satisfied ({user_exp} yrs >= {job_exp} yrs required)"
        }
        if job_exp > 0:
            match_reasons.append(f"Possesses required professional experience ({user_exp} years)")

    # -------------------------------------------------------------
    # 2. WEIGHTED COMPATIBILITY SCORING (0 to 100%)
    # -------------------------------------------------------------
    if not is_eligible:
        # Strict cutoff: if mandatory rules fail, capped at max 25%
        raw_score = max(5, int(25 - (len(disqualification_reasons) * 7)))
        classification = "Not Eligible"
        return {
            "compatibility_score": raw_score,
            "classification": classification,
            "is_eligible": False,
            "eligibility_breakdown": eligibility_breakdown,
            "match_reasons": match_reasons,
            "disqualification_reasons": disqualification_reasons
        }

    # Weight 1: Degree & Field of Study Match (40 pts)
    field_ratio, field_desc = evaluate_field_match(
        user_field=user_profile.get("field_of_study", ""),
        user_degree=user_profile.get("degree_title", ""),
        job_field=job.get("field_of_study", ""),
        job_degree=job.get("required_degree", "")
    )
    score_field = field_ratio * 40.0
    if field_ratio >= 0.7:
        match_reasons.append(field_desc)

    # Weight 2: Experience Match (20 pts)
    if job_exp == 0:
        score_exp = 20.0
        match_reasons.append("Fresh graduates welcome (No prior experience required)")
    else:
        exp_ratio = min(1.5, user_exp / job_exp)
        score_exp = min(20.0, exp_ratio * 20.0)

    # Weight 3: Preferred Job Fields Alignment (15 pts)
    raw_user_fields = user_profile.get("preferred_job_fields", "[]")
    if isinstance(raw_user_fields, str):
        try:
            pref_fields = [f.lower() for f in json.loads(raw_user_fields)]
        except Exception:
            pref_fields = [f.strip().lower() for f in raw_user_fields.split(",") if f.strip()]
    else:
        pref_fields = [f.lower() for f in raw_user_fields]

    job_dept = job.get("department", "").lower()
    job_title = job.get("job_title", "").lower()
    job_field = job.get("field_of_study", "").lower()

    field_match_hit = any(
        pf in job_dept or pf in job_title or pf in job_field or job_field in pf
        for pf in pref_fields
    )
    if field_match_hit or not pref_fields:
        score_pref = 15.0
        match_reasons.append("Directly aligns with your selected career preferences")
    else:
        score_pref = 5.0

    # Weight 4: Location & Employment Type (15 pts)
    score_loc_emp = 0.0
    user_city = user_profile.get("city", "").lower()
    job_loc = job.get("location", "").lower()

    if "anywhere" in job_loc or "all pakistan" in job_loc or user_city in job_loc or user_province in job_loc:
        score_loc_emp += 10.0
        match_reasons.append(f"Location ({job.get('location')}) is favorable")
    else:
        score_loc_emp += 5.0

    user_emp_type = user_profile.get("preferred_employment_type", "Permanent").lower()
    job_emp_type = job.get("employment_type", "Permanent").lower()
    if user_emp_type in job_emp_type or "any" in user_emp_type:
        score_loc_emp += 5.0
        match_reasons.append(f"Preferred job type ({job.get('employment_type')}) matched")
    else:
        score_loc_emp += 2.0

    # Weight 5: Skills & Age Margin (10 pts)
    score_skills_age = 0.0
    # User Age Margin: comfortably within limit
    if user_age <= (max_age + 2):
        score_skills_age += 5.0

    # Skills overlap
    raw_skills = user_profile.get("skills", "[]")
    if isinstance(raw_skills, str):
        try:
            skills_list = json.loads(raw_skills)
        except Exception:
            skills_list = [s.strip() for s in raw_skills.split(",") if s.strip()]
    else:
        skills_list = list(raw_skills)

    matched_skills = [
        s for s in skills_list
        if s.lower() in job_title or s.lower() in job.get("required_degree", "").lower()
    ]
    if matched_skills:
        score_skills_age += 5.0
        match_reasons.append(f"Matches your key skills ({', '.join(matched_skills[:3])})")
    else:
        score_skills_age += 2.5

    # Total Score Calculation
    total_score = int(round(score_field + score_exp + score_pref + score_loc_emp + score_skills_age))
    total_score = max(35, min(99, total_score))

    # Classification
    if total_score >= 80:
        classification = "Highly Relevant"
    elif total_score >= 60:
        classification = "Relevant"
    else:
        classification = "Potentially Eligible"

    return {
        "compatibility_score": total_score,
        "classification": classification,
        "is_eligible": True,
        "eligibility_breakdown": eligibility_breakdown,
        "match_reasons": match_reasons,
        "disqualification_reasons": disqualification_reasons
    }

