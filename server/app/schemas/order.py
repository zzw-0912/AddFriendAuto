from datetime import datetime

from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    plan_id: int
    payment_channel: str = "wechat"


class OrderResponse(BaseModel):
    id: int
    order_no: str
    plan_id: int
    amount_cents: int
    payment_channel: str | None
    status: str
    paid_at: datetime | None
    created_at: datetime
