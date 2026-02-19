from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, User
from auth import get_current_user, hash_password, verify_password
import os, uuid, shutil
try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

router = APIRouter()
templates = Jinja2Templates(directory="templates")

AVATAR_DIR = "uploads/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}


def _save_avatar(upload: UploadFile) -> str:
    """Saves avatar, returns stored filename."""
    ext = upload.filename.rsplit(".", 1)[-1].lower()
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(AVATAR_DIR, filename)

    with open(path, "wb") as f:
        shutil.copyfileobj(upload.file, f)

    # Resize to max 400x400 (only if Pillow is installed)
    if HAS_PIL:
        try:
            img = Image.open(path)
            img.thumbnail((400, 400))
            img.save(path)
        except Exception:
            pass

    return filename


# ─── Profile View ─────────────────────────────────────────────────────────────

@router.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "user": user,
        "success": request.query_params.get("saved"),
        "error": None
    })


# ─── Update Profile Info ──────────────────────────────────────────────────────

@router.post("/profile")
async def update_profile(
    request: Request,
    full_name: str = Form(""),
    company:   str = Form(""),
    job_title: str = Form(""),
    phone:     str = Form(""),
    bio:       str = Form(""),
    linkedin:  str = Form(""),
    website:   str = Form(""),
    db: Session    = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    user.full_name = full_name.strip()
    user.company   = company.strip()
    user.job_title = job_title.strip()
    user.phone     = phone.strip()
    user.bio       = bio.strip()
    user.linkedin  = linkedin.strip()
    user.website   = website.strip()
    db.commit()

    return RedirectResponse("/profile?saved=1", status_code=302)


# ─── Upload Avatar ────────────────────────────────────────────────────────────

@router.post("/profile/avatar")
async def upload_avatar(
    request: Request,
    avatar: UploadFile = File(...),
    db: Session        = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    if avatar.content_type not in ALLOWED_IMAGE_TYPES:
        return templates.TemplateResponse("profile.html", {
            "request": request, "user": user,
            "error": "Only JPEG, PNG, WebP or GIF images are allowed.",
            "success": None
        }, status_code=400)

    # Delete old avatar
    if user.avatar:
        old_path = os.path.join(AVATAR_DIR, user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)

    filename = _save_avatar(avatar)
    user.avatar = filename
    db.commit()

    return RedirectResponse("/profile?saved=1", status_code=302)


# ─── Remove Avatar ────────────────────────────────────────────────────────────

@router.post("/profile/avatar/remove")
async def remove_avatar(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    if user.avatar:
        old_path = os.path.join(AVATAR_DIR, user.avatar)
        if os.path.exists(old_path):
            os.remove(old_path)
        user.avatar = None
        db.commit()

    return RedirectResponse("/profile?saved=1", status_code=302)


# ─── Change Password ──────────────────────────────────────────────────────────

@router.post("/profile/change-password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password:     str = Form(...),
    confirm_password: str = Form(...),
    db: Session           = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    def error(msg):
        return templates.TemplateResponse("profile.html", {
            "request": request, "user": user,
            "error": msg, "success": None, "tab": "security"
        }, status_code=400)

    if not verify_password(current_password, user.hashed_password):
        return error("Current password is incorrect.")
    if new_password != confirm_password:
        return error("New passwords do not match.")
    if len(new_password) < 8:
        return error("Password must be at least 8 characters.")

    user.hashed_password = hash_password(new_password)
    db.commit()
    return RedirectResponse("/profile?saved=1&tab=security", status_code=302)
