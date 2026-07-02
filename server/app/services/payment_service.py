from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.order import Order
from app.models.plan import Plan


def process_wechat_payment(order_no: str, db: Session) -> dict:
    """Process WeChat payment notification (mock for dev)."""
    return process_order_payment_by_order_no(order_no, "wechat", db)


def process_alipay_payment(order_no: str, db: Session) -> dict:
    """Process Alipay payment notification (mock for dev)."""
    return process_order_payment_by_order_no(order_no, "alipay", db)


def process_order_payment_by_order_no(order_no: str, channel: str, db: Session) -> dict:
    order = db.query(Order).filter(Order.order_no == order_no).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return process_order_payment(order, channel, db)


def process_order_payment(order: Order, channel: str, db: Session) -> dict:
    """Mark an order paid and activate/extend membership once."""
    locked_order = db.query(Order).filter(Order.id == order.id).with_for_update().first()
    if not locked_order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    order = locked_order

    if order.status == "paid":
        return {
            "success": True,
            "message": "Already processed",
            "order_id": order.id,
            "order_no": order.order_no,
            "status": order.status,
            "paid_at": order.paid_at,
        }

    if order.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Order status is {order.status}")

    plan = db.query(Plan).filter(Plan.id == order.plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order plan not found")

    now = datetime.utcnow()
    order.status = "paid"
    order.paid_at = now
    order.payment_channel = channel

    existing = (
        db.query(Membership)
        .filter(
            Membership.user_id == order.user_id,
            Membership.status == "active",
            Membership.ends_at > now,
        )
        .order_by(Membership.ends_at.desc())
        .first()
    )

    if existing:
        starts_at = existing.ends_at
    else:
        starts_at = now
        db.query(Membership).filter(
            Membership.user_id == order.user_id,
            Membership.status == "active",
        ).update({"status": "expired"}, synchronize_session=False)

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
    db.refresh(order)
    db.refresh(membership)
    return {
        "success": True,
        "message": "Payment processed",
        "order_id": order.id,
        "order_no": order.order_no,
        "status": order.status,
        "paid_at": order.paid_at,
        "membership_id": membership.id,
        "ends_at": membership.ends_at,
    }
