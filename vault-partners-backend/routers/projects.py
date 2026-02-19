from fastapi import APIRouter, Request, Form, Depends, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db, User, Project, ProjectFile
from auth import get_current_user
import os, uuid, shutil, mimetypes

try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

router = APIRouter()
templates = Jinja2Templates(directory="templates")

PROJECTS_DIR = "uploads/projects"
THUMBS_DIR   = "uploads/thumbnails"
os.makedirs(PROJECTS_DIR, exist_ok=True)
os.makedirs(THUMBS_DIR, exist_ok=True)

MAX_FILE_BYTES = int(os.getenv("MAX_FILE_SIZE_MB", "50")) * 1024 * 1024

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
IMAGE_EXTS  = {"jpg", "jpeg", "png", "webp", "gif"}


def _human_size(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _is_image(upload: UploadFile) -> bool:
    if upload.content_type in IMAGE_TYPES:
        return True
    ext = upload.filename.rsplit(".", 1)[-1].lower() if "." in upload.filename else ""
    return ext in IMAGE_EXTS


def _make_thumbnail(src_path: str) -> str | None:
    """Create a 600x400 thumbnail. Returns stored filename or None."""
    if not HAS_PIL:
        # No Pillow — just copy the original as thumbnail
        thumb_name = f"thumb_{uuid.uuid4().hex}.jpg"
        thumb_path = os.path.join(THUMBS_DIR, thumb_name)
        shutil.copy2(src_path, thumb_path)
        return thumb_name
    try:
        thumb_name = f"thumb_{uuid.uuid4().hex}.jpg"
        thumb_path = os.path.join(THUMBS_DIR, thumb_name)
        img = PILImage.open(src_path)
        img = img.convert("RGB")
        img.thumbnail((800, 500), PILImage.LANCZOS)
        # Crop to exact 800x500 with center crop
        w, h = img.size
        target_w, target_h = 800, 500
        ratio = max(target_w / w, target_h / h)
        new_w, new_h = int(w * ratio), int(h * ratio)
        img = img.resize((new_w, new_h), PILImage.LANCZOS)
        left = (new_w - target_w) // 2
        top  = (new_h - target_h) // 2
        img = img.crop((left, top, left + target_w, top + target_h))
        img.save(thumb_path, "JPEG", quality=85, optimize=True)
        return thumb_name
    except Exception as e:
        print(f"[THUMB ERROR] {e}")
        return None


def _save_file(content: bytes, filename: str) -> str:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    stored_name = f"{uuid.uuid4().hex}.{ext}"
    dest = os.path.join(PROJECTS_DIR, stored_name)
    with open(dest, "wb") as f:
        f.write(content)
    return stored_name, dest


def _process_uploads(files, project_id, db):
    """Save all uploaded files. Sets thumbnail on project if an image is found."""
    from database import Project as ProjectModel
    project = db.query(ProjectModel).filter(ProjectModel.id == project_id).first()
    first_image_set = project.thumbnail is not None  # already has one

    for upload in files:
        if not upload.filename:
            continue

        content = upload.read() if not hasattr(upload, '_content') else upload._content
        if len(content) > MAX_FILE_BYTES:
            continue

        stored_name, dest = _save_file(content, upload.filename)

        pf = ProjectFile(
            project_id=project_id,
            filename=stored_name,
            original_name=upload.filename,
            file_size=len(content),
            mime_type=upload.content_type
        )
        db.add(pf)

        # Auto-set thumbnail from first image uploaded
        if not first_image_set and _is_image(upload):
            thumb = _make_thumbnail(dest)
            if thumb:
                project.thumbnail = thumb
                first_image_set = True

    db.commit()


# ─── Dashboard ────────────────────────────────────────────────────────────────

@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    projects = db.query(Project).filter(Project.owner_id == user.id)\
                 .order_by(Project.created_at.desc()).all()

    return templates.TemplateResponse("dashboard.html", {
        "request": request, "user": user,
        "projects": projects, "human_size": _human_size
    })


@router.get("/projects", response_class=HTMLResponse)
async def projects_list(request: Request):
    return RedirectResponse("/dashboard", 302)


# ─── New Project ──────────────────────────────────────────────────────────────

@router.get("/projects/new", response_class=HTMLResponse)
async def new_project_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)
    return templates.TemplateResponse("project_form.html", {
        "request": request, "user": user, "project": None, "error": None
    })


@router.post("/projects/new")
async def create_project(
    request: Request,
    title:       str = Form(...),
    description: str = Form(""),
    category:    str = Form(""),
    status:      str = Form("active"),
    tags:        str = Form(""),
    files: list[UploadFile] = File([]),
    db: Session  = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = Project(
        title=title.strip(), description=description.strip(),
        category=category.strip(), status=status,
        tags=tags.strip(), owner_id=user.id
    )
    db.add(project)
    db.commit()
    db.refresh(project)

    first_image_set = False
    for upload in files:
        if not upload.filename:
            continue
        content = await upload.read()
        if len(content) > MAX_FILE_BYTES:
            continue

        stored_name, dest = _save_file(content, upload.filename)

        pf = ProjectFile(
            project_id=project.id, filename=stored_name,
            original_name=upload.filename,
            file_size=len(content), mime_type=upload.content_type
        )
        db.add(pf)

        if not first_image_set and _is_image(upload):
            thumb = _make_thumbnail(dest)
            if thumb:
                project.thumbnail = thumb
                first_image_set = True

    db.commit()
    return RedirectResponse(f"/projects/{project.id}", status_code=302)


# ─── Project Detail ───────────────────────────────────────────────────────────

@router.get("/projects/{project_id}", response_class=HTMLResponse)
async def project_detail(request: Request, project_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if not project:
        return RedirectResponse("/dashboard", 302)

    return templates.TemplateResponse("project_detail.html", {
        "request": request, "user": user, "project": project,
        "human_size": _human_size, "success": request.query_params.get("saved")
    })


# ─── Edit Project ─────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/edit", response_class=HTMLResponse)
async def edit_project_page(request: Request, project_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if not project:
        return RedirectResponse("/dashboard", 302)

    return templates.TemplateResponse("project_form.html", {
        "request": request, "user": user, "project": project, "error": None
    })


@router.post("/projects/{project_id}/edit")
async def update_project(
    request: Request,
    project_id: int,
    title:       str = Form(...),
    description: str = Form(""),
    category:    str = Form(""),
    status:      str = Form("active"),
    tags:        str = Form(""),
    files: list[UploadFile] = File([]),
    db: Session  = Depends(get_db)
):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if not project:
        return RedirectResponse("/dashboard", 302)

    project.title       = title.strip()
    project.description = description.strip()
    project.category    = category.strip()
    project.status      = status
    project.tags        = tags.strip()

    for upload in files:
        if not upload.filename:
            continue
        content = await upload.read()
        if len(content) > MAX_FILE_BYTES:
            continue

        stored_name, dest = _save_file(content, upload.filename)

        pf = ProjectFile(
            project_id=project.id, filename=stored_name,
            original_name=upload.filename,
            file_size=len(content), mime_type=upload.content_type
        )
        db.add(pf)

        # Set thumbnail if project doesn't have one yet and this is an image
        if not project.thumbnail and _is_image(upload):
            thumb = _make_thumbnail(dest)
            if thumb:
                project.thumbnail = thumb

    db.commit()
    return RedirectResponse(f"/projects/{project_id}?saved=1", status_code=302)


# ─── Delete Project ───────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/delete")
async def delete_project(request: Request, project_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if project:
        for pf in project.files:
            path = os.path.join(PROJECTS_DIR, pf.filename)
            if os.path.exists(path):
                os.remove(path)
        if project.thumbnail:
            tp = os.path.join(THUMBS_DIR, project.thumbnail)
            if os.path.exists(tp):
                os.remove(tp)
        db.delete(project)
        db.commit()

    return RedirectResponse("/dashboard", status_code=302)


# ─── Delete File ──────────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/files/{file_id}/delete")
async def delete_file(request: Request, project_id: int, file_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if not project:
        return RedirectResponse("/dashboard", 302)

    pf = db.query(ProjectFile).filter(
        ProjectFile.id == file_id, ProjectFile.project_id == project_id
    ).first()
    if pf:
        path = os.path.join(PROJECTS_DIR, pf.filename)
        if os.path.exists(path):
            os.remove(path)
        db.delete(pf)
        db.commit()

    return RedirectResponse(f"/projects/{project_id}?saved=1", status_code=302)


# ─── Download File ────────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/files/{file_id}/download")
async def download_file(request: Request, project_id: int, file_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if not project:
        return RedirectResponse("/dashboard", 302)

    pf = db.query(ProjectFile).filter(
        ProjectFile.id == file_id, ProjectFile.project_id == project_id
    ).first()
    if not pf:
        return RedirectResponse(f"/projects/{project_id}", 302)

    path = os.path.join(PROJECTS_DIR, pf.filename)
    return FileResponse(path, filename=pf.original_name,
                        media_type=pf.mime_type or "application/octet-stream")


# ─── Remove Thumbnail ─────────────────────────────────────────────────────────

@router.post("/projects/{project_id}/thumbnail/remove")
async def remove_thumbnail(request: Request, project_id: int, db: Session = Depends(get_db)):
    user = get_current_user(request, db)
    if not user:
        return RedirectResponse("/login", 302)

    project = db.query(Project).filter(
        Project.id == project_id, Project.owner_id == user.id
    ).first()
    if project and project.thumbnail:
        tp = os.path.join(THUMBS_DIR, project.thumbnail)
        if os.path.exists(tp):
            os.remove(tp)
        project.thumbnail = None
        db.commit()

    return RedirectResponse(f"/projects/{project_id}/edit?saved=1", status_code=302)
