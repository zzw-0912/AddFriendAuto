export const API_BASE = import.meta.env.VITE_API_BASE || "";

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

async function request(path: string, options: RequestInit = {}) {
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
  return res.json();
}

export async function login(username: string, password: string) {
  const res = await fetch(`${API_BASE}/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `登录失败 (${res.status})`);
  }
  const data = await res.json();
  setToken(data.access_token);
  return data;
}

export async function getUsers(page = 1, pageSize = 20) {
  return request(`/admin/users?page=${page}&page_size=${pageSize}`);
}

export async function getUserDetail(userId: number) {
  return request(`/admin/users/${userId}`);
}

export async function updateMembership(userId: number, action: string, days?: number) {
  return request(`/admin/users/${userId}/membership`, {
    method: "PATCH",
    body: JSON.stringify({ action, days }),
  });
}

export async function getDevices(page = 1, pageSize = 20) {
  return request(`/admin/devices?page=${page}&page_size=${pageSize}`);
}

export async function updateDevice(deviceId: number, data: { status?: string; remark?: string; unbind?: boolean }) {
  return request(`/admin/devices/${deviceId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function rebindDevice(deviceId: number, newUserId: number) {
  return request(`/admin/devices/${deviceId}/rebind?new_user_id=${newUserId}`, {
    method: "POST",
  });
}

export async function getPlans() {
  return request("/admin/plans");
}

export async function updatePlan(planId: number, data: Record<string, unknown>) {
  return request(`/admin/plans/${planId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function getOrders(page = 1, pageSize = 20, status?: string) {
  let path = `/admin/orders?page=${page}&page_size=${pageSize}`;
  if (status) path += `&status=${status}`;
  return request(path);
}

export async function confirmOrderPayment(orderId: number, data: { channel?: string; remark?: string } = {}) {
  return request(`/admin/orders/${orderId}/confirm-payment`, {
    method: "POST",
    body: JSON.stringify({ channel: "manual_wechat", ...data }),
  });
}

export async function getTasks(page = 1, pageSize = 20, status?: string) {
  let path = `/admin/tasks?page=${page}&page_size=${pageSize}`;
  if (status) path += `&status=${status}`;
  return request(path);
}

export async function getTaskResults(taskId: number) {
  return request(`/admin/tasks/${taskId}/results`);
}

export async function getAuditLogs(page = 1, pageSize = 20) {
  return request(`/admin/audit-logs?page=${page}&page_size=${pageSize}`);
}

export async function getContacts(page = 1, pageSize = 20, q?: string) {
  let path = `/admin/contacts?page=${page}&page_size=${pageSize}`;
  if (q) path += `&q=${encodeURIComponent(q)}`;
  return request(path);
}

export async function getFeedback(page = 1, pageSize = 20) {
  return request(`/admin/feedback?page=${page}&page_size=${pageSize}`);
}
