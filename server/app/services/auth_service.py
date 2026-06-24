import random
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_access_token, decode_access_token, hash_code, verify_code
from app.models.email_code import EmailCode
from app.models.user import User


def send_code(email: str, db: Session) -> dict:
    code = str(random.randint(100000, 999999))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

    email_code = EmailCode(
        email=email,
        code_hash=hash_code(code),
        expires_at=expires_at,
    )
    db.add(email_code)
    db.commit()

    print(f"[EMAIL] Code for {email}: {code}")

    from app.core.config import settings
    result = {"message": "Code sent", "email": email}
    if settings.debug:
        result["dev_code"] = code
    if settings.debug and email == "test@friendauto.com":
        result["dev_code"] = "888888"
    return result


def login(email: str, code: str, machine_code: str, db: Session) -> dict:
    # Verify code
    valid = False

    # Dev mode: fixed test code for test@friendauto.com
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

    # Find or create user
    user = db.query(User).filter(User.email == email).first()
    is_new = False
    if not user:
        user = User(email=email)
        db.add(user)
        db.flush()
        is_new = True

    user.last_login_at = datetime.now(timezone.utc)

    # Check device binding (skip for test account in dev mode)
    is_test_account = settings.debug and email == "test@friendauto.com"
    if not is_test_account:
        from app.models.device import Device
        device = db.query(Device).filter(Device.machine_code_hash == hash_code(machine_code)).first()

        if device:
            if device.user_id != user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Device already bound to another account. Contact admin to unbind.",
                )
            device.last_seen_at = datetime.now(timezone.utc)
        else:
            existing = db.query(Device).filter(Device.user_id == user.id).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account already bound to another device. Contact admin to unbind.",
                )
            device = Device(
                user_id=user.id,
                machine_code_hash=hash_code(machine_code),
            )
            db.add(device)

    db.commit()

    access_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "is_new_user": is_new,
    }


def refresh(token: str, db: Session) -> dict:
    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == payload.get("sub")).first()
    if not user or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")

    new_token = create_access_token({"sub": str(user.id), "email": user.email})

    return {"access_token": new_token, "token_type": "bearer"}
