import hashlib
import json
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password, verify_password
from app.models.admin_audit_log import AdminAuditLog
from app.models.admin_user import AdminUser
from app.models.contact import Contact
from app.models.device import Device
from app.models.feedback import Feedback
from app.models.membership import Membership
from app.models.order import Order
from app.models.plan import Plan
from app.models.task import Task
from app.models.task_result import TaskResult
from app.models.trial_quota import TrialQuota
from app.models.user import User
from app.schemas.admin import (
    AdminInfo,
    AdminPlanResponse,
    AuditLogItem,
    OrderListItem,
    TaskListItem,
    TaskResultItem,
    UserDetailDevice,
    UserDetailMembership,
    UserDetailResponse,
    UserDetailTrial,
    UserListItem,
)
from app.services.payment_service import process_order_payment


def _is_bcrypt_hash(password_hash: str) -> bool:
    return password_hash.startswith(("$2a$", "$2b$", "$2y$"))


def _verify_admin_password(admin: AdminUser, password: str, db: Session) -> bool:
    if _is_bcrypt_hash(admin.password_hash):
        try:
            return verify_password(password, admin.password_hash)
        except ValueError:
            return False

    legacy_hash = hashlib.sha256(password.encode()).hexdigest()
    if admin.password_hash != legacy_hash:
        return False

    admin.password_hash = hash_password(password)
    db.commit()
    return True


def admin_login(username: str, password: str, db: Session) -> dict:
    admin = db.query(AdminUser).filter(AdminUser.username == username, AdminUser.status == "active").first()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    if not _verify_admin_password(admin, password, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token({
        "sub": f"admin_{admin.id}",
        "username": admin.username,
        "role": admin.role,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "admin": AdminInfo(id=admin.id, username=admin.username, role=admin.role).model_dump(),
    }


def create_audit_log(admin_user_id: int, action: str, target_type: str | None = None,
                     target_id: int | None = None, detail: str | None = None, db: Session | None = None):
    if db is None:
        return
    log = AdminAuditLog(
        admin_user_id=admin_user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
    )
    db.add(log)
    db.commit()


def list_users(page: int, page_size: int, db: Session) -> dict:
    query = db.query(User).order_by(User.id.desc())
    total = query.count()
    users = query.offset((page - 1) * page_size).limit(page_size).all()
    items = [
        UserListItem(
            id=u.id, email=u.email, status=u.status,
            created_at=u.created_at, last_login_at=u.last_login_at,
        )
        for u in users
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def get_user_detail(user_id: int, db: Session) -> UserDetailResponse:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    devices_q = db.query(Device).filter(Device.user_id == user_id).all()
    device_infos = [
        UserDetailDevice(
            id=d.id, machine_code_hash=d.machine_code_hash,
            status=d.status, bound_at=d.bound_at,
            last_seen_at=d.last_seen_at, remark=d.remark,
        )
        for d in devices_q
    ]

    membership_info = None
    active_membership = (
        db.query(Membership)
        .filter(Membership.user_id == user_id)
        .order_by(Membership.ends_at.desc())
        .first()
    )
    if active_membership:
        ends = active_membership.ends_at
        if ends and ends.tzinfo:
            ends = ends.replace(tzinfo=None)
        membership_info = UserDetailMembership(
            is_active=active_membership.status == "active" and ends > datetime.utcnow(),
            starts_at=active_membership.starts_at,
            ends_at=active_membership.ends_at,
            status=active_membership.status,
        )

    trial_info = None
    quota = db.query(TrialQuota).filter(TrialQuota.user_id == user_id).first()
    if quota:
        trial_info = UserDetailTrial(total=quota.total_count, used=quota.used_count, remaining=quota.remaining_count)

    return UserDetailResponse(
        id=user.id, email=user.email, status=user.status,
        created_at=user.created_at, last_login_at=user.last_login_at,
        devices=device_infos, membership=membership_info, trial=trial_info,
    )


def update_membership(user_id: int, action: str, days: int | None,
                      admin_user_id: int, db: Session) -> dict:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    now = datetime.utcnow()

    if action == "extend":
        if not days or days <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="days must be positive")

        active = (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.status == "active",
                Membership.ends_at > now,
            )
            .order_by(Membership.ends_at.desc())
            .first()
        )

        if active:
            new_start = active.ends_at
        else:
            new_start = now

        membership = Membership(
            user_id=user_id,
            starts_at=new_start,
            ends_at=new_start + timedelta(days=days),
            status="active",
        )
        db.add(membership)
        db.commit()
        db.refresh(membership)

        create_audit_log(admin_user_id, "extend_membership", "user", user_id,
                         f"Extended membership by {days} days, new ends_at: {membership.ends_at}", db)
        return {"success": True, "membership_id": membership.id, "ends_at": str(membership.ends_at)}

    elif action == "freeze":
        active = (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.status == "active",
                Membership.ends_at > now,
            )
            .all()
        )
        for m in active:
            m.status = "frozen"
        db.commit()
        create_audit_log(admin_user_id, "freeze_membership", "user", user_id, "Frozen all active memberships", db)
        return {"success": True, "frozen_count": len(active)}

    elif action == "unfreeze":
        frozen = (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.status == "frozen",
            )
            .all()
        )
        for m in frozen:
            m.status = "active"
        db.commit()
        create_audit_log(admin_user_id, "unfreeze_membership", "user", user_id,
                         f"Unfrozen {len(frozen)} memberships", db)
        return {"success": True, "unfrozen_count": len(frozen)}

    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown action: {action}")


def list_devices(page: int, page_size: int, db: Session) -> dict:
    query = db.query(Device).order_by(Device.id.desc())
    total = query.count()
    devices = query.offset((page - 1) * page_size).limit(page_size).all()

    user_ids = [d.user_id for d in devices]
    users_map = {u.id: u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    items = []
    for d in devices:
        d_dict = {
            "id": d.id, "user_id": d.user_id, "email": users_map.get(d.user_id),
            "machine_code_hash": d.machine_code_hash, "status": d.status,
            "bound_at": d.bound_at, "last_seen_at": d.last_seen_at, "remark": d.remark,
        }
        items.append(d_dict)

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def update_device(device_id: int, status: str | None, remark: str | None,
                  unbind: bool, admin_user_id: int, db: Session) -> dict:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")

    if unbind:
        old_user_id = device.user_id
        db.delete(device)
        db.commit()
        create_audit_log(admin_user_id, "unbind_device", "device", device_id,
                         f"Unbound from user {old_user_id}", db)
        return {"success": True, "action": "unbound"}

    if status is not None:
        device.status = status
    if remark is not None:
        device.remark = remark
    db.commit()

    create_audit_log(admin_user_id, "update_device", "device", device_id,
                     f"Updated: status={status}, remark={remark}", db)
    return {"success": True, "action": "updated"}


def rebind_device(device_id: int, new_user_id: int, admin_user_id: int, db: Session) -> dict:
    device = db.query(Device).filter(Device.id == device_id).first()
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    new_user = db.query(User).filter(User.id == new_user_id).first()
    if not new_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="New user not found")

    existing_devices = db.query(Device).filter(Device.user_id == new_user_id, Device.id != device_id).all()
    for existing in existing_devices:
        db.delete(existing)

    old_user_id = device.user_id
    device.user_id = new_user_id
    device.status = "active"
    db.commit()

    create_audit_log(admin_user_id, "rebind_device", "device", device_id,
                     f"Rebound from user {old_user_id} to user {new_user_id}", db)
    return {"success": True, "action": "rebound", "old_user_id": old_user_id, "new_user_id": new_user_id}


def list_plans(db: Session) -> list:
    plans = db.query(Plan).order_by(Plan.id).all()
    return [AdminPlanResponse(
        id=p.id, name=p.name, duration_days=p.duration_days,
        price_cents=p.price_cents, enabled=p.enabled,
    ) for p in plans]


def update_plan(plan_id: int, req, admin_user_id: int, db: Session) -> AdminPlanResponse:
    plan = db.query(Plan).filter(Plan.id == plan_id).first()
    if not plan:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")

    changes = []
    if req.name is not None:
        changes.append(f"name: {plan.name} -> {req.name}")
        plan.name = req.name
    if req.duration_days is not None:
        changes.append(f"duration: {plan.duration_days} -> {req.duration_days}")
        plan.duration_days = req.duration_days
    if req.price_cents is not None:
        changes.append(f"price: {plan.price_cents} -> {req.price_cents}")
        plan.price_cents = req.price_cents
    if req.enabled is not None:
        changes.append(f"enabled: {plan.enabled} -> {req.enabled}")
        plan.enabled = req.enabled

    db.commit()
    db.refresh(plan)

    if changes:
        create_audit_log(admin_user_id, "update_plan", "plan", plan_id, "; ".join(changes), db)

    return AdminPlanResponse(
        id=plan.id, name=plan.name, duration_days=plan.duration_days,
        price_cents=plan.price_cents, enabled=plan.enabled,
    )


def list_orders(page: int, page_size: int, status_filter: str | None, db: Session) -> dict:
    query = db.query(Order).order_by(Order.id.desc())
    if status_filter:
        query = query.filter(Order.status == status_filter)
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()

    user_ids = [o.user_id for o in orders]
    users_map = {u.id: u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    items = [OrderListItem(
        id=o.id, order_no=o.order_no, user_id=o.user_id,
        email=users_map.get(o.user_id), plan_id=o.plan_id,
        amount_cents=o.amount_cents, payment_channel=o.payment_channel,
        status=o.status, paid_at=o.paid_at, created_at=o.created_at,
    ) for o in orders]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def confirm_order_payment(order_id: int, channel: str | None, remark: str | None,
                          admin_user_id: int, db: Session) -> dict:
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    payment_channel = channel or order.payment_channel or "manual_wechat"
    result = process_order_payment(order, payment_channel, db)
    detail_parts = [
        f"Confirmed order {order.order_no}",
        f"user_id={order.user_id}",
        f"amount_cents={order.amount_cents}",
        f"channel={payment_channel}",
        f"result={result.get('message')}",
    ]
    if remark:
        detail_parts.append(f"remark={remark}")
    create_audit_log(
        admin_user_id,
        "confirm_order_payment",
        "order",
        order.id,
        "; ".join(detail_parts),
        db,
    )
    return result


def list_tasks(page: int, page_size: int, status_filter: str | None, db: Session) -> dict:
    query = db.query(Task).order_by(Task.id.desc())
    if status_filter:
        query = query.filter(Task.status == status_filter)
    total = query.count()
    tasks = query.offset((page - 1) * page_size).limit(page_size).all()

    user_ids = [t.user_id for t in tasks]
    users_map = {u.id: u.email for u in db.query(User).filter(User.id.in_(user_ids)).all()} if user_ids else {}

    task_ids = [t.id for t in tasks]
    stats_map = {}
    if task_ids:
        from sqlalchemy import func
        rows = (
            db.query(TaskResult.task_id, TaskResult.result, func.count(TaskResult.id))
            .filter(TaskResult.task_id.in_(task_ids))
            .group_by(TaskResult.task_id, TaskResult.result)
            .all()
        )
        for task_id, result, cnt in rows:
            if task_id not in stats_map:
                stats_map[task_id] = {"success": 0, "failed": 0, "invalid": 0}
            key = result if result in ("success", "failed", "invalid") else "failed"
            stats_map[task_id][key] = cnt

    items = []
    for t in tasks:
        s = stats_map.get(t.id, {"success": 0, "failed": 0, "invalid": 0})
        items.append(TaskListItem(
            id=t.id, user_id=t.user_id, email=users_map.get(t.user_id),
            device_id=t.device_id, slot_id=t.slot_id, daily_limit=t.daily_limit,
            status=t.status, started_at=t.started_at, finished_at=t.finished_at,
            success_count=s["success"], failed_count=s["failed"], invalid_count=s["invalid"],
        ))

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_task_results(task_id: int, db: Session) -> list:
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    results = db.query(TaskResult).filter(TaskResult.task_id == task_id).order_by(TaskResult.id).all()
    return [TaskResultItem(
        id=r.id, contact_id=r.contact_id, result=r.result,
        message=r.message, trial_charged=r.trial_charged, created_at=r.created_at,
    ) for r in results]


def list_audit_logs(page: int, page_size: int, db: Session) -> dict:
    query = db.query(AdminAuditLog).order_by(AdminAuditLog.id.desc())
    total = query.count()
    logs = query.offset((page - 1) * page_size).limit(page_size).all()

    admin_ids = [l.admin_user_id for l in logs]
    admins_map = {a.id: a.username for a in db.query(AdminUser).filter(AdminUser.id.in_(admin_ids)).all()} if admin_ids else {}

    items = [AuditLogItem(
        id=l.id, admin_username=admins_map.get(l.admin_user_id),
        action=l.action, target_type=l.target_type, target_id=l.target_id,
        detail=l.detail, created_at=l.created_at,
    ) for l in logs]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_contacts(page: int, page_size: int, q: str | None, db: Session) -> dict:
    query = db.query(Contact).order_by(Contact.id.desc())
    if q:
        like = f"%{q}%"
        query = query.filter(
            Contact.wechat_nickname.ilike(like) | Contact.wechat_id.ilike(like)
        )
    total = query.count()
    contacts = query.offset((page - 1) * page_size).limit(page_size).all()

    items = []
    for c in contacts:
        items.append({
            "id": c.id, "wechat_nickname": c.wechat_nickname,
            "wechat_id": c.wechat_id, "tag": c.tag,
            "status": c.status, "remark": c.remark, "created_at": c.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_feedback(page: int, page_size: int, db: Session) -> dict:
    query = db.query(Feedback).order_by(Feedback.id.desc())
    total = query.count()
    feedbacks = query.offset((page - 1) * page_size).limit(page_size).all()

    user_cache: dict[int, str] = {}
    items = []
    for fb in feedbacks:
        if fb.user_id not in user_cache:
            u = db.query(User).filter(User.id == fb.user_id).first()
            user_cache[fb.user_id] = u.email if u else None
        images = json.loads(fb.images) if fb.images else None
        items.append({
            "id": fb.id,
            "user_id": fb.user_id,
            "email": user_cache[fb.user_id],
            "content": fb.content,
            "images": images,
            "created_at": fb.created_at,
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}
