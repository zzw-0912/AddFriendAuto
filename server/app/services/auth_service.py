import asyncio
import random
import string
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_code,
    hash_password,
    verify_code,
    verify_password,
)
from app.models.email_code import EmailCode
from app.models.user import User


async def send_code(email: str, db: Session) -> dict:
    recent = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.created_at > datetime.now(timezone.utc) - timedelta(seconds=60),
        )
        .first()
    )
    if recent:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 60 seconds before requesting a new code",
        )

    code = str(random.randint(100000, 999999))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    email_code = EmailCode(
        email=email,
        code_hash=hash_code(code),
        expires_at=expires_at,
    )
    db.add(email_code)
    db.commit()

    from app.services.email_service import send_verification_email
    asyncio.create_task(send_verification_email(email, code))

    result = {"message": "Code sent", "email": email}
    if settings.debug:
        result["dev_code"] = code
    if settings.debug and email == "test@friendauto.com":
        result["dev_code"] = "888888"
    return result


def _bind_device(user_id: int, machine_code: str, db: Session):
    from app.models.device import Device

    mc_hash = hash_code(machine_code)
    existing = db.query(Device).filter(
        Device.user_id == user_id,
        Device.machine_code_hash == mc_hash,
    ).first()
    if existing:
        existing.last_seen_at = datetime.now(timezone.utc)
        return

    user_device = db.query(Device).filter(Device.user_id == user_id).first()
    if user_device:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account already bound to another device. Contact admin to unbind.",
        )

    device = Device(user_id=user_id, machine_code_hash=mc_hash)
    db.add(device)


def _create_trial_quota(user_id: int, db: Session):
    from app.models.trial_quota import TrialQuota

    existing = db.query(TrialQuota).filter(TrialQuota.user_id == user_id).first()
    if not existing:
        quota = TrialQuota(
            user_id=user_id,
            device_id=0,
            total_count=20,
            used_count=0,
            remaining_count=20,
        )
        db.add(quota)


def _generate_referral_code(db: Session) -> str:
    chars = string.ascii_uppercase + string.digits
    for _ in range(100):
        code = "".join(random.choices(chars, k=6))
        if not db.query(User).filter(User.referral_code == code).first():
            return code
    return hex(random.getrandbits(48))[2:10]


def _issue_token(user_id: int, email: str) -> dict:
    access_token = create_access_token({"sub": str(user_id), "email": email})
    return {"access_token": access_token, "token_type": "bearer"}


def login(email: str, password: str, machine_code: str, db: Session) -> dict:
    # Dev mode: fixed test account with verification code
    if settings.debug and email == "test@friendauto.com" and password == "888888":
        user = db.query(User).filter(User.email == email).first()
        is_new = False
        if not user:
            user = User(email=email, referral_code=_generate_referral_code(db))
            db.add(user)
            db.flush()
            _create_trial_quota(user.id, db)
            is_new = True

        user.last_login_at = datetime.now(timezone.utc)
        db.commit()
        result = _issue_token(user.id, email)
        result["is_new_user"] = is_new
        return result

    user = db.query(User).filter(User.email == email).with_for_update().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account does not exist")

    if not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set. Please use 'Find Account' to set your password.",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    is_test_account = settings.debug and email == "test@friendauto.com"
    if not is_test_account:
        _bind_device(user.id, machine_code, db)

    user.last_login_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Account device binding conflict. Please retry.",
        ) from exc

    result = _issue_token(user.id, email)
    result["is_new_user"] = False
    return result


def register(email: str, password: str, code: str, machine_code: str, db: Session) -> dict:
    # Verify code
    valid = False
    if settings.debug and email == "test@friendauto.com" and code == "888888":
        valid = True

    if not valid:
        codes = (
            db.query(EmailCode)
            .filter(
                EmailCode.email == email,
                EmailCode.used_at.is_(None),
                EmailCode.expires_at > datetime.now(timezone.utc),
            )
            .order_by(EmailCode.created_at.desc())
            .all()
        )
        for c in codes:
            if verify_code(code, c.code_hash):
                c.used_at = datetime.now(timezone.utc)
                valid = True
                break

    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(password), referral_code=_generate_referral_code(db))
    db.add(user)
    db.flush()

    _create_trial_quota(user.id, db)
    _bind_device(user.id, machine_code, db)

    user.last_login_at = datetime.now(timezone.utc)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered or device already bound.",
        ) from exc

    result = _issue_token(user.id, email)
    result["is_new_user"] = True
    return result


def reset_password(email: str, code: str, new_password: str, db: Session) -> dict:
    # Verify code
    valid = False
    codes = (
        db.query(EmailCode)
        .filter(
            EmailCode.email == email,
            EmailCode.used_at.is_(None),
            EmailCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(EmailCode.created_at.desc())
        .all()
    )
    for c in codes:
        if verify_code(code, c.code_hash):
            c.used_at = datetime.now(timezone.utc)
            valid = True
            break

    if not valid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account does not exist")

    user.password_hash = hash_password(new_password)
    db.commit()

    return {"message": "Password reset successfully"}


def refresh(token: str, db: Session) -> dict:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    new_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {"access_token": new_token, "token_type": "bearer"}
