import os
from datetime import datetime, timedelta, timezone

import jwt
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

import models
from database import get_db

load_dotenv()

# Reads JWT_SECRET_KEY from a local .env file (see .env.example).
# Falls back to a dev-only default so the project still runs out of
# the box, but you should always set your own secret before deploying
# anywhere public.
SECRET_KEY = os.environ.get("JWT_SECRET_KEY", "college-project-dev-secret-key-CHANGE-ME")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours

_security = HTTPBearer()


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "email": email, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired, please log in again",
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token",
        )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_security),
    db: Session = Depends(get_db),
) -> models.User:
    payload = decode_access_token(credentials.credentials)
    user_id = int(payload.get("sub"))

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user
