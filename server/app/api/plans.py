from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.plan import Plan
from app.schemas.plan import PlanResponse

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("", response_model=list[PlanResponse])
def list_plans(db: Session = Depends(get_db)):
    plans = db.query(Plan).filter(Plan.enabled == True).all()
    return [
        PlanResponse(
            id=p.id,
            name=p.name,
            duration_days=p.duration_days,
            price_cents=p.price_cents,
            price_yuan=round(p.price_cents / 100, 2),
        )
        for p in plans
    ]
