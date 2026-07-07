from datetime import datetime, timedelta

from sqlalchemy.orm import Query, Session

from app.models.membership import Membership


def utc_now() -> datetime:
    return datetime.utcnow()


def current_membership_query(db: Session, user_id: int, now: datetime | None = None) -> Query:
    now = now or utc_now()
    return db.query(Membership).filter(
        Membership.user_id == user_id,
        Membership.status == "active",
        Membership.starts_at <= now,
        Membership.ends_at > now,
    )


def get_current_membership(db: Session, user_id: int, now: datetime | None = None) -> Membership | None:
    return current_membership_query(db, user_id, now).order_by(Membership.ends_at.desc()).first()


def is_membership_current(membership: Membership | None, now: datetime | None = None) -> bool:
    if not membership:
        return False
    now = now or utc_now()
    starts_at = membership.starts_at
    ends_at = membership.ends_at
    return (
        membership.status == "active"
        and starts_at is not None
        and ends_at is not None
        and starts_at <= now
        and ends_at > now
    )


def expire_active_memberships(db: Session, user_id: int, now: datetime | None = None) -> tuple[int, datetime]:
    now = now or utc_now()
    expire_at = now - timedelta(seconds=1)
    memberships = (
        db.query(Membership)
        .filter(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.ends_at > expire_at,
        )
        .all()
    )
    for membership in memberships:
        membership.status = "expired"
        membership.ends_at = expire_at
        if membership.starts_at > expire_at:
            membership.starts_at = expire_at
    return len(memberships), expire_at
