from datetime import datetime

from pydantic import BaseModel


class ProfileResponse(BaseModel):
    user_id: int
    email: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None
    membership: dict
    trial: dict
    success_count: int = 0
    failed_count: int = 0
    invalid_count: int = 0
    referral_code: str | None = None

    model_config = {"from_attributes": True}
