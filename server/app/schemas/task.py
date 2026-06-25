from datetime import datetime

from pydantic import BaseModel

from app.schemas.status import MembershipInfo, TrialInfo


class StartCheckRequest(BaseModel):
    daily_limit: int = 20
    create_tag: bool = False
    greeting_text: str | None = None


class StartCheckResponse(BaseModel):
    can_start: bool
    reason: str | None = None
    task_id: int | None = None
    membership: MembershipInfo
    trial: TrialInfo


class ResultRequest(BaseModel):
    contact_id: int
    event: str
    message: str = ""


class TaskResponse(BaseModel):
    id: int
    user_id: int
    device_id: int
    daily_limit: int
    create_tag: bool
    greeting_text: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
