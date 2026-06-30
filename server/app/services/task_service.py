import math
import random
import re
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.membership import Membership
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.task_target import TaskTarget
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.schemas.status import MembershipInfo, TrialInfo
from app.schemas.task import ClaimTargetsResponse, StartCheckResponse, TaskResponse, TaskTargetItem


STALE_RUNNING_TASK_HOURS = 12
VALID_TARGET_TYPES = {"contact", "phone", "wechat_id"}


def random_claim_limit(daily_limit: int | None) -> int:
    max_limit = max(1, int(daily_limit or 1))
    if max_limit <= 3:
        return random.randint(1, max_limit)
    min_limit = math.ceil(max_limit * 0.7)
    return random.randint(min_limit, max_limit)


def random_order_expression(db: Session):
    bind = db.get_bind()
    dialect_name = bind.dialect.name if bind else ""
    if dialect_name in {"mysql", "mariadb"}:
        return func.rand()
    return func.random()


def result_target_status(event: str) -> str:
    if event == "success":
        return "success"
    if event == "invalid":
        return "invalid"
    return "failed"


def mask_target_value(target_type: str, value: str) -> str:
    text = str(value or "")
    if target_type == "phone":
        digits = re.sub(r"\D+", "", text)
        if len(digits) >= 7:
            return f"{digits[:3]}****{digits[-4:]}"
        return text

    if target_type == "contact":
        digits = re.sub(r"\D+", "", text)
        if len(digits) == 11:
            return f"{digits[:3]}****{digits[-4:]}"

    if len(text) <= 4:
        return "*" * len(text)
    return f"{text[:2]}***{text[-2:]}"


def serialize_target(target: TaskTarget) -> TaskTargetItem:
    return TaskTargetItem(
        target_id=target.id,
        target_type=target.target_type,
        target_value=target.target_value,
        masked_value=mask_target_value(target.target_type, target.target_value),
        name=target.name,
        display_name=target.display_name or target.name,
    )


def release_claimed_targets(task_ids: list[int], db: Session) -> None:
    if not task_ids:
        return
    targets = (
        db.query(TaskTarget)
        .filter(TaskTarget.claimed_task_id.in_(task_ids), TaskTarget.status == "claimed")
        .all()
    )
    for target in targets:
        target.status = "pending"
        target.claimed_task_id = None
        target.claimed_at = None
        target.result_message = None


def allowed_slot_count(plan_id: int | None, has_membership: bool) -> int:
    if not has_membership:
        return 1
    if plan_id == 2:
        return 2
    if plan_id == 3:
        return 3
    return 1


def finish_stale_running_tasks(user_id: int, slot_id: int, db: Session) -> bool:
    stale_before = datetime.utcnow() - timedelta(hours=STALE_RUNNING_TASK_HOURS)
    stale_tasks = (
        db.query(Task)
        .filter(
            Task.user_id == user_id,
            Task.slot_id == slot_id,
            Task.status == "running",
            Task.started_at < stale_before,
        )
        .all()
    )
    if not stale_tasks:
        return False

    finished_at = datetime.now(timezone.utc)
    stale_task_ids = [task.id for task in stale_tasks]
    for task in stale_tasks:
        task.status = "finished"
        task.finished_at = finished_at
    release_claimed_targets(stale_task_ids, db)
    db.flush()
    return True


def finish_existing_running_tasks(user_id: int, slot_id: int, db: Session) -> bool:
    running_tasks = (
        db.query(Task)
        .filter(Task.user_id == user_id, Task.slot_id == slot_id, Task.status == "running")
        .all()
    )
    if not running_tasks:
        return False

    finished_at = datetime.now(timezone.utc)
    running_task_ids = [task.id for task in running_tasks]
    for task in running_tasks:
        task.status = "finished"
        task.finished_at = finished_at
    release_claimed_targets(running_task_ids, db)
    db.flush()
    return True


def start_check(
    user: User,
    slot_id: int,
    target_type: str,
    daily_limit: int,
    create_tag: bool,
    greeting_text: str | None,
    db: Session,
) -> StartCheckResponse:
    if target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target type")

    db.query(User).filter(User.id == user.id).with_for_update().first()

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

    finish_existing_running_tasks(user.id, slot_id, db)

    task = Task(
        user_id=user.id,
        device_id=device_id,
        slot_id=slot_id,
        target_type=target_type,
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


def claim_targets(task_id: int, user: User, db: Session) -> ClaimTargetsResponse:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).with_for_update().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task is not running")

    existing_targets = (
        db.query(TaskTarget)
        .filter(TaskTarget.claimed_task_id == task.id)
        .order_by(TaskTarget.id)
        .all()
    )
    if existing_targets:
        return ClaimTargetsResponse(
            task_id=task.id,
            target_type=task.target_type,
            count=len(existing_targets),
            targets=[serialize_target(target) for target in existing_targets],
        )

    limit = random_claim_limit(task.daily_limit)
    targets = (
        db.query(TaskTarget)
        .filter(
            TaskTarget.user_id == user.id,
            TaskTarget.target_type == task.target_type,
            TaskTarget.status == "pending",
        )
        .order_by(random_order_expression(db))
        .limit(limit)
        .with_for_update()
        .all()
    )

    claimed_at = datetime.now(timezone.utc)
    for target in targets:
        target.status = "claimed"
        target.claimed_task_id = task.id
        target.claimed_at = claimed_at
        target.finished_at = None
        target.result_message = None

    if targets:
        db.commit()

    return ClaimTargetsResponse(
        task_id=task.id,
        target_type=task.target_type,
        count=len(targets),
        targets=[serialize_target(target) for target in targets],
    )


def report_result(
    task_id: int,
    target_id: int | None,
    contact_id: int | None,
    event: str,
    message: str,
    user: User,
    db: Session,
) -> dict:
    if not target_id and not contact_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="target_id or contact_id is required")

    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).with_for_update().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    if task.status != "running":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task is not running")

    target: TaskTarget | None = None
    if target_id:
        target = (
            db.query(TaskTarget)
            .filter(
                TaskTarget.id == target_id,
                TaskTarget.user_id == user.id,
                TaskTarget.claimed_task_id == task_id,
            )
            .with_for_update()
            .first()
        )
        if not target:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task target not found")
        existing = (
            db.query(TaskResult)
            .filter(TaskResult.task_id == task_id, TaskResult.target_id == target_id)
            .first()
        )
    else:
        existing = (
            db.query(TaskResult)
            .filter(TaskResult.task_id == task_id, TaskResult.contact_id == contact_id)
            .first()
        )
    if existing:
        return {"charged": existing.trial_charged, "duplicate": True}

    charged = False
    if event == "success":
        quota = db.query(TrialQuota).filter(TrialQuota.user_id == user.id).with_for_update().first()
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
        target_id=target_id,
        contact_id=contact_id,
        target_type=target.target_type if target else None,
        result=event,
        message=message,
        trial_charged=charged,
    )
    db.add(result)
    if target:
        target.status = result_target_status(event)
        target.finished_at = datetime.now(timezone.utc)
        target.result_message = message
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if target_id:
            existing = (
                db.query(TaskResult)
                .filter(TaskResult.task_id == task_id, TaskResult.target_id == target_id)
                .first()
            )
        else:
            existing = (
                db.query(TaskResult)
                .filter(TaskResult.task_id == task_id, TaskResult.contact_id == contact_id)
                .first()
            )
        if existing:
            return {"charged": existing.trial_charged, "duplicate": True}
        raise

    return {"charged": charged, "duplicate": False}


def finish_task(task_id: int, user: User, db: Session) -> TaskResponse:
    task = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).with_for_update().first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    task.status = "finished"
    task.finished_at = datetime.now(timezone.utc)
    release_claimed_targets([task.id], db)
    db.commit()
    db.refresh(task)

    return TaskResponse(
        id=task.id,
        user_id=task.user_id,
        device_id=task.device_id,
        slot_id=task.slot_id,
        target_type=task.target_type,
        daily_limit=task.daily_limit,
        create_tag=task.create_tag,
        greeting_text=task.greeting_text,
        status=task.status,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )
