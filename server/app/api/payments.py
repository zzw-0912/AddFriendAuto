from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.payment_service import process_alipay_payment, process_wechat_payment

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentNotifyRequest:
    """Simplified: in production, parse the actual payment gateway notification."""
    pass


@router.post("/wechat/callback")
def wechat_callback(order_no: str, db: Session = Depends(get_db)):
    return process_wechat_payment(order_no, db)


@router.post("/alipay/callback")
def alipay_callback(order_no: str, db: Session = Depends(get_db)):
    return process_alipay_payment(order_no, db)
