from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class CreateOrderRequest(BaseModel):
    plan_id: int = Field(ge=1)
    payment_channel: Literal["manual_wechat", "wechat", "alipay"] = "manual_wechat"


class OrderResponse(BaseModel):
    id: int
    order_no: str
    plan_id: int
    amount_cents: int
    payment_channel: str | None
    status: str
    paid_at: datetime | None
    created_at: datetime
