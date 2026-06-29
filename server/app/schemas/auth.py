from pydantic import BaseModel, EmailStr, Field


CODE_PATTERN = r"^\d{6}$"


class SendCodeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)
    machine_code: str = Field(min_length=1, max_length=255)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    code: str = Field(pattern=CODE_PATTERN)
    machine_code: str = Field(min_length=1, max_length=255)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=CODE_PATTERN)
    new_password: str = Field(min_length=6, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


class AuthStatusResponse(BaseModel):
    id: int
    email: str
    status: str
