from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.status import MembershipInfo, TrialInfo


class StartCheckRequest(BaseModel):
    slot_id: int = Field(default=1, ge=1, le=3)
    daily_limit: int = Field(default=20, ge=1, le=200)
    create_tag: bool = False
    greeting_text: str | None = Field(default=None, max_length=500)


class StartCheckResponse(BaseModel):
    can_start: bool
    reason: str | None = None
    task_id: int | None = None
    membership: MembershipInfo
    trial: TrialInfo


class ResultRequest(BaseModel):
    contact_id: int = Field(ge=1)
    event: Literal["success", "failed", "invalid", "error"]
    message: str = Field(default="", max_length=1000)


class TaskResponse(BaseModel):
    id: int
    user_id: int
    device_id: int
    slot_id: int
    daily_limit: int
    create_tag: bool
    greeting_text: str | None
    status: str
    started_at: datetime
    finished_at: datetime | None
