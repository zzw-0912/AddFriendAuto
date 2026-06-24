from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, SendCodeRequest, TokenResponse
from app.services.auth_service import login, refresh, send_code

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-code")
def send_verification_code(req: SendCodeRequest, db: Session = Depends(get_db)):
    return send_code(req.email, db)


@router.post("/login", response_model=TokenResponse)
def login_or_register(req: LoginRequest, db: Session = Depends(get_db)):
    return login(req.email, req.code, req.machine_code, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    return refresh(req.refresh_token, db)
