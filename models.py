from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    password = Column(String)

    applications = relationship(
        "Application",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    match_results = relationship(
        "MatchResult",
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Application(Base):
    __tablename__ = "applications"

    id = Column(Integer, primary_key=True, index=True)

    company = Column(String)
    role = Column(String)
    status = Column(String)
    notes = Column(String)

    user_id = Column(Integer, ForeignKey("users.id"))

    user = relationship("User", back_populates="applications")
    match_results = relationship(
        "MatchResult",
        back_populates="application",
        cascade="all, delete-orphan",
    )


class MatchResult(Base):
    __tablename__ = "match_results"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"))
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=True)

    resume_filename = Column(String)
    match_score = Column(Float)
    skill_coverage = Column(Float)
    text_similarity = Column(Float)
    matched_skills = Column(Text)   # JSON-encoded list
    missing_skills = Column(Text)   # JSON-encoded list

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="match_results")
    application = relationship("Application", back_populates="match_results")
