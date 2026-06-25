from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    SendCodeRequest,
    TokenResponse,
)
from app.services.auth_service import login, refresh, register, reset_password, send_code

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-code")
async def send_verification_code(req: SendCodeRequest, db: Session = Depends(get_db)):
    return await send_code(req.email, db)


@router.post("/login", response_model=TokenResponse)
def login_or_register(req: LoginRequest, db: Session = Depends(get_db)):
    return login(req.email, req.password, req.machine_code, db)


@router.post("/register", response_model=TokenResponse)
def register_account(req: RegisterRequest, db: Session = Depends(get_db)):
    return register(req.email, req.password, req.code, req.machine_code, db)


@router.post("/reset-password")
def reset_account_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    return reset_password(req.email, req.code, req.new_password, db)


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    return refresh(req.refresh_token, db)
