import sys
import unittest
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.services.task_service import member_claim_limit, trial_claim_limit


class TaskClaimLimitTest(unittest.TestCase):
    def test_member_claim_limit_uses_requested_daily_limit(self):
        self.assertEqual(member_claim_limit(2), 2)

    def test_trial_claim_limit_caps_to_remaining_quota(self):
        self.assertEqual(trial_claim_limit(2, 1), 1)
        self.assertEqual(trial_claim_limit(4, 2), 2)


if __name__ == "__main__":
    unittest.main()
