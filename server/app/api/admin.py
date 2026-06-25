from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.admin_user import AdminUser
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenResponse,
    AuditLogItem,
    OrderListItem,
    TaskListItem,
    TaskResultItem,
    UpdateDeviceRequest,
    UpdateMembershipRequest,
    UpdatePlanRequest,
    UserDetailResponse,
    UserListItem,
)
from app.services.admin_service import (
    admin_login,
    list_audit_logs,
    list_contacts,
    list_devices,
    list_orders,
    list_plans,
    list_task_results,
    list_tasks,
    list_users,
    get_user_detail,
    rebind_device,
    update_device,
    update_membership,
    update_plan,
)

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/login", response_model=AdminTokenResponse)
def login(req: AdminLoginRequest, db: Session = Depends(get_db)):
    return admin_login(req.username, req.password, db)


@router.get("/users")
def get_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_users(page, page_size, db)


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return get_user_detail(user_id, db)


@router.patch("/users/{user_id}/membership")
def patch_membership(
    user_id: int,
    req: UpdateMembershipRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_membership(user_id, req.action, req.days, admin.id, db)


@router.get("/devices")
def get_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_devices(page, page_size, db)


@router.patch("/devices/{device_id}")
def patch_device(
    device_id: int,
    req: UpdateDeviceRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_device(device_id, req.status, req.remark, req.unbind, admin.id, db)


@router.post("/devices/{device_id}/rebind")
def rebind_device_endpoint(
    device_id: int,
    new_user_id: int = Query(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return rebind_device(device_id, new_user_id, admin.id, db)


@router.get("/plans")
def get_plans(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_plans(db)


@router.patch("/plans/{plan_id}")
def patch_plan(
    plan_id: int,
    req: UpdatePlanRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_plan(plan_id, req, admin.id, db)


@router.get("/orders")
def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_orders(page, page_size, status, db)


@router.get("/tasks")
def get_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_tasks(page, page_size, status, db)


@router.get("/tasks/{task_id}/results")
def get_task_results(
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_task_results(task_id, db)


@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_audit_logs(page, page_size, db)


@router.get("/contacts")
def get_contacts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return list_contacts(page, page_size, q, db)
