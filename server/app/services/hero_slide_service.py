import logging
import os
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.hero_slide import HeroSlide
from app.schemas.hero_slide import HeroSlideResponse


HERO_SLIDE_SLOT_INDEXES = (1, 2, 3)
HERO_SLIDE_UPLOAD_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")) / "hero-slides"
HERO_SLIDE_URL_PREFIX = "/uploads/hero-slides"
ALLOWED_HERO_SLIDE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
logger = logging.getLogger("friendauto.hero_slides")


def ensure_hero_slide_slots(db: Session) -> list[HeroSlide]:
    slides = db.query(HeroSlide).order_by(HeroSlide.slot_index.asc()).all()
    existing_slots = {slide.slot_index for slide in slides}
    missing_slots = [slot_index for slot_index in HERO_SLIDE_SLOT_INDEXES if slot_index not in existing_slots]
    if not missing_slots:
        return slides

    for slot_index in missing_slots:
        db.add(HeroSlide(slot_index=slot_index))
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("hero_slide_slots_create_failed missing_slots=%s", missing_slots)
        raise
    logger.info("hero_slide_slots_created missing_slots=%s", missing_slots)
    return db.query(HeroSlide).order_by(HeroSlide.slot_index.asc()).all()


def list_hero_slides(db: Session) -> list[HeroSlideResponse]:
    slides = [_serialize_hero_slide(slide) for slide in ensure_hero_slide_slots(db)]
    logger.info(
        "hero_slide_list count=%s configured_slots=%s",
        len(slides),
        [slide.slot_index for slide in slides if slide.image_url],
    )
    return slides


def upload_hero_slide_image(slot_index: int, image: UploadFile, db: Session) -> HeroSlideResponse:
    logger.info(
        "hero_slide_upload_start slot=%s filename=%s content_type=%s size=%s",
        slot_index,
        image.filename,
        image.content_type,
        getattr(image, "size", None),
    )
    slide = _get_hero_slide(slot_index, db)
    saved = _save_uploaded_image(slot_index, image)
    old_image_path = slide.image_path
    slide.image_path = f"{HERO_SLIDE_URL_PREFIX}/{slot_index}/{saved.filename}"
    slide.updated_at = datetime.now(timezone.utc)
    db.add(slide)
    try:
        db.commit()
        db.refresh(slide)
    except Exception:
        db.rollback()
        _delete_file_path(saved.file_path)
        logger.exception(
            "hero_slide_upload_db_failed slot=%s filename=%s saved_file=%s",
            slot_index,
            image.filename,
            saved.file_path,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="轮播图配置保存失败，请查看服务端日志",
        )
    _delete_slot_file(slot_index, old_image_path)
    logger.info(
        "hero_slide_upload_success slot=%s image_url=%s file_path=%s bytes=%s old_image_path=%s",
        slot_index,
        slide.image_path,
        saved.file_path.resolve(),
        saved.byte_count,
        old_image_path,
    )
    return _serialize_hero_slide(slide)


def clear_hero_slide_image(slot_index: int, db: Session) -> HeroSlideResponse:
    logger.info("hero_slide_clear_start slot=%s", slot_index)
    slide = _get_hero_slide(slot_index, db)
    old_image_path = slide.image_path
    if slide.image_path is not None:
        slide.image_path = None
        slide.updated_at = datetime.now(timezone.utc)
        db.add(slide)
        try:
            db.commit()
            db.refresh(slide)
        except Exception:
            db.rollback()
            logger.exception("hero_slide_clear_db_failed slot=%s old_image_path=%s", slot_index, old_image_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="轮播图配置清空失败，请查看服务端日志",
            )
    _delete_slot_file(slot_index, old_image_path)
    logger.info("hero_slide_clear_success slot=%s old_image_path=%s", slot_index, old_image_path)
    return _serialize_hero_slide(slide)


def _serialize_hero_slide(slide: HeroSlide) -> HeroSlideResponse:
    return HeroSlideResponse(
        slot_index=slide.slot_index,
        image_url=slide.image_path,
        updated_at=slide.updated_at,
    )


def _get_hero_slide(slot_index: int, db: Session) -> HeroSlide:
    _validate_slot_index(slot_index)
    ensure_hero_slide_slots(db)
    slide = db.query(HeroSlide).filter(HeroSlide.slot_index == slot_index).first()
    if slide is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hero slide not found")
    return slide


def _validate_slot_index(slot_index: int) -> None:
    if slot_index not in HERO_SLIDE_SLOT_INDEXES:
        logger.warning("hero_slide_invalid_slot slot=%s", slot_index)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="slot_index must be between 1 and 3")


class SavedHeroSlideImage:
    def __init__(self, filename: str, file_path: Path, byte_count: int) -> None:
        self.filename = filename
        self.file_path = file_path
        self.byte_count = byte_count


def _save_uploaded_image(slot_index: int, image: UploadFile) -> SavedHeroSlideImage:
    if image.filename is None or not image.filename.strip():
        logger.warning("hero_slide_upload_missing_filename slot=%s", slot_index)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image file is required")

    extension = Path(image.filename).suffix.lower()
    if extension not in ALLOWED_HERO_SLIDE_EXTENSIONS:
        logger.warning(
            "hero_slide_upload_invalid_extension slot=%s filename=%s extension=%s",
            slot_index,
            image.filename,
            extension,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only jpg, jpeg, png, webp images are supported",
        )

    if image.content_type and not image.content_type.startswith("image/"):
        logger.warning(
            "hero_slide_upload_invalid_content_type slot=%s filename=%s content_type=%s",
            slot_index,
            image.filename,
            image.content_type,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file must be an image")

    slot_dir = HERO_SLIDE_UPLOAD_DIR / str(slot_index)
    filename = f"{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}{extension}"
    file_path = slot_dir / filename
    try:
        slot_dir.mkdir(parents=True, exist_ok=True)
        content = image.file.read()
    except OSError:
        logger.exception("hero_slide_upload_read_or_mkdir_failed slot=%s upload_dir=%s", slot_index, slot_dir.resolve())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="轮播图文件读取失败，请查看服务端日志",
        )

    if not content:
        logger.warning("hero_slide_upload_empty_file slot=%s filename=%s", slot_index, image.filename)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded image is empty")
    try:
        file_path.write_bytes(content)
    except OSError:
        logger.exception("hero_slide_upload_write_failed slot=%s file_path=%s", slot_index, file_path.resolve())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="轮播图文件保存失败，请查看服务端日志",
        )
    logger.info(
        "hero_slide_file_saved slot=%s filename=%s file_path=%s bytes=%s",
        slot_index,
        image.filename,
        file_path.resolve(),
        len(content),
    )
    return SavedHeroSlideImage(filename=filename, file_path=file_path, byte_count=len(content))


def _delete_file_path(file_path: Path) -> None:
    try:
        file_path.unlink()
        logger.info("hero_slide_file_deleted file_path=%s", file_path.resolve())
    except FileNotFoundError:
        logger.warning("hero_slide_file_delete_missing file_path=%s", file_path.resolve())
    except OSError:
        logger.warning("hero_slide_file_delete_failed file_path=%s", file_path.resolve(), exc_info=True)


def _delete_slot_file(slot_index: int, image_path: str | None) -> None:
    if not image_path:
        return

    file_path = HERO_SLIDE_UPLOAD_DIR / str(slot_index) / Path(image_path).name
    _delete_file_path(file_path)

    parent_dir = file_path.parent
    try:
        if parent_dir.exists() and not any(parent_dir.iterdir()):
            parent_dir.rmdir()
            logger.info("hero_slide_empty_slot_dir_removed slot=%s directory=%s", slot_index, parent_dir.resolve())
    except OSError:
        logger.warning("hero_slide_slot_dir_cleanup_failed slot=%s directory=%s", slot_index, parent_dir.resolve(), exc_info=True)
