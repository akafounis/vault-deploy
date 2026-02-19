from fastapi import APIRouter, Request, Form, Depends, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, User
from auth import (
    hash_password, verify_password,
    create_session_token, COOKIE_NAME, SESSION_MAX_AGE,
    get_current_user, create_reset_token, decode_reset_token
)
from email_utils import send_password_reset_email, send_welcome_email

router = APIRouter()
templates = Jinja2Templates(directory="templates")


# ─── Register ─────────────────────────────────────────────────────────────────

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/dashboard", 302)
    return templates.TemplateResponse("register.html", {"request": request, "error": None})


@router.post("/register")
async def register(
    request: Request,
    full_name: str = Form(...),
    email: str     = Form(...),
    password: str  = Form(...),
    confirm: str   = Form(...),
    db: Session    = Depends(get_db)
):
    error = None

    if password != confirm:
        error = "Passwords do not match."
    elif len(password) < 8:
        error = "Password must be at least 8 characters."
    elif db.query(User).filter(User.email == email.lower()).first():
        error = "An account with this email already exists."

    if error:
        return templates.TemplateResponse("register.html", {"request": request, "error": error}, status_code=400)

    user = User(
        email=email.lower().strip(),
        hashed_password=hash_password(password),
        full_name=full_name.strip()
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    send_welcome_email(user.email, user.full_name)

    response = RedirectResponse("/dashboard", status_code=302)
    token = create_session_token(user.id)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return response


# ─── Login ────────────────────────────────────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, db: Session = Depends(get_db)):
    if get_current_user(request, db):
        return RedirectResponse("/dashboard", 302)
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@router.post("/login")
async def login(
    request: Request,
    email: str    = Form(...),
    password: str = Form(...),
    db: Session   = Depends(get_db)
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Invalid email or password."},
            status_code=401
        )

    if not user.is_active:
        return templates.TemplateResponse(
            "login.html",
            {"request": request, "error": "Your account has been deactivated."},
            status_code=403
        )

    response = RedirectResponse("/dashboard", status_code=302)
    token = create_session_token(user.id)
    response.set_cookie(COOKIE_NAME, token, max_age=SESSION_MAX_AGE, httponly=True, samesite="lax")
    return response


# ─── Logout ───────────────────────────────────────────────────────────────────

@router.get("/logout")
async def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


# ─── Forgot Password ──────────────────────────────────────────────────────────

@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_page(request: Request):
    return templates.TemplateResponse("forgot_password.html", {"request": request, "sent": False, "error": None})


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    email: str  = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email.lower().strip()).first()

    # Always show success to prevent email enumeration
    if user:
        token = create_reset_token(user.email)
        send_password_reset_email(user.email, token)

    return templates.TemplateResponse("forgot_password.html", {"request": request, "sent": True, "error": None})


# ─── Reset Password ───────────────────────────────────────────────────────────

@router.get("/reset-password/{token}", response_class=HTMLResponse)
async def reset_page(request: Request, token: str, db: Session = Depends(get_db)):
    email = decode_reset_token(token)
    if not email:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "valid": False, "token": token, "error": "This link is invalid or has expired."
        })
    return templates.TemplateResponse("reset_password.html", {
        "request": request, "valid": True, "token": token, "error": None
    })


@router.post("/reset-password/{token}")
async def reset_password(
    request: Request,
    token: str,
    password: str = Form(...),
    confirm: str  = Form(...),
    db: Session   = Depends(get_db)
):
    email = decode_reset_token(token)
    if not email:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "valid": False, "token": token,
            "error": "This link is invalid or has expired."
        })

    if password != confirm:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "valid": True, "token": token,
            "error": "Passwords do not match."
        })

    if len(password) < 8:
        return templates.TemplateResponse("reset_password.html", {
            "request": request, "valid": True, "token": token,
            "error": "Password must be at least 8 characters."
        })

    user = db.query(User).filter(User.email == email).first()
    if user:
        user.hashed_password = hash_password(password)
        db.commit()

    return RedirectResponse("/login?reset=1", status_code=302)
