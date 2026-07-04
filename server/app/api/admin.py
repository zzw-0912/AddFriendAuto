import logging

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.admin_user import AdminUser
from app.schemas.admin import (
    AdminLoginRequest,
    AdminTokenResponse,
    AuditLogItem,
    ConfirmOrderPaymentRequest,
    OrderListItem,
    TaskListItem,
    TaskResultItem,
    UpdateDeviceRequest,
    UpdateMembershipRequest,
    UpdatePlanRequest,
    UpdateTrialQuotaRequest,
    UserDetailResponse,
    UserListItem,
)
from app.schemas.client_update import ClientUpdateConfigRequest, ClientUpdateConfigResponse
from app.schemas.hero_slide import HeroSlideResponse
from app.services.admin_service import (
    admin_login,
    audit_detail,
    confirm_order_payment,
    create_audit_log,
    delete_user,
    list_audit_logs,
    list_devices,
    list_feedback,
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
    update_trial_quota,
)
from app.services.client_update_service import (
    clear_client_update_qr_image,
    get_client_update_config,
    set_client_force_update,
    update_client_update_config,
    upload_client_update_qr_image,
)
from app.services.hero_slide_service import clear_hero_slide_image, list_hero_slides, upload_hero_slide_image

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger("friendauto.admin.api")


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
    result = list_users(page, page_size, db)
    create_audit_log(
        admin.id,
        "view_users",
        "user",
        None,
        audit_detail(page=page, page_size=page_size, total=result.get("total")),
        db,
    )
    return result


@router.get("/users/{user_id}", response_model=UserDetailResponse)
def get_user(
    user_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = get_user_detail(user_id, db)
    create_audit_log(admin.id, "view_user_detail", "user", user_id, audit_detail(email=result.email), db)
    return result


@router.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return delete_user(user_id, admin.id, db)


@router.patch("/users/{user_id}/membership")
def patch_membership(
    user_id: int,
    req: UpdateMembershipRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_membership(user_id, req.action, req.days, admin.id, db)


@router.patch("/users/{user_id}/trial-quota")
def patch_trial_quota(
    user_id: int,
    req: UpdateTrialQuotaRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return update_trial_quota(user_id, req.action, req.amount, req.remaining_count, admin.id, db)


@router.get("/devices")
def get_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = list_devices(page, page_size, db)
    create_audit_log(
        admin.id,
        "view_devices",
        "device",
        None,
        audit_detail(page=page, page_size=page_size, total=result.get("total")),
        db,
    )
    return result


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
    result = list_plans(db)
    create_audit_log(admin.id, "view_plans", "plan", None, audit_detail(count=len(result)), db)
    return result


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
    result = list_orders(page, page_size, status, db)
    create_audit_log(
        admin.id,
        "view_orders",
        "order",
        None,
        audit_detail(page=page, page_size=page_size, status=status, total=result.get("total")),
        db,
    )
    return result


@router.post("/orders/{order_id}/confirm-payment")
def post_confirm_order_payment(
    order_id: int,
    req: ConfirmOrderPaymentRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return confirm_order_payment(order_id, req.channel, req.remark, admin.id, db)


@router.get("/tasks")
def get_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = list_tasks(page, page_size, status, db)
    create_audit_log(
        admin.id,
        "view_tasks",
        "task",
        None,
        audit_detail(page=page, page_size=page_size, status=status, total=result.get("total")),
        db,
    )
    return result


@router.get("/tasks/{task_id}/results")
def get_task_results(
    task_id: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = list_task_results(task_id, db)
    create_audit_log(admin.id, "view_task_results", "task", task_id, audit_detail(count=len(result)), db)
    return result


@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = list_audit_logs(page, page_size, db)
    create_audit_log(
        admin.id,
        "view_audit_logs",
        "audit_log",
        None,
        audit_detail(page=page, page_size=page_size, total=result.get("total")),
        db,
    )
    return result


@router.get("/feedback")
def get_feedback(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = list_feedback(page, page_size, db)
    create_audit_log(
        admin.id,
        "view_feedback",
        "feedback",
        None,
        audit_detail(page=page, page_size=page_size, total=result.get("total")),
        db,
    )
    return result


@router.get("/client-update", response_model=ClientUpdateConfigResponse)
def get_admin_client_update_config(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = get_client_update_config(db)
    create_audit_log(admin.id, "view_client_update_config", "client_update", 1, audit_detail(), db)
    return result


@router.patch("/client-update", response_model=ClientUpdateConfigResponse)
def patch_admin_client_update_config(
    req: ClientUpdateConfigRequest,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = update_client_update_config(req, db)
    create_audit_log(
        admin.id,
        "update_client_update_config",
        "client_update",
        1,
        audit_detail(
            latest_version=result.latest_version,
            force_update_enabled=result.force_update_enabled,
            download_url=result.download_url,
        ),
        db,
    )
    return result


@router.post("/client-update/force", response_model=ClientUpdateConfigResponse)
def post_admin_client_update_force(
    enabled: bool = Query(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    result = set_client_force_update(enabled, db)
    create_audit_log(
        admin.id,
        "toggle_client_force_update",
        "client_update",
        1,
        audit_detail(enabled=enabled, latest_version=result.latest_version),
        db,
    )
    return result


@router.post("/client-update/qr-image", response_model=ClientUpdateConfigResponse)
def post_admin_client_update_qr_image(
    image: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logger.info(
        "admin_client_update_qr_upload_request admin_id=%s filename=%s content_type=%s size=%s",
        admin.id,
        image.filename,
        image.content_type,
        getattr(image, "size", None),
    )
    result = upload_client_update_qr_image(image, db)
    logger.info(
        "admin_client_update_qr_upload_success admin_id=%s image_url=%s",
        admin.id,
        result.qr_image_url,
    )
    create_audit_log(
        admin.id,
        "upload_client_update_qr_image",
        "client_update",
        1,
        audit_detail(qr_image_url=result.qr_image_url),
        db,
    )
    return result


@router.delete("/client-update/qr-image", response_model=ClientUpdateConfigResponse)
def delete_admin_client_update_qr_image(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logger.info("admin_client_update_qr_clear_request admin_id=%s", admin.id)
    result = clear_client_update_qr_image(db)
    logger.info("admin_client_update_qr_clear_success admin_id=%s", admin.id)
    create_audit_log(admin.id, "clear_client_update_qr_image", "client_update", 1, audit_detail(), db)
    return result


@router.get("/hero-slides", response_model=list[HeroSlideResponse])
def get_admin_hero_slides(
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logger.info("admin_hero_slides_list_request admin_id=%s", admin.id)
    result = list_hero_slides(db)
    create_audit_log(admin.id, "view_hero_slides", "hero_slide", None, audit_detail(count=len(result)), db)
    return result


@router.post("/hero-slides/{slot_index}/image", response_model=HeroSlideResponse)
def post_admin_hero_slide_image(
    slot_index: int,
    image: UploadFile = File(...),
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logger.info(
        "admin_hero_slide_upload_request admin_id=%s slot=%s filename=%s content_type=%s size=%s",
        admin.id,
        slot_index,
        image.filename,
        image.content_type,
        getattr(image, "size", None),
    )
    result = upload_hero_slide_image(slot_index, image, db)
    logger.info(
        "admin_hero_slide_upload_success admin_id=%s slot=%s image_url=%s",
        admin.id,
        slot_index,
        result.image_url,
    )
    create_audit_log(
        admin.id,
        "upload_hero_slide_image",
        "hero_slide",
        slot_index,
        audit_detail(slot_index=slot_index, image_url=result.image_url),
        db,
    )
    return result


@router.delete("/hero-slides/{slot_index}/image", response_model=HeroSlideResponse)
def delete_admin_hero_slide_image(
    slot_index: int,
    admin: AdminUser = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    logger.info("admin_hero_slide_clear_request admin_id=%s slot=%s", admin.id, slot_index)
    result = clear_hero_slide_image(slot_index, db)
    logger.info("admin_hero_slide_clear_success admin_id=%s slot=%s", admin.id, slot_index)
    create_audit_log(
        admin.id,
        "clear_hero_slide_image",
        "hero_slide",
        slot_index,
        audit_detail(slot_index=slot_index),
        db,
    )
    return result
