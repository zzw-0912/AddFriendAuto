from datetime import datetime

from pydantic import BaseModel


class BindDeviceRequest(BaseModel):
    machine_code: str


class DeviceResponse(BaseModel):
    id: int
    user_id: int
    machine_code_hash: str
    status: str
    bound_at: datetime | None
    last_seen_at: datetime | None
    remark: str | None
