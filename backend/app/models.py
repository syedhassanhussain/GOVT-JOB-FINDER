"""
Pydantic Models and validation schemas for Government Job Finder & Career Assistant
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime


class UserRegister(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., min_length=5, max_length=150)
    phone: Optional[str] = None


class UserProfileCreate(BaseModel):
    highest_qualification: str = Field(..., description="e.g. Intermediate, Bachelor (14 Years), Bachelor (16 Years / BS), Master, MPhil / MS, PhD")
    degree_title: str = Field(..., description="e.g. BS Computer Science, MBA, M.Com, MBBS, LLB")
    field_of_study: str = Field(..., description="e.g. Computer Science / IT, Administration, Finance, Education, Engineering, Health, Police / Law Enforcement")
    institution: Optional[str] = None
    graduation_year: Optional[int] = None
    cgpa_or_percentage: Optional[str] = None
    date_of_birth: str = Field(..., description="YYYY-MM-DD")
    gender: str = Field(..., description="Male, Female, Transgender")
    province: str = Field(..., description="Punjab, Sindh (Urban), Sindh (Rural), Khyber Pakhtunkhwa, Balochistan, Islamabad (ICT), AJK, Gilgit-Baltistan")
    city: str
    domicile: str
    preferred_job_fields: List[str] = Field(default_factory=list)
    preferred_employment_type: str = Field(default="Permanent")
    preferred_locations: List[str] = Field(default_factory=list)
    years_of_experience: float = Field(default=0.0, ge=0)
    skills: List[str] = Field(default_factory=list)


class UserProfileUpdate(UserProfileCreate):
    pass


class JobSummary(BaseModel):
    id: int
    source_code: str
    case_or_ad_no: Optional[str] = None
    job_title: str
    department: str
    ministry_or_provincial_dept: Optional[str] = None
    bps_scale: Optional[str] = None
    min_qualification_level: str
    required_degree: str
    field_of_study: str
    min_experience_years: float
    min_age: int
    max_age: int
    age_relaxation_years: int
    allowed_domiciles: List[str]
    gender_eligibility: str
    location: str
    employment_type: str
    vacancies_count: int
    salary_or_scale: Optional[str] = None
    ad_date: Optional[str] = None
    closing_date: str
    application_fee: Optional[str] = None
    official_ad_url: str
    official_apply_url: str
    status: str
    verification_status: str


class JobDetail(JobSummary):
    required_documents: List[str]
    step_by_step_instructions: List[str]
    syllabus_or_test_info: Optional[str] = None
    last_verified_at: Optional[str] = None


class JobMatchDetail(BaseModel):
    job: JobDetail
    compatibility_score: int
    classification: str
    is_eligible: bool
    eligibility_breakdown: Dict[str, Any]
    match_reasons: List[str]
    disqualification_reasons: List[str]
    is_saved: bool = False
    is_applied: bool = False


class NotificationItem(BaseModel):
    id: int
    user_id: int
    job_id: Optional[int] = None
    title: str
    message: str
    type: str
    is_read: bool
    created_at: str


class AdminJobVerify(BaseModel):
    verification_status: str  # verified, rejected, pending_review
    status: Optional[str] = None  # open, closed, extended
