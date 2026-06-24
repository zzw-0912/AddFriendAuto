from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: int
    name: str
    duration_days: int
    price_cents: int
    price_yuan: float
