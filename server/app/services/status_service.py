from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.membership import Membership
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.schemas.status import MembershipInfo, TrialInfo, UserStatusResponse


def get_user_status(user: User, db: Session) -> UserStatusResponse:
    # Membership
    membership_info = MembershipInfo()
    active_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.status == "active",
            Membership.ends_at > datetime.now(timezone.utc),
        )
        .first()
    )
    if active_membership:
        membership_info = MembershipInfo(
            is_active=True,
            plan_id=active_membership.plan_id,
            starts_at=active_membership.starts_at,
            ends_at=active_membership.ends_at,
        )

    # Trial quota
    quota = db.query(TrialQuota).filter(TrialQuota.user_id == user.id).first()
    trial_info = TrialInfo()
    if quota:
        trial_info = TrialInfo(
            total=quota.total_count,
            used=quota.used_count,
            remaining=quota.remaining_count,
        )

    return UserStatusResponse(
        user_id=user.id,
        email=user.email,
        membership=membership_info,
        trial=trial_info,
    )
