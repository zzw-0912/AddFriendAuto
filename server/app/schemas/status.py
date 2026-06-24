from datetime import datetime

from pydantic import BaseModel


class MembershipInfo(BaseModel):
    is_active: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class TrialInfo(BaseModel):
    total: int = 20
    used: int = 0
    remaining: int = 20


class UserStatusResponse(BaseModel):
    user_id: int
    email: str
    membership: MembershipInfo
    trial: TrialInfo
