import sys
import unittest
from pathlib import Path


SERVER_ROOT = Path(__file__).resolve().parents[1]
if str(SERVER_ROOT) not in sys.path:
    sys.path.insert(0, str(SERVER_ROOT))

from app.services.task_service import (
    allowed_slot_count,
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


if __name__ == "__main__":
    unittest.main()
