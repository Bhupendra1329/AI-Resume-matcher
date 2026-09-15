import json

from passlib.context import CryptContext
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import Optional

import models
import schemas
import nlp_engine
import file_parser

from database import engine, get_db
from auth import create_access_token, get_current_user

# Create tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Resume Matcher & Job Application Assistant")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str):
    return pwd_context.hash(password)


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


@app.get("/api")
def home():
    return {"message": "AI Resume Matcher API Running"}


# ============================================================
# AUTH
# ============================================================

@app.post("/register")
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    existing_user = db.query(models.User).filter(models.User.email == user.email).first()
    if existing_user:
        return {"message": "Email already registered"}

    new_user = models.User(
        name=user.name,
        email=user.email,
        password=hash_password(user.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"message": "User Registered Successfully", "user_id": new_user.id}


@app.post("/login", response_model=schemas.TokenResponse)
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()

    if not db_user:
        return {"message": "Invalid Email"}

    if not verify_password(user.password, db_user.password):
        return {"message": "Invalid Password"}

    token = create_access_token(db_user.id, db_user.email)

    return {
        "message": "Login Successful",
        "access_token": token,
        "token_type": "bearer",
        "user_id": db_user.id,
        "name": db_user.name,
    }


@app.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


# ============================================================
# APPLICATIONS  (all scoped to the authenticated user)
# ============================================================

@app.post("/applications")
def add_application(
    application: schemas.ApplicationCreate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    new_application = models.Application(
        company=application.company,
        role=application.role,
        status=application.status,
        notes=application.notes,
        user_id=current_user.id,
    )
    db.add(new_application)
    db.commit()
    db.refresh(new_application)

    return {"message": "Application Added Successfully", "application_id": new_application.id}


@app.get("/applications/search", response_model=list[schemas.ApplicationResponse])
def search_applications(
    company: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    applications = (
        db.query(models.Application)
        .filter(models.Application.user_id == current_user.id)
        .filter(models.Application.company.contains(company))
        .all()
    )
    return applications


@app.get("/applications", response_model=list[schemas.ApplicationResponse])
def get_applications(
    status: Optional[schemas.ApplicationStatus] = None,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    query = db.query(models.Application).filter(models.Application.user_id == current_user.id)
    if status:
        query = query.filter(models.Application.status == status)
    return query.all()


@app.get("/applications/{app_id}", response_model=schemas.ApplicationResponse)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == app_id, models.Application.user_id == current_user.id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application Not Found")
    return application


@app.put("/applications/{app_id}")
def update_application(
    app_id: int,
    status: schemas.ApplicationStatus,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == app_id, models.Application.user_id == current_user.id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application Not Found")

    application.status = status
    db.commit()

    return {"message": "Application Updated Successfully"}


@app.delete("/applications/{app_id}")
def delete_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    application = (
        db.query(models.Application)
        .filter(models.Application.id == app_id, models.Application.user_id == current_user.id)
        .first()
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application Not Found")

    db.delete(application)
    db.commit()

    return {"message": "Application Deleted Successfully"}


@app.get("/dashboard", response_model=schemas.DashboardResponse)
def get_dashboard(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    base = db.query(models.Application).filter(models.Application.user_id == current_user.id)

    return {
        "total_applications": base.count(),
        "applied": base.filter(models.Application.status == "Applied").count(),
        "interview": base.filter(models.Application.status == "Interview").count(),
        "offer": base.filter(models.Application.status == "Offer").count(),
        "rejected": base.filter(models.Application.status == "Rejected").count(),
    }


# ============================================================
# RESUME MATCHING
# ============================================================

@app.post("/match/analyze", response_model=schemas.MatchResultResponse)
async def analyze_resume(
    job_description: str = Form(...),
    application_id: Optional[int] = Form(None),
    resume: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    if application_id is not None:
        owned = (
            db.query(models.Application)
            .filter(models.Application.id == application_id, models.Application.user_id == current_user.id)
            .first()
        )
        if not owned:
            raise HTTPException(status_code=404, detail="Application Not Found")

    file_bytes = await resume.read()
    try:
        resume_text = file_parser.extract_text(resume.filename, file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not resume_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from that resume. Try a different file.",
        )

    result = nlp_engine.analyze_match(resume_text, job_description)

    match_row = models.MatchResult(
        user_id=current_user.id,
        application_id=application_id,
        resume_filename=resume.filename,
        match_score=result["match_score"],
        skill_coverage=result["skill_coverage"],
        text_similarity=result["text_similarity"],
        matched_skills=json.dumps(result["matched_skills"]),
        missing_skills=json.dumps(result["missing_skills"]),
    )
    db.add(match_row)
    db.commit()
    db.refresh(match_row)

    return schemas.MatchResultResponse(
        id=match_row.id,
        resume_filename=match_row.resume_filename,
        match_score=match_row.match_score,
        skill_coverage=match_row.skill_coverage,
        text_similarity=match_row.text_similarity,
        matched_skills=result["matched_skills"],
        missing_skills=result["missing_skills"],
        application_id=match_row.application_id,
        created_at=match_row.created_at,
    )


@app.get("/match/history", response_model=list[schemas.MatchResultResponse])
def match_history(
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    rows = (
        db.query(models.MatchResult)
        .filter(models.MatchResult.user_id == current_user.id)
        .order_by(models.MatchResult.created_at.desc())
        .all()
    )
    return [
        schemas.MatchResultResponse(
            id=r.id,
            resume_filename=r.resume_filename,
            match_score=r.match_score,
            skill_coverage=r.skill_coverage,
            text_similarity=r.text_similarity,
            matched_skills=json.loads(r.matched_skills),
            missing_skills=json.loads(r.missing_skills),
            application_id=r.application_id,
            created_at=r.created_at,
        )
        for r in rows
    ]


# Serve the frontend last so it doesn't shadow the API routes above.
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")
