import json
from datetime import datetime

from pydantic import BaseModel, field_validator


class FeedbackResponse(BaseModel):
    id: int
    user_id: int
    content: str
    images: list[str] | None = None
    created_at: datetime

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = {"from_attributes": True}


class FeedbackListItem(BaseModel):
    id: int
    user_id: int
    email: str | None = None
    content: str
    images: list[str] | None = None
    created_at: datetime

    @field_validator("images", mode="before")
    @classmethod
    def parse_images(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    model_config = {"from_attributes": True}
