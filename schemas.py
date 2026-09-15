from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from enum import Enum


# ---------- Auth ----------
class UserCreate(BaseModel):
    name: str
    email: str
    password: str


class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    message: str
    access_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    user_id: Optional[int] = None
    name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


# ---------- Applications ----------
class ApplicationStatus(str, Enum):
    applied = "Applied"
    interview = "Interview"
    rejected = "Rejected"
    offer = "Offer"


class ApplicationCreate(BaseModel):
    company: str
    role: str
    status: ApplicationStatus
    notes: str


class ApplicationResponse(BaseModel):
    id: int
    company: str
    role: str
    status: ApplicationStatus
    notes: str
    user_id: int

    class Config:
        from_attributes = True


class DashboardResponse(BaseModel):
    total_applications: int
    applied: int
    interview: int
    offer: int
    rejected: int


# ---------- Resume Matching ----------
class MatchResultResponse(BaseModel):
    id: int
    resume_filename: str
    match_score: float
    skill_coverage: float
    text_similarity: float
    matched_skills: List[str]
    missing_skills: List[str]
    application_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True
