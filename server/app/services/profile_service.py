from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.user import User
from app.services.status_service import get_user_status


def get_profile(user: User, db: Session) -> dict:
    status_data = get_user_status(user, db)
    sd = status_data.model_dump()

    stats = (
        db.query(TaskResult.result, func.count(TaskResult.id))
        .join(Task, TaskResult.task_id == Task.id)
        .filter(Task.user_id == user.id)
        .group_by(TaskResult.result)
        .all()
    )
    counts = {"success": 0, "failed": 0, "invalid": 0}
    for result, cnt in stats:
        if result in counts:
            counts[result] = cnt

    return {
        "user_id": user.id,
        "email": user.email,
        "status": user.status,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "membership": sd["membership"],
        "trial": sd["trial"],
        "success_count": counts["success"],
        "failed_count": counts["failed"],
        "invalid_count": counts["invalid"],
        "referral_code": user.referral_code,
    }
