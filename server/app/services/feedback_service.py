import json
import os
import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.feedback import Feedback

UPLOAD_DIR = "uploads/feedback"


def _save_images(user_id: int, images: list[UploadFile] | None) -> list[str]:
    if not images:
        return []
    paths: list[str] = []
    for img in images:
        if img.filename is None or img.filename == "":
            continue
        ext = os.path.splitext(img.filename)[1] or ".jpg"
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        filename = f"{ts}_{uuid.uuid4().hex[:8]}{ext}"
        subdir = os.path.join(UPLOAD_DIR, str(user_id))
        os.makedirs(subdir, exist_ok=True)
        filepath = os.path.join(subdir, filename)
        content = img.file.read()
        with open(filepath, "wb") as f:
            f.write(content)
        paths.append(f"/{filepath.replace(os.sep, '/')}")
    return paths


def create_feedback(
    user_id: int,
    content: str,
    images: list[UploadFile] | None,
    db: Session,
) -> Feedback:
    if not content or not content.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Content is required")

    image_paths = _save_images(user_id, images)

    fb = Feedback(
        user_id=user_id,
        content=content.strip(),
        images=json.dumps(image_paths) if image_paths else None,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def list_feedback(page: int, page_size: int, db: Session) -> dict:
    query = db.query(Feedback).order_by(Feedback.id.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()

    result = []
    for fb in items:
        images = json.loads(fb.images) if fb.images else None
        result.append({
            "id": fb.id,
            "user_id": fb.user_id,
            "email": None,
            "content": fb.content,
            "images": images,
            "created_at": fb.created_at,
        })

    return {"items": result, "total": total, "page": page, "page_size": page_size}
