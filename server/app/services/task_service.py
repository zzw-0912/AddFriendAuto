from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.membership import Membership
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.schemas.status import MembershipInfo, TrialInfo
from app.schemas.task import StartCheckResponse, TaskResponse


def allowed_slot_count(plan_id: int | None, has_membership: bool) -> int:
    if not has_membership:
        return 1
    if plan_id == 2:
        return 2
    if plan_id == 3:
        return 3
    return 1


def start_check(
    user: User,
    slot_id: int,
    daily_limit: int,
    create_tag: bool,
    greeting_text: str | None,
    db: Session,
) -> StartCheckResponse:
    device = db.query(Device).filter(Device.user_id == user.id, Device.status == "active").first()
    device_id = device.id if device else 0

    membership_info = MembershipInfo()
    active_membership = (
        db.query(Membership)
        .filter(
            Membership.user_id == user.id,
            Membership.status == "active",
            Membership.ends_at > datetime.utcnow(),
        )
        .order_by(Membership.ends_at.desc())
        .first()
    )
    if active_membership:
        membership_info = MembershipInfo(
            is_active=True,
            plan_id=active_membership.plan_id,
            starts_at=active_membership.starts_at,
            ends_at=active_membership.ends_at,
        )

    quota = db.query(TrialQuota).filter(TrialQuota.user_id == user.id).first()
    trial_info = TrialInfo()
    if quota:
        trial_info = TrialInfo(
            total=quota.total_count,
            used=quota.used_count,
            remaining=quota.remaining_count,
        )

    has_remaining = membership_info.is_active or (trial_info.remaining > 0)
    if not has_remaining:
        return StartCheckResponse(
            can_start=False,
            reason="试用次数已用完，请充值后再使用",
            membership=membership_info,
            trial=trial_info,
        )

    max_slots = allowed_slot_count(active_membership.plan_id if active_membership else None, membership_info.is_active)
    if slot_id > max_slots:
        return StartCheckResponse(
            can_start=False,
            reason=f"当前套餐最多可使用 {max_slots} 个微信任务配置",
            membership=membership_info,
            trial=trial_info,
        )

    running_task = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.slot_id == slot_id, Task.status == "running")
        .first()
    )
    if running_task:
        return StartCheckResponse(
            can_start=False,
            reason=f"微信{slot_id}任务正在运行，请先停止后再启动",
            membership=membership_info,
            trial=trial_info,
        )

    task = Task(
        user_id=user.id,
        device_id=device_id,
        slot_id=slot_id,
        daily_limit=daily_limit,
        create_tag=create_tag,
        greeting_text=greeting_text,
        status="running",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    return StartCheckResponse(
        can_start=True,
        task_id=task.id,
        membership=membership_info,
        trial=trial_info,
    )


def report_result(task_id: int, contact_id: int, event: str, message: str, user: User, db: Session) -> dict:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task is not running")

    existing = (
        db.query(TaskResult)
        .filter(TaskResult.task_id == task_id, TaskResult.contact_id == contact_id)
        .first()
    )
    if existing:
        return {"charged": existing.trial_charged, "duplicate": True}

    charged = False
    if event == "success":
        quota = db.query(TrialQuota).filter(TrialQuota.user_id == user.id).first()
        if quota and quota.remaining_count > 0:
            active_membership = (
                db.query(Membership)
                .filter(
                    Membership.user_id == user.id,
                    Membership.status == "active",
                    Membership.ends_at > datetime.utcnow(),
                )
                .order_by(Membership.ends_at.desc())
                .first()
            )
            if not active_membership:
                quota.used_count += 1
                quota.remaining_count -= 1
                charged = True

    result = TaskResult(
        task_id=task_id,
        contact_id=contact_id,
        result=event,
        message=message,
        trial_charged=charged,
    )
    db.add(result)
    db.commit()

    return {"charged": charged, "duplicate": False}


def finish_task(task_id: int, user: User, db: Session) -> TaskResponse:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "finished"
    task.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        device_id=task.device_id,
        slot_id=task.slot_id,
        daily_limit=task.daily_limit,
        create_tag=task.create_tag,
        greeting_text=task.greeting_text,
        status=task.status,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
