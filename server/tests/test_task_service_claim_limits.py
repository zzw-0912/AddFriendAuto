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
    allowed_slot_count,
    claim_targets,
    member_claim_limit,
    member_monthly_success_limit,
    trial_claim_limit,
)


class TaskClaimLimitTest(unittest.TestCase):
    def test_member_claim_limit_uses_requested_daily_limit(self):
        self.assertEqual(member_claim_limit(2), 2)
        self.assertEqual(member_claim_limit(5, 3), 3)

    def test_trial_claim_limit_caps_to_remaining_quota(self):
        self.assertEqual(trial_claim_limit(2, 1), 1)
        self.assertEqual(trial_claim_limit(4, 2), 2)

    def test_hidden_top_tier_is_capped_to_two_slots(self):
        self.assertEqual(allowed_slot_count(3, True), 2)

    def test_member_monthly_success_limit_matches_slot_count(self):
        self.assertEqual(member_monthly_success_limit(1), 700)
        self.assertEqual(member_monthly_success_limit(2), 1400)
        self.assertEqual(member_monthly_success_limit(3), 1400)


class TaskClaimReplenishTest(unittest.TestCase):
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

    def add_user(self, email: str) -> User:
        user = User(email=email, password_hash="hashed", referral_code=email[:6].upper())
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def add_membership(self, user_id: int, plan_id: int = 1) -> Membership:
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

    def add_task(self, user_id: int, daily_limit: int, *, status: str = "running") -> Task:
        task = Task(
            user_id=user_id,
            device_id=0,
            slot_id=1,
            target_type="contact",
            daily_limit=daily_limit,
            status=status,
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def add_results(self, task_id: int, count: int, result: str, *, start_at: int = 0) -> None:
        self.db.add_all(
            [
                TaskResult(
                    task_id=task_id,
                    target_id=start_at + index + 1,
                    target_type="contact",
                    result=result,
                    message=result,
                    trial_charged=(result == "success"),
                )
                for index in range(count)
            ]
        )
        self.db.commit()

    def add_targets(self, user_id: int, count: int) -> None:
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

    def test_member_claim_targets_uses_remaining_success_goal(self):
        user = self.add_user("member-claim@qq.com")
        self.add_membership(user.id)
        task = self.add_task(user.id, 20)
        self.add_results(task.id, 11, "success")
        self.add_targets(user.id, 30)

        claim = claim_targets(task.id, user, self.db)

        self.assertEqual(claim.count, 9)
        self.assertEqual(len(claim.targets), 9)

    def test_trial_claim_targets_uses_remaining_success_goal(self):
        user = self.add_user("trial-claim@qq.com")
        quota = TrialQuota(user_id=user.id, device_id=0, total_count=20, used_count=1, remaining_count=1)
        self.db.add(quota)
        self.db.commit()
        task = self.add_task(user.id, 2)
        self.add_results(task.id, 1, "success")
        self.add_targets(user.id, 5)

        claim = claim_targets(task.id, user, self.db)

        self.assertEqual(claim.count, 1)
        self.assertEqual(len(claim.targets), 1)

    def test_failed_and_invalid_results_do_not_reduce_next_claim_goal(self):
        user = self.add_user("retry-goal@qq.com")
        self.add_membership(user.id)
        task = self.add_task(user.id, 20)
        self.add_results(task.id, 9, "invalid")
        self.add_results(task.id, 11, "failed", start_at=9)
        self.add_targets(user.id, 25)

        claim = claim_targets(task.id, user, self.db)

        self.assertEqual(claim.count, 20)
        self.assertEqual(len(claim.targets), 20)

    def test_claim_targets_stops_when_goal_reached(self):
        user = self.add_user("goal@qq.com")
        self.add_membership(user.id)
        task = self.add_task(user.id, 2)
        self.add_results(task.id, 2, "success")

        claim = claim_targets(task.id, user, self.db)
        self.db.refresh(task)

        self.assertFalse(claim.can_claim)
        self.assertEqual(claim.reason_code, "goal_reached")
        self.assertEqual(task.status, "finished")

    def test_claim_targets_reports_exhausted_pool_when_no_pending_targets(self):
        user = self.add_user("empty-pool@qq.com")
        self.add_membership(user.id)
        task = self.add_task(user.id, 5)

        claim = claim_targets(task.id, user, self.db)
        self.db.refresh(task)

        self.assertFalse(claim.can_claim)
        self.assertEqual(claim.reason_code, "targets_exhausted")
        self.assertEqual(task.status, "finished")


if __name__ == "__main__":
    unittest.main()
