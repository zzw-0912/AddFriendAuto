export const API_BASE = import.meta.env.VITE_API_BASE || "";

export interface PageResponse<T> {
  items: T[];
  total: number;
  page?: number;
  page_size?: number;
}

export interface AdminInfo {
  id: number;
  username: string;
  role: string;
}

export interface AdminLoginResponse {
  access_token: string;
  token_type: string;
  admin: AdminInfo;
}

export interface UserListItem {
  id: number;
  email: string;
  status: string;
  created_at: string;
  last_login_at?: string | null;
}

export interface UserDetailDevice {
  id: number;
  machine_code_hash: string;
  status: string;
  bound_at?: string | null;
  last_seen_at?: string | null;
  remark?: string | null;
}

export interface UserDetailMembership {
  is_active: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  status?: string | null;
}

export interface UserDetailTrial {
  total: number;
  used: number;
  remaining: number;
}

export interface UserDetail {
  id: number;
  email: string;
  status: string;
  created_at: string;
  last_login_at?: string | null;
  devices: UserDetailDevice[];
  membership?: UserDetailMembership | null;
  trial?: UserDetailTrial | null;
}

export interface MembershipUpdateResult {
  success: boolean;
  membership_id?: number;
  ends_at?: string;
  frozen_count?: number;
  unfrozen_count?: number;
  expired_count?: number;
}

export interface TrialQuotaUpdateResult {
  success: boolean;
  total: number;
  used: number;
  remaining: number;
}

export interface DeviceListItem extends UserDetailDevice {
  user_id: number;
  email?: string | null;
}

export interface PlanItem {
  id: number;
  name: string;
  duration_days: number;
  price_cents: number;
  enabled: boolean;
}

export interface OrderListItem {
  id: number;
  order_no: string;
  user_id: number;
  email?: string | null;
  plan_id: number;
  amount_cents: number;
  payment_channel?: string | null;
  status: string;
  paid_at?: string | null;
  created_at: string;
}

export interface TaskListItem {
  id: number;
  user_id: number;
  email?: string | null;
  device_id: number;
  slot_id: number;
  target_type: string;
  daily_limit: number;
  status: string;
  started_at: string;
  finished_at?: string | null;
  success_count: number;
  failed_count: number;
  invalid_count: number;
}

export interface TaskResultItem {
  id: number;
  target_id?: number | null;
  target_type?: string | null;
  contact_id?: number | null;
  result: string;
  message?: string | null;
  trial_charged: boolean;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  admin_user_id?: number;
  admin_username?: string | null;
  action: string;
  target_type?: string | null;
  target_id?: number | null;
  detail?: string | null;
  created_at: string;
}

export interface ContactListItem {
  id: number;
  wechat_nickname?: string | null;
  wechat_id?: string | null;
  tag?: string | null;
  status?: string | null;
  remark?: string | null;
}

export interface FeedbackItem {
  id: number;
  user_id: number;
  email?: string | null;
  content?: string;
  images?: string[] | null;
  created_at?: string;
}

export function resolveAssetUrl(url: string) {
  if (!url) return "";
  if (/^(https?:)?\/\//.test(url) || url.startsWith("data:") || url.startsWith("blob:")) {
    return url;
  }
  if (!API_BASE) return url;
  return `${API_BASE.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

function getToken(): string | null {
  return localStorage.getItem("admin_token");
}

export function setToken(token: string) {
  localStorage.setItem("admin_token", token);
}

export function clearToken() {
  localStorage.removeItem("admin_token");
}

export function isLoggedIn(): boolean {
  return !!getToken();
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  if (res.status === 401) {
    clearToken();
    window.location.hash = "#/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function login(username: string, password: string): Promise<AdminLoginResponse> {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `登录失败 (${res.status})`);
  }
  const data = await res.json() as AdminLoginResponse;
  setToken(data.access_token);
  return data;
}

export async function getUsers(page = 1, pageSize = 20): Promise<PageResponse<UserListItem>> {
  return request(`/admin/users?page=${page}&page_size=${pageSize}`);
}

export async function getUserDetail(userId: number): Promise<UserDetail> {
  return request(`/admin/users/${userId}`);
}

export async function updateMembership(userId: number, action: "extend" | "freeze" | "unfreeze" | "expire", days?: number): Promise<MembershipUpdateResult> {
  return request(`/admin/users/${userId}/membership`, {
    method: "PATCH",
    body: JSON.stringify({ action, days }),
  });
}

export async function updateTrialQuota(
  userId: number,
  data: { action: "decrement" | "set_remaining" | "clear"; amount?: number; remaining_count?: number },
): Promise<TrialQuotaUpdateResult> {
  return request(`/admin/users/${userId}/trial-quota`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getDevices(page = 1, pageSize = 20): Promise<PageResponse<DeviceListItem>> {
  return request(`/admin/devices?page=${page}&page_size=${pageSize}`);
}

export async function updateDevice(deviceId: number, data: { status?: "active" | "inactive" | "blocked"; remark?: string; unbind?: boolean }): Promise<{ success: boolean; action: string }> {
  return request(`/admin/devices/${deviceId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function rebindDevice(deviceId: number, newUserId: number): Promise<{ success: boolean; action: string }> {
  return request(`/admin/devices/${deviceId}/rebind?new_user_id=${newUserId}`, {
    method: "POST",
  });
}

export async function getPlans(): Promise<PlanItem[]> {
  return request("/admin/plans");
}

export async function updatePlan(planId: number, data: Partial<Pick<PlanItem, "name" | "duration_days" | "price_cents" | "enabled">>): Promise<PlanItem> {
  return request(`/admin/plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getOrders(page = 1, pageSize = 20, status?: string): Promise<PageResponse<OrderListItem>> {
  let path = `/admin/orders?page=${page}&page_size=${pageSize}`;
  if (status) path += `&status=${status}`;
  return request(path);
}

export async function confirmOrderPayment(orderId: number, data: { channel?: "manual_wechat" | "wechat" | "alipay"; remark?: string } = {}): Promise<{ success: boolean }> {
  return request(`/admin/orders/${orderId}/confirm-payment`, {
    method: "POST",
    body: JSON.stringify({ channel: "manual_wechat", ...data }),
  });
}

export async function getTasks(page = 1, pageSize = 20, status?: string): Promise<PageResponse<TaskListItem>> {
  let path = `/admin/tasks?page=${page}&page_size=${pageSize}`;
  if (status) path += `&status=${status}`;
  return request(path);
}

export async function getTaskResults(taskId: number): Promise<TaskResultItem[]> {
  return request(`/admin/tasks/${taskId}/results`);
}

export async function getAuditLogs(page = 1, pageSize = 20): Promise<PageResponse<AuditLogItem>> {
  return request(`/admin/audit-logs?page=${page}&page_size=${pageSize}`);
}

export async function getContacts(page = 1, pageSize = 20, q?: string): Promise<PageResponse<ContactListItem>> {
  let path = `/admin/contacts?page=${page}&page_size=${pageSize}`;
  if (q) path += `&q=${encodeURIComponent(q)}`;
  return request(path);
}

export async function getFeedback(page = 1, pageSize = 20): Promise<PageResponse<FeedbackItem>> {
  return request(`/admin/feedback?page=${page}&page_size=${pageSize}`);
}
