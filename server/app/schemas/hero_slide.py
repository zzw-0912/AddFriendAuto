from datetime import datetime

from pydantic import BaseModel


class HeroSlideResponse(BaseModel):
    slot_index: int
    image_url: str | None = None
    updated_at: datetime | None = None
