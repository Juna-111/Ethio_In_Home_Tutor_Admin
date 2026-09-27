from datetime import datetime
from enum import Enum
import re
from typing import Any, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StudentLevel(str, Enum):
    PRIMARY_1_4 = "Primary 1-4"
    PRIMARY_5_8 = "Primary 5-8"
    HIGH_SCHOOL_9_10 = "High School 9-10"
    PREP_11_12 = "Prep 11-12"
    FRESHMAN = "Freshman"


class PreferredGender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"
    NO_PREFERENCE = "No preference"


class TutorGender(str, Enum):
    MALE = "Male"
    FEMALE = "Female"


class PreferredExperience(str, Enum):
    UNIVERSITY_STUDENT = "University Student"
    FRESH_GRADUATE = "Fresh Graduate"
    SENIOR_TEACHER = "Senior Teacher"


class ParentStatus(str, Enum):
    PENDING = "pending"
    MATCHED = "matched"
    CLOSED = "closed"


class TutorStatus(str, Enum):
    PENDING = "pending"
    VERIFIED = "verified"
    PROBATION = "probation"
    REJECTED = "rejected"


def normalize_ethiopian_phone(value: str) -> str:
    """Normalize Ethiopian mobile numbers to +2519... or +2517... E.164 form."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("00"):
        digits = digits[2:]
    if digits.startswith("251"):
        local = digits[3:]
    elif digits.startswith(("09", "07")):
        local = digits[1:]
    elif digits.startswith(("9", "7")):
        local = digits
    else:
        raise ValueError("Enter a valid Ethiopian mobile number starting with 09, 07, +2519, or +2517.")

    if len(local) != 9 or local[0] not in "97":
        raise ValueError("Enter a valid 9-digit Ethiopian mobile number.")
    return f"+251{local}"


# ==========================================
# Parent Request Schemas
# ==========================================

class ParentRequestCreate(BaseModel):
    telegram_user_id: Optional[int] = Field(None, description="Telegram User ID if submitted via Telegram")
    parent_name: str = Field(..., min_length=2, max_length=150, description="Parent's full name")
    phone_number: str = Field(..., min_length=7, max_length=50, description="Primary contact phone number")
    student_level: str = Field(..., description="Student educational level")
    subjects: List[str] = Field(..., min_length=1, description="List of subjects needed")
    preferred_gender: str = Field(default="No preference", description="Tutor gender preference")
    preferred_experience: str = Field(..., description="Desired tutor background/experience")
    location_subcity: str = Field(..., min_length=2, max_length=100, description="Addis Ababa subcity")
    location_landmark: Optional[str] = Field(None, max_length=255, description="Nearby landmark/area")
    schedule_days: Union[List[str], str] = Field(..., description="Days preferred for tutoring")
    time_slot: str = Field(..., description="Preferred time of day (e.g., 4:30 PM - 6:30 PM)")
    session_duration: str = Field(..., description="Duration per session (e.g. 1 hr, 1.5 hrs, 2 hrs)")
    budget_etb: float = Field(..., gt=0, description="Budget in Ethiopian Birr")

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_ethiopian_phone(value)


class ParentRequestResponse(ParentRequestCreate):
    id: int
    status: str
    telegram_topic_id: Optional[int] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Tutor Schemas
# ==========================================

class TutorCreate(BaseModel):
    telegram_user_id: Optional[int] = Field(None, description="Telegram User ID if registered via Telegram")
    full_name: str = Field(..., min_length=2, max_length=150, description="Tutor full legal name")
    gender: str = Field(..., description="Gender: Male or Female")
    phone_number: str = Field(..., min_length=7, max_length=50, description="Active phone number")
    university: str = Field(..., min_length=2, max_length=150, description="University attended/attending")
    department: str = Field(..., min_length=2, max_length=150, description="Field of study / department")
    education_year: str = Field(..., description="Year of study or Graduate status")
    subjects_qualified: List[str] = Field(..., min_length=1, description="Subjects the tutor is qualified to teach")
    grades_qualified: List[str] = Field(..., min_length=1, description="Grade levels the tutor can teach")
    years_of_experience: float = Field(0.0, ge=0.0, description="Years of teaching/tutoring experience")
    expected_fee_etb: float = Field(..., gt=0, description="Expected fee in ETB (per hour or month)")
    base_subcity: str = Field(..., min_length=2, max_length=100, description="Subcity where tutor resides")
    coverage_areas: List[str] = Field(..., min_length=1, description="Subcities tutor is willing to travel to")
    availability_schedule: Union[dict, List[str], str] = Field(..., description="Available days and time slots")
    id_document_url: Optional[str] = Field(None, max_length=2048, description="URL or Telegram file ID of student/national ID")
    entrance_result: Optional[float] = Field(None, ge=0, description="Numeric entrance exam result")

    @field_validator("phone_number", mode="before")
    @classmethod
    def normalize_phone(cls, value: str) -> str:
        return normalize_ethiopian_phone(value)


class TutorResponse(TutorCreate):
    id: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==========================================
# Health Schema
# ==========================================

class HealthResponse(BaseModel):
    status: str
    database: str


class AdminDashboardResponse(BaseModel):
    admin_telegram_id: int
    admin_role: str
    pending_tutors: int
    pending_requests: int
    active_assignments: int
    requests_today: int


class AdminRequestListItem(BaseModel):
    id: int
    parent_name: str
    location_subcity: str
    student_level: str
    subjects: List[str]
    preferred_gender: str
    budget_etb: float
    status: str
    created_at: datetime


class AdminRequestListResponse(BaseModel):
    items: List[AdminRequestListItem]
    total: int
    page: int
    page_size: int


class AdminCandidateResponse(BaseModel):
    tutor_id: int
    full_name: str
    gender: str
    university: str
    department: str
    education_year: str
    subjects_qualified: List[str]
    grades_qualified: List[str]
    years_of_experience: float
    expected_fee_etb: float
    base_subcity: str
    coverage_areas: List[str]
    availability_schedule: Any
    tier: str
    matched_subjects: List[str]
    match_reasons: List[str]
    overall_score: float
    score_breakdown: dict[str, dict[str, Any]]
    invite_status: Optional[str] = None
    telegram_available: bool


class AdminCandidatesResponse(BaseModel):
    request_id: int
    candidates: List[AdminCandidateResponse]


class AdminCoverageGapResponse(BaseModel):
    subcity: str
    subject: str
    pending_requests: int
    approved_tutors: int
    gap_ratio: float


class AdminIdleTutorResponse(BaseModel):
    id: int
    full_name: str
    phone_number: str
    telegram_user_id: Optional[int]
    base_subcity: str
    subjects_qualified: List[str]
    last_assigned_at: Optional[datetime] = None


class AdminPingRequest(BaseModel):
    tutor_ids: List[int] = Field(..., min_length=1, max_length=20)


class AdminAssignRequest(BaseModel):
    tutor_id: int = Field(..., gt=0)


class AdminActionResponse(BaseModel):
    ok: bool
    message: str
