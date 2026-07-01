from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AdminLoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=128)


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
    action: Literal["extend", "freeze", "unfreeze", "expire"]
    days: int | None = Field(default=None, ge=1, le=3650)


class UpdateTrialQuotaRequest(BaseModel):
    action: Literal["decrement", "set_remaining", "clear"]
    amount: int | None = Field(default=None, ge=1, le=10_000)
    remaining_count: int | None = Field(default=None, ge=0, le=10_000)


class UpdateDeviceRequest(BaseModel):
    status: Literal["active", "inactive", "blocked"] | None = None
    remark: str | None = Field(default=None, max_length=500)
    unbind: bool = False


class UpdatePlanRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)
    duration_days: int | None = Field(default=None, ge=1, le=3650)
    price_cents: int | None = Field(default=None, ge=0, le=10_000_000)
    enabled: bool | None = None


class ConfirmOrderPaymentRequest(BaseModel):
    channel: Literal["manual_wechat", "wechat", "alipay"] | None = "manual_wechat"
    remark: str | None = Field(default=None, max_length=500)


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
    slot_id: int = 1
    target_type: str = "phone"
    daily_limit: int
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    success_count: int = 0
    failed_count: int = 0
    invalid_count: int = 0


class TaskResultItem(BaseModel):
    id: int
    target_id: int | None = None
    target_type: str | None = None
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
