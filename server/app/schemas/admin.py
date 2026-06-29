from datetime import datetime

from pydantic import BaseModel


class AdminLoginRequest(BaseModel):
    username: str
    password: str


class AdminInfo(BaseModel):
    id: int
    username: str
    role: str


class AdminTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin: AdminInfo


class UserListItem(BaseModel):
    id: int
    email: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None


class UserDetailDevice(BaseModel):
    id: int
    machine_code_hash: str
    status: str
    bound_at: datetime | None = None
    last_seen_at: datetime | None = None
    remark: str | None = None


class UserDetailMembership(BaseModel):
    is_active: bool = False
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    status: str | None = None


class UserDetailTrial(BaseModel):
    total: int = 20
    used: int = 0
    remaining: int = 20


class UserDetailResponse(BaseModel):
    id: int
    email: str
    status: str
    created_at: datetime
    last_login_at: datetime | None = None
    devices: list[UserDetailDevice] = []
    membership: UserDetailMembership | None = None
    trial: UserDetailTrial | None = None


class UpdateMembershipRequest(BaseModel):
    action: str
    days: int | None = None


class UpdateDeviceRequest(BaseModel):
    status: str | None = None
    remark: str | None = None
    unbind: bool = False


class UpdatePlanRequest(BaseModel):
    name: str | None = None
    duration_days: int | None = None
    price_cents: int | None = None
    enabled: bool | None = None


class ConfirmOrderPaymentRequest(BaseModel):
    channel: str | None = "manual_wechat"
    remark: str | None = None


class AdminPlanResponse(BaseModel):
    id: int
    name: str
    duration_days: int
    price_cents: int
    enabled: bool


class OrderListItem(BaseModel):
    id: int
    order_no: str
    user_id: int
    email: str | None = None
    plan_id: int
    amount_cents: int
    payment_channel: str | None = None
    status: str
    paid_at: datetime | None = None
    created_at: datetime


class TaskListItem(BaseModel):
    id: int
    user_id: int
    email: str | None = None
    device_id: int
    daily_limit: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    success_count: int = 0
    failed_count: int = 0
    invalid_count: int = 0


class TaskResultItem(BaseModel):
    id: int
    contact_id: int | None = None
    result: str
    message: str | None = None
    trial_charged: bool = False
    created_at: datetime


class AuditLogItem(BaseModel):
    id: int
    admin_username: str | None = None
    action: str
    target_type: str | None = None
    target_id: int | None = None
    detail: str | None = None
    created_at: datetime
