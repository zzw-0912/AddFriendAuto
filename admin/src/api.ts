export const API_BASE = import.meta.env.VITE_API_BASE || "http://47.111.3.83:8001";

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

export interface DeleteUserResult {
  success: boolean;
  deleted_user_id: number;
  email: string;
  deleted_counts: Record<string, number>;
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

export interface FeedbackItem {
  id: number;
  user_id: number;
  email?: string | null;
  content?: string;
  images?: string[] | null;
  created_at?: string;
}

export interface HeroSlideItem {
  slot_index: number;
  image_url?: string | null;
  updated_at?: string | null;
}

export interface ClientUpdateConfig {
  latest_version: string;
  force_update_enabled: boolean;
  download_url?: string | null;
  qr_image_url?: string | null;
  message?: string | null;
  updated_at?: string | null;
}

export class ApiRequestError extends Error {
  status: number;
  path: string;
  method: string;
  responseText: string;

  constructor(message: string, status: number, path: string, method: string, responseText = "") {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.path = path;
    this.method = method;
    this.responseText = responseText;
  }
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

function parseErrorText(text: string): string {
  if (!text) return "";
  try {
    const body = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (typeof body.message === "string") return body.message;
    if (body.detail) return JSON.stringify(body.detail);
  } catch {}
  return text.replace(/\s+/g, " ").trim().slice(0, 300);
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken();
  const method = (options.method || "GET").toString().toUpperCase();
  const headers = new Headers(options.headers);
  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  if (!isFormData && options.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  } catch (err: unknown) {
    console.error("[admin-api] request network failed", { method, path, error: err });
    throw new ApiRequestError(`网络请求失败：${method} ${path}`, 0, path, method);
  }
  if (res.status === 401) {
    clearToken();
    window.location.hash = "#/login";
    throw new ApiRequestError(`登录已失效：${method} ${path}`, 401, path, method);
  }
  if (!res.ok) {
    const responseText = await res.text().catch(() => "");
    const detail = parseErrorText(responseText);
    console.error("[admin-api] request failed", {
      method,
      path,
      status: res.status,
      detail,
      responseText: responseText.slice(0, 1000),
    });
    throw new ApiRequestError(
      `请求失败：${method} ${path}，HTTP ${res.status}${detail ? `，${detail}` : ""}`,
      res.status,
      path,
      method,
      responseText,
    );
  }
  if (res.status === 204) return undefined as T;
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
  data: { action: "increment" | "decrement" | "set_remaining" | "clear"; amount?: number; remaining_count?: number },
): Promise<TrialQuotaUpdateResult> {
  return request(`/admin/users/${userId}/trial-quota`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function deleteUser(userId: number): Promise<DeleteUserResult> {
  return request(`/admin/users/${userId}`, {
    method: "DELETE",
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

export async function getFeedback(page = 1, pageSize = 20): Promise<PageResponse<FeedbackItem>> {
  return request(`/admin/feedback?page=${page}&page_size=${pageSize}`);
}

export async function getAdminHeroSlides(): Promise<HeroSlideItem[]> {
  return request("/admin/hero-slides");
}

export async function uploadAdminHeroSlideImage(slotIndex: number, file: File): Promise<HeroSlideItem> {
  const formData = new FormData();
  formData.append("image", file);
  return request(`/admin/hero-slides/${slotIndex}/image`, {
    method: "POST",
    body: formData,
  });
}

export async function clearAdminHeroSlideImage(slotIndex: number): Promise<HeroSlideItem> {
  return request(`/admin/hero-slides/${slotIndex}/image`, {
    method: "DELETE",
  });
}

export async function getAdminClientUpdateConfig(): Promise<ClientUpdateConfig> {
  return request("/admin/client-update");
}

export async function updateAdminClientUpdateConfig(data: Partial<Pick<ClientUpdateConfig, "latest_version" | "download_url" | "message" | "force_update_enabled">>): Promise<ClientUpdateConfig> {
  return request("/admin/client-update", {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function setAdminClientForceUpdate(enabled: boolean): Promise<ClientUpdateConfig> {
  return request(`/admin/client-update/force?enabled=${enabled ? "true" : "false"}`, {
    method: "POST",
  });
}

export async function uploadAdminClientUpdateQrImage(file: File): Promise<ClientUpdateConfig> {
  const formData = new FormData();
  formData.append("image", file);
  return request("/admin/client-update/qr-image", {
    method: "POST",
    body: formData,
  });
}

export async function clearAdminClientUpdateQrImage(): Promise<ClientUpdateConfig> {
  return request("/admin/client-update/qr-image", {
    method: "DELETE",
  });
}
