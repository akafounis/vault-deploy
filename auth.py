from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from fastapi import Request, HTTPException, Depends
from sqlalchemy.orm import Session
from database import get_db, User
import os
import bcrypt

# ─── Password Hashing ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt()).decode("utf-8")

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8")[:72], hashed.encode("utf-8"))


# ─── Session Cookie Auth ──────────────────────────────────────────────────────

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-32-chars-min!")
serializer = URLSafeTimedSerializer(SECRET_KEY)
COOKIE_NAME = "vault_session"
SESSION_MAX_AGE = 60 * 60 * 24 * 7   # 7 days in seconds


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def decode_session_token(token: str, max_age: int = SESSION_MAX_AGE):
    try:
        data = serializer.loads(token, max_age=max_age)
        return data.get("user_id")
    except (SignatureExpired, BadSignature):
        return None


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    user_id = decode_session_token(token)
    if not user_id:
        return None
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    return user


def require_user(request: Request, db: Session = Depends(get_db)) -> User:
    user = get_current_user(request, db)
    if not user:
        raise HTTPException(status_code=302, headers={"Location": "/login"})
    return user


# ─── Password Reset Token ─────────────────────────────────────────────────────

RESET_SECRET = SECRET_KEY + "-reset"
reset_serializer = URLSafeTimedSerializer(RESET_SECRET)

def create_reset_token(email: str) -> str:
    return reset_serializer.dumps(email, salt="password-reset")

def decode_reset_token(token: str, max_age: int = 3600) -> str | None:
    """Returns email or None if invalid/expired."""
    try:
        email = reset_serializer.loads(token, salt="password-reset", max_age=max_age)
        return email
    except (SignatureExpired, BadSignature):
        return None
