from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_code
from app.models.device import Device
from app.models.user import User


def bind_device(user: User, machine_code: str, db: Session) -> Device:
    db.query(User).filter(User.id == user.id).with_for_update().first()
    machine_hash = hash_code(machine_code)

    existing = db.query(Device).filter(
        Device.user_id == user.id,
        Device.machine_code_hash == machine_hash,
    ).first()
    if existing:
        existing.last_seen_at = datetime.now(timezone.utc)
        db.commit()
        return existing

    user_device = db.query(Device).filter(Device.user_id == user.id).first()
    if user_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account already bound to another device",
        )

    device = Device(user_id=user.id, machine_code_hash=machine_hash)
    db.add(device)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account device binding conflict. Please retry.",
        ) from exc
    db.refresh(device)
    return device


def get_current_device(user: User, db: Session) -> Device | None:
    return db.query(Device).filter(Device.user_id == user.id).first()
