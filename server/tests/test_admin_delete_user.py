import sys
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.core.database import Base
from app.models.admin_audit_log import AdminAuditLog  # noqa: F401
from app.models.device import Device  # noqa: F401
from app.models.email_code import EmailCode  # noqa: F401
from app.models.feedback import Feedback  # noqa: F401
from app.models.membership import Membership  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.task import Task  # noqa: F401
from app.models.task_result import TaskResult  # noqa: F401
from app.models.task_target import TaskTarget
from app.models.trial_quota import TrialQuota  # noqa: F401
from app.models.user import User
from app.services.admin_service import delete_user


class AdminDeleteUserTest(unittest.TestCase):
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

    def test_delete_user_preserves_global_task_targets(self):
        user = User(email="target-owner@qq.com", password_hash="hashed")
        self.db.add(user)
        self.db.flush()
        self.db.add_all(
            [
                TaskTarget(
                    user_id=user.id,
                    target_type="contact",
                    target_value="target-1",
                    status="pending",
                ),
                TaskTarget(
                    user_id=user.id,
                    target_type="contact",
                    target_value="target-2",
                    status="success",
                ),
            ]
        )
        self.db.commit()

        result = delete_user(user.id, admin_user_id=1, db=self.db)

        self.assertTrue(result["success"])
        self.assertEqual(result["deleted_counts"]["task_targets"], 0)
        self.assertIsNone(self.db.query(User).filter(User.id == user.id).first())
        self.assertEqual(self.db.query(TaskTarget).count(), 2)


if __name__ == "__main__":
    unittest.main()
