from datetime import datetime

from pydantic import BaseModel, Field


class ClientUpdateConfigResponse(BaseModel):
    latest_version: str
    force_update_enabled: bool
    download_url: str | None = None
    qr_image_url: str | None = None
    message: str | None = None
    updated_at: datetime | None = None


class ClientUpdateConfigRequest(BaseModel):
    latest_version: str | None = Field(default=None, min_length=1, max_length=50)
    download_url: str | None = Field(default=None, max_length=1000)
    message: str | None = Field(default=None, max_length=2000)
    force_update_enabled: bool | None = None
