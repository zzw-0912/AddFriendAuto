from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.order import Order
from app.models.plan import Plan


def process_wechat_payment(order_no: str, db: Session) -> dict:
    """Process WeChat payment notification (mock for dev)."""
    return _process_payment(order_no, "wechat", db)


def process_alipay_payment(order_no: str, db: Session) -> dict:
    """Process Alipay payment notification (mock for dev)."""
    return _process_payment(order_no, "alipay", db)


def _process_payment(order_no: str, channel: str, db: Session) -> dict:
    order = db.query(Order).filter(Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.status == "paid":
        return {"message": "Already processed", "order_no": order_no}

    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order status is {order.status}")

    # Mark order as paid
    order.status = "paid"
    order.paid_at = datetime.now(timezone.utc)

    # Activate / extend membership
    plan = db.query(Plan).filter(Plan.id == order.plan_id).first()
    if plan:
        existing = (
            db.query(Membership)
            .filter(
                Membership.user_id == order.user_id,
                Membership.status == "active",
            )
            .first()
        )

        now = datetime.now(timezone.utc)
        if existing and existing.ends_at > now:
            starts_at = existing.ends_at
        else:
            starts_at = now
            # Deactivate old ones
            db.query(Membership).filter(
                Membership.user_id == order.user_id,
                Membership.status == "active",
            ).update({"status": "expired"})

        ends_at = starts_at + timedelta(days=plan.duration_days)
        membership = Membership(
            user_id=order.user_id,
            plan_id=order.plan_id,
            starts_at=starts_at,
            ends_at=ends_at,
            status="active",
        )
        db.add(membership)

    db.commit()
    return {"message": "Payment processed", "order_no": order_no}
