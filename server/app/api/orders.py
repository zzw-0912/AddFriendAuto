from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.order import CreateOrderRequest, OrderResponse
from app.services.order_service import create_order, get_order

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse)
def new_order(req: CreateOrderRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = create_order(user, req.plan_id, req.payment_channel, db)
    return order


@router.get("/{order_id}", response_model=OrderResponse)
def order_detail(order_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return get_order(order_id, user, db)
