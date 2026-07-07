import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.models.device import Device  # noqa: F401
from app.models.membership import Membership
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.task_target import TaskTarget
from app.models.trial_quota import TrialQuota  # noqa: F401
from app.models.user import User
from app.services.task_service import (
    MEMBER_LIMIT_REACHED_REASON,
    claim_targets,
    start_check,
)


class TaskServiceMemberMonthlyLimitTest(unittest.TestCase):
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

    def add_user(self, email: str = "member@qq.com") -> User:
        user = User(email=email, password_hash="hashed", referral_code=email[:6].upper())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def add_active_membership(self, user_id: int, plan_id: int = 1) -> Membership:
        membership = Membership(
            user_id=user_id,
            plan_id=plan_id,
            starts_at=datetime.now(timezone.utc) - timedelta(days=1),
            ends_at=datetime.now(timezone.utc) + timedelta(days=29),
            status="active",
        )
        self.db.add(membership)
        self.db.commit()
        self.db.refresh(membership)
        return membership

    def add_success_results(self, user_id: int, count: int, slot_id: int = 1):
        task = Task(
            user_id=user_id,
            device_id=0,
            slot_id=slot_id,
            target_type="contact",
            daily_limit=20,
            status="finished",
            started_at=datetime.now(timezone.utc) - timedelta(hours=1),
            finished_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )
        self.db.add(task)
        self.db.flush()
        self.db.add_all(
            [
                TaskResult(
                    task_id=task.id,
                    target_id=index + 1,
                    target_type="contact",
                    result="success",
                    message="ok",
                    trial_charged=False,
                    created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
                )
                for index in range(count)
            ]
        )
        self.db.commit()

    def add_pending_targets(self, user_id: int, count: int):
        self.db.add_all(
            [
                TaskTarget(
                    user_id=user_id,
                    target_type="contact",
                    target_value=f"target-{index}",
                    name=f"Target {index}",
                    status="pending",
                )
                for index in range(count)
            ]
        )
        self.db.commit()

    def test_start_check_blocks_when_member_monthly_quota_is_exhausted(self):
        user = self.add_user()
        self.add_active_membership(user.id, plan_id=1)
        self.add_success_results(user.id, 700)

        result = start_check(user, 1, "contact", 20, False, None, self.db)

        self.assertFalse(result.can_start)
        self.assertEqual(result.reason, MEMBER_LIMIT_REACHED_REASON)

    def test_claim_targets_caps_to_remaining_member_monthly_quota(self):
        user = self.add_user()
        self.add_active_membership(user.id, plan_id=1)
        self.add_success_results(user.id, 698)
        self.add_pending_targets(user.id, 10)

        start_result = start_check(user, 1, "contact", 10, False, None, self.db)
        self.assertTrue(start_result.can_start)

        claim_result = claim_targets(start_result.task_id, user, self.db)

        self.assertEqual(claim_result.count, 2)
        self.assertEqual(len(claim_result.targets), 2)

    def test_claim_targets_respects_other_window_reserved_quota(self):
        user = self.add_user("member2@qq.com")
        self.add_active_membership(user.id, plan_id=2)
        self.add_success_results(user.id, 1398, slot_id=2)

        other_task = Task(
            user_id=user.id,
            device_id=0,
            slot_id=2,
            target_type="contact",
            daily_limit=5,
            status="running",
        )
        self.db.add(other_task)
        self.db.flush()
        self.db.add(
            TaskTarget(
                user_id=user.id,
                target_type="contact",
                target_value="reserved-target",
                name="Reserved Target",
                status="claimed",
                claimed_task_id=other_task.id,
                claimed_at=datetime.now(timezone.utc),
            )
        )
        self.db.commit()

        self.add_pending_targets(user.id, 5)

        start_result = start_check(user, 1, "contact", 5, False, None, self.db)
        self.assertTrue(start_result.can_start)

        claim_result = claim_targets(start_result.task_id, user, self.db)

        self.assertEqual(claim_result.count, 1)
        self.assertEqual(len(claim_result.targets), 1)


if __name__ == "__main__":
    unittest.main()
