import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.core.security import hash_code
from app.models.device import Device  # noqa: F401
from app.models.email_code import EmailCode
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.services.auth_service import register


class AuthReferralBonusTest(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.db = self.Session()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def add_email_code(self, email: str, code: str = "123456"):
        self.db.add(
            EmailCode(
                email=email,
                code_hash=hash_code(code),
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            )
        )
        self.db.commit()

    def add_referrer(self, referral_code: str = "ABC123") -> int:
        referrer = User(
            email="referrer@qq.com",
            password_hash="hashed",
            referral_code=referral_code,
        )
        self.db.add(referrer)
        self.db.flush()
        self.db.add(
            TrialQuota(
                user_id=referrer.id,
                device_id=0,
                total_count=20,
                used_count=3,
                remaining_count=17,
            )
        )
        self.db.commit()
        return referrer.id

    def quota_for(self, user_id: int) -> TrialQuota:
        return self.db.query(TrialQuota).filter(TrialQuota.user_id == user_id).one()

    def test_valid_referral_adds_bonus_to_referrer_only(self):
        referrer_id = self.add_referrer()
        self.add_email_code("new@qq.com")

        result = register(
            "new@qq.com",
            "password123",
            "123456",
            "machine-new",
            self.db,
            " abc123 ",
        )

        self.assertTrue(result["access_token"])
        referrer_quota = self.quota_for(referrer_id)
        self.assertEqual(referrer_quota.total_count, 40)
        self.assertEqual(referrer_quota.used_count, 3)
        self.assertEqual(referrer_quota.remaining_count, 37)

        new_user = self.db.query(User).filter(User.email == "new@qq.com").one()
        new_quota = self.quota_for(new_user.id)
        self.assertEqual(new_quota.total_count, 20)
        self.assertEqual(new_quota.remaining_count, 20)

    def test_empty_referral_does_not_change_referrer_quota(self):
        referrer_id = self.add_referrer()
        self.add_email_code("plain@qq.com")

        register("plain@qq.com", "password123", "123456", "machine-plain", self.db)

        referrer_quota = self.quota_for(referrer_id)
        self.assertEqual(referrer_quota.total_count, 20)
        self.assertEqual(referrer_quota.remaining_count, 17)

    def test_missing_referral_blocks_registration_and_bonus(self):
        referrer_id = self.add_referrer()
        self.add_email_code("bad@qq.com")

        with self.assertRaises(HTTPException) as raised:
            register(
                "bad@qq.com",
                "password123",
                "123456",
                "machine-bad",
                self.db,
                "MISSING",
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.assertEqual(raised.exception.detail, "邀请码不存在，请检查后重试")
        self.db.rollback()
        self.assertIsNone(self.db.query(User).filter(User.email == "bad@qq.com").first())
        referrer_quota = self.quota_for(referrer_id)
        self.assertEqual(referrer_quota.total_count, 20)
        self.assertEqual(referrer_quota.remaining_count, 17)

    def test_duplicate_email_does_not_add_referral_bonus(self):
        referrer_id = self.add_referrer()
        existing = User(
            email="existing@qq.com",
            password_hash="hashed",
            referral_code="EXIST1",
        )
        self.db.add(existing)
        self.db.commit()
        self.add_email_code("existing@qq.com")

        with self.assertRaises(HTTPException) as raised:
            register(
                "existing@qq.com",
                "password123",
                "123456",
                "machine-existing",
                self.db,
                "ABC123",
            )

        self.assertEqual(raised.exception.status_code, 400)
        self.db.rollback()
        referrer_quota = self.quota_for(referrer_id)
        self.assertEqual(referrer_quota.total_count, 20)
        self.assertEqual(referrer_quota.remaining_count, 17)


if __name__ == "__main__":
    unittest.main()
