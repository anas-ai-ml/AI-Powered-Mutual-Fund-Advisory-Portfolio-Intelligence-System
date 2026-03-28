import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from backend.database.connection import get_db
from backend.database.models import Advisor


SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not set. Configure it in .env before starting the API.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)
router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: Literal["advisor", "admin"] = "advisor"


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def create_access_token(*, advisor_id: int, role: str, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": email,
        "advisor_id": advisor_id,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _serialize_advisor(advisor: Advisor) -> dict:
    return {
        "id": advisor.id,
        "email": advisor.email,
        "name": advisor.name,
        "role": advisor.role,
        "created_at": advisor.created_at.isoformat() if advisor.created_at else None,
    }


def get_current_advisor(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Advisor:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authorization header",
        )

    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        advisor_id = int(payload.get("advisor_id"))
    except (JWTError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    advisor = db.query(Advisor).filter(Advisor.id == advisor_id).first()
    if advisor is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Advisor not found",
        )
    return advisor


@router.post("/register")
def register_advisor(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(Advisor).filter(Advisor.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Advisor already exists")

    advisor = Advisor(
        email=payload.email,
        hashed_password=get_password_hash(payload.password),
        name=payload.name.strip(),
        role=payload.role,
    )
    try:
        db.add(advisor)
        db.commit()
        db.refresh(advisor)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to register advisor: {exc}")

    token = create_access_token(
        advisor_id=advisor.id,
        role=advisor.role,
        email=advisor.email,
    )
    return {"access_token": token, "token_type": "bearer", "advisor": _serialize_advisor(advisor)}


@router.post("/login")
def login_advisor(payload: LoginRequest, db: Session = Depends(get_db)):
    advisor = db.query(Advisor).filter(Advisor.email == payload.email).first()
    if advisor is None or not verify_password(payload.password, advisor.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(
        advisor_id=advisor.id,
        role=advisor.role,
        email=advisor.email,
    )
    return {"access_token": token, "token_type": "bearer", "advisor": _serialize_advisor(advisor)}


@router.get("/me")
def get_me(current_advisor: Advisor = Depends(get_current_advisor)):
    return _serialize_advisor(current_advisor)
