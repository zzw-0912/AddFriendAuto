import sys
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.models.membership import Membership  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.plan import Plan
from app.models.user import User
from app.services.order_service import create_order
from app.services.payment_service import process_order_payment
from app.services.plan_visibility import public_plan_query


class PlanVisibilityTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()
        self.db.add_all(
            [
                Plan(id=1, name="Plus", duration_days=30, price_cents=30000, enabled=True),
                Plan(id=2, name="Pro 5x", duration_days=30, price_cents=50000, enabled=True),
                Plan(id=3, name="Pro 20x", duration_days=30, price_cents=80000, enabled=True),
            ]
        )
        self.user = User(email="buyer@qq.com", password_hash="hashed", referral_code="BUY001")
        self.db.add(self.user)
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_public_plan_query_hides_800_tier(self):
        plans = public_plan_query(self.db.query(Plan)).order_by(Plan.id).all()

        self.assertEqual([plan.id for plan in plans], [1, 2])

    def test_create_order_rejects_hidden_800_tier(self):
        with self.assertRaises(HTTPException) as raised:
            create_order(self.user, 3, "manual_wechat", self.db)

        self.assertEqual(raised.exception.status_code, 404)

    def test_payment_confirmation_rejects_hidden_800_tier_order(self):
        order = Order(
            order_no="FA-HIDDEN-800",
            user_id=self.user.id,
            plan_id=3,
            amount_cents=80000,
            payment_channel="manual_wechat",
            status="pending",
        )
        self.db.add(order)
        self.db.commit()

        with self.assertRaises(HTTPException) as raised:
            process_order_payment(order, "manual_wechat", self.db)

        self.assertEqual(raised.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
