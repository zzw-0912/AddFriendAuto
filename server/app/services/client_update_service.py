import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.models.client_update import ClientUpdateConfig
from app.schemas.client_update import ClientUpdateConfigRequest, ClientUpdateConfigResponse


CLIENT_UPDATE_CONFIG_ID = 1
CLIENT_UPDATE_UPLOAD_DIR = Path(os.getenv("UPLOADS_DIR", "uploads")) / "client-update"
CLIENT_UPDATE_QR_URL_PREFIX = "/uploads/client-update"
ALLOWED_QR_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_UPDATE_MESSAGE = "当前软件版本已停用，请下载最新版本后继续使用。"

logger = logging.getLogger("friendauto.client_update")


def ensure_client_update_config(db: Session) -> ClientUpdateConfig:
    config = db.query(ClientUpdateConfig).filter(ClientUpdateConfig.id == CLIENT_UPDATE_CONFIG_ID).first()
    if config:
        return config

    config = ClientUpdateConfig(
        id=CLIENT_UPDATE_CONFIG_ID,
        latest_version="0.1.0",
        force_update_enabled=False,
        message=DEFAULT_UPDATE_MESSAGE,
    )
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("client_update_config_create_failed")
        raise
    logger.info("client_update_config_created id=%s latest_version=%s", config.id, config.latest_version)
    return config


def get_client_update_config(db: Session) -> ClientUpdateConfigResponse:
    return serialize_client_update_config(ensure_client_update_config(db))


def update_client_update_config(req: ClientUpdateConfigRequest, db: Session) -> ClientUpdateConfigResponse:
    config = ensure_client_update_config(db)
    if req.latest_version is not None:
        latest_version = req.latest_version.strip()
        if not latest_version:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最新版本号不能为空")
        config.latest_version = latest_version
    if req.download_url is not None:
        config.download_url = req.download_url.strip() or None
    if req.message is not None:
        config.message = req.message.strip() or None
    if req.force_update_enabled is not None:
        config.force_update_enabled = req.force_update_enabled
    config.updated_at = datetime.now(timezone.utc)
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("client_update_config_update_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="客户端版本配置保存失败，请查看服务端日志",
        )
    logger.info(
        "client_update_config_updated latest_version=%s force=%s download_url=%s",
        config.latest_version,
        config.force_update_enabled,
        config.download_url,
    )
    return serialize_client_update_config(config)


def set_client_force_update(enabled: bool, db: Session) -> ClientUpdateConfigResponse:
    config = ensure_client_update_config(db)
    config.force_update_enabled = enabled
    config.updated_at = datetime.now(timezone.utc)
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("client_update_force_toggle_failed enabled=%s", enabled)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="强制更新状态保存失败，请查看服务端日志",
        )
    logger.info("client_update_force_toggled enabled=%s latest_version=%s", enabled, config.latest_version)
    return serialize_client_update_config(config)


def upload_client_update_qr_image(image: UploadFile, db: Session) -> ClientUpdateConfigResponse:
    config = ensure_client_update_config(db)
    saved = _save_qr_image(image)
    old_path = config.qr_image_path
    config.qr_image_path = f"{CLIENT_UPDATE_QR_URL_PREFIX}/{saved.filename}"
    config.updated_at = datetime.now(timezone.utc)
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        _delete_file_path(saved.file_path)
        logger.exception("client_update_qr_db_failed filename=%s saved_file=%s", image.filename, saved.file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新二维码保存失败，请查看服务端日志",
        )
    _delete_qr_file(old_path)
    logger.info("client_update_qr_uploaded image_url=%s file_path=%s", config.qr_image_path, saved.file_path.resolve())
    return serialize_client_update_config(config)


def clear_client_update_qr_image(db: Session) -> ClientUpdateConfigResponse:
    config = ensure_client_update_config(db)
    old_path = config.qr_image_path
    config.qr_image_path = None
    config.updated_at = datetime.now(timezone.utc)
    db.add(config)
    try:
        db.commit()
        db.refresh(config)
    except Exception:
        db.rollback()
        logger.exception("client_update_qr_clear_failed old_path=%s", old_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新二维码清空失败，请查看服务端日志",
        )
    _delete_qr_file(old_path)
    logger.info("client_update_qr_cleared old_path=%s", old_path)
    return serialize_client_update_config(config)


def serialize_client_update_config(config: ClientUpdateConfig) -> ClientUpdateConfigResponse:
    return ClientUpdateConfigResponse(
        latest_version=config.latest_version,
        force_update_enabled=config.force_update_enabled,
        download_url=config.download_url,
        qr_image_url=config.qr_image_path,
        message=config.message or DEFAULT_UPDATE_MESSAGE,
        updated_at=config.updated_at,
    )


def is_client_update_required(config: ClientUpdateConfig, client_version: str | None) -> bool:
    if not config.force_update_enabled:
        return False
    return (client_version or "").strip() != (config.latest_version or "").strip()


def build_upgrade_required_payload(config: ClientUpdateConfig) -> dict:
    data = serialize_client_update_config(config).model_dump()
    return {
        "code": "CLIENT_UPDATE_REQUIRED",
        "detail": data["message"],
        **data,
    }


class SavedClientUpdateImage:
    def __init__(self, filename: str, file_path: Path) -> None:
        self.filename = filename
        self.file_path = file_path


def _save_qr_image(image: UploadFile) -> SavedClientUpdateImage:
    if image.filename is None or not image.filename.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请上传微信扫码图片")

    extension = Path(image.filename).suffix.lower()
    if extension not in ALLOWED_QR_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持 jpg、jpeg、png、webp 图片",
        )
    if image.content_type and not image.content_type.startswith("image/"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件必须是图片")

    CLIENT_UPDATE_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"qr_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:12]}{extension}"
    file_path = CLIENT_UPDATE_UPLOAD_DIR / filename
    content = image.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传图片不能为空")
    try:
        file_path.write_bytes(content)
    except OSError:
        logger.exception("client_update_qr_write_failed file_path=%s", file_path.resolve())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="更新二维码文件保存失败，请查看服务端日志",
        )
    return SavedClientUpdateImage(filename=filename, file_path=file_path)


def _delete_qr_file(image_path: str | None) -> None:
    if not image_path:
        return
    _delete_file_path(CLIENT_UPDATE_UPLOAD_DIR / Path(image_path).name)


def _delete_file_path(file_path: Path) -> None:
    try:
        file_path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        logger.warning("client_update_file_delete_failed file_path=%s", file_path.resolve(), exc_info=True)
