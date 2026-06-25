from pydantic import BaseModel, EmailStr


class SendCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = ""
    machine_code: str


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    code: str
    machine_code: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    new_password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


class AuthStatusResponse(BaseModel):
    id: int
    email: str
    status: str
