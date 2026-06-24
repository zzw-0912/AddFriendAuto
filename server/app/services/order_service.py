import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.order import Order
from app.models.plan import Plan
from app.models.user import User


def create_order(user: User, plan_id: int, payment_channel: str, db: Session) -> Order:
    plan = db.query(Plan).filter(Plan.id == plan_id, Plan.enabled == True).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found or disabled")

    order_no = f"FA{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"

    order = Order(
        order_no=order_no,
        user_id=user.id,
        plan_id=plan.id,
        amount_cents=plan.price_cents,
        payment_channel=payment_channel,
        status="pending",
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


def get_order(order_id: int, user: User, db: Session) -> Order:
    order = db.query(Order).filter(Order.id == order_id, Order.user_id == user.id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    return order
