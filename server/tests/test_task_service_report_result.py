import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.models.device import Device  # noqa: F401
from app.models.membership import Membership  # noqa: F401
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.task_target import TaskTarget
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.services.task_service import finish_task, report_result


class TaskServiceReportResultTest(unittest.TestCase):
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

    def add_running_task_with_target(self):
        user = User(email="trial@qq.com", password_hash="hashed", referral_code="TRIAL1")
        self.db.add(user)
        self.db.flush()
        quota = TrialQuota(user_id=user.id, device_id=0, total_count=20, used_count=0, remaining_count=2)
        task = Task(
            user_id=user.id,
            device_id=0,
            slot_id=1,
            target_type="phone",
            daily_limit=2,
            status="running",
        )
        self.db.add_all([quota, task])
        self.db.flush()
        target = TaskTarget(
            user_id=user.id,
            target_type="phone",
            target_value="13800138000",
            status="claimed",
            claimed_task_id=task.id,
        )
        self.db.add(target)
        self.db.commit()
        self.db.refresh(user)
        self.db.refresh(task)
        self.db.refresh(target)
        return user, task, target

    def quota_for(self, user_id: int) -> TrialQuota:
        return self.db.query(TrialQuota).filter(TrialQuota.user_id == user_id).one()

    def test_non_member_success_charges_trial_quota_once(self):
        user, task, target = self.add_running_task_with_target()

        first = report_result(task.id, target.id, None, "success", "ok", user, self.db)
        second = report_result(task.id, target.id, None, "success", "ok", user, self.db)

        quota = self.quota_for(user.id)
        self.assertTrue(first["charged"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(quota.used_count, 1)
        self.assertEqual(quota.remaining_count, 1)

    def test_failed_result_does_not_charge_trial_quota(self):
        user, task, target = self.add_running_task_with_target()

        result = report_result(task.id, target.id, None, "failed", "failed", user, self.db)

        quota = self.quota_for(user.id)
        self.assertFalse(result["charged"])
        self.assertEqual(quota.used_count, 0)
        self.assertEqual(quota.remaining_count, 2)

    def test_success_after_finish_release_still_charges_trial_quota(self):
        user, task, target = self.add_running_task_with_target()
        finish_task(task.id, user, self.db)
        self.db.refresh(target)
        self.assertIsNone(target.claimed_task_id)
        self.assertEqual(target.status, "pending")

        result = report_result(task.id, target.id, None, "success", "late ok", user, self.db)

        quota = self.quota_for(user.id)
        self.db.refresh(target)
        self.assertTrue(result["charged"])
        self.assertEqual(quota.used_count, 1)
        self.assertEqual(quota.remaining_count, 1)
        self.assertEqual(target.status, "success")

    def test_success_after_invalid_upgrades_result_and_charges_once(self):
        user, task, target = self.add_running_task_with_target()

        invalid = report_result(task.id, target.id, None, "invalid", "bad", user, self.db)
        success = report_result(task.id, target.id, None, "success", "ok", user, self.db)
        duplicate = report_result(task.id, target.id, None, "success", "ok again", user, self.db)

        quota = self.quota_for(user.id)
        result = self.db.query(TaskResult).filter(TaskResult.task_id == task.id, TaskResult.target_id == target.id).one()
        self.db.refresh(target)
        self.assertFalse(invalid["charged"])
        self.assertTrue(success["charged"])
        self.assertTrue(success["updated"])
        self.assertTrue(duplicate["duplicate"])
        self.assertEqual(quota.used_count, 1)
        self.assertEqual(quota.remaining_count, 1)
        self.assertEqual(result.result, "success")
        self.assertTrue(result.trial_charged)
        self.assertEqual(target.status, "success")

    def test_success_for_claimed_global_target_charges_and_reassigns_target_owner(self):
        user, task, target = self.add_running_task_with_target()
        original_owner = User(email="owner@qq.com", password_hash="hashed", referral_code="OWNER1")
        self.db.add(original_owner)
        self.db.flush()
        target.user_id = original_owner.id
        self.db.commit()

        result = report_result(task.id, target.id, None, "success", "ok", user, self.db)

        quota = self.quota_for(user.id)
        self.db.refresh(target)
        self.assertTrue(result["charged"])
        self.assertEqual(quota.used_count, 1)
        self.assertEqual(quota.remaining_count, 1)
        self.assertEqual(target.user_id, user.id)
        self.assertEqual(target.status, "success")


if __name__ == "__main__":
    unittest.main()
