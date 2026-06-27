export class NetworkError extends Error {
  constructor(message?: string) {
    super(message || "无法连接服务器，请确认后端服务已启动");
    this.name = "NetworkError";
  }
}

export class AuthError extends Error {
  constructor(message?: string) {
    super(message || "登录已失效，请重新登录");
    this.name = "AuthError";
  }
}

export async function readErrorDetail(res: Response): Promise<string> {
  const text = await res.text().catch(() => "");
  if (!text) return "";
  try {
    const data = JSON.parse(text) as { detail?: unknown; message?: unknown };
    if (typeof data.detail === "string") return data.detail;
    if (typeof data.message === "string") return data.message;
    if (data.detail) return JSON.stringify(data.detail);
  } catch {}
  return text;
}

export async function apiGet<T>(apiBase: string, path: string, token?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${apiBase}${path}`, { headers });
  } catch {
    throw new NetworkError();
  }

  if (res.status === 401 || res.status === 403) throw new AuthError();
  if (!res.ok) throw new Error((await readErrorDetail(res)) || `请求失败(${res.status})`);

  return res.json() as Promise<T>;
}

export async function apiPost<T>(apiBase: string, path: string, body?: unknown, token?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${apiBase}${path}`, {
      method: "POST",
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new NetworkError();
  }

  if (res.status === 401 || res.status === 403) throw new AuthError();
  if (!res.ok) throw new Error((await readErrorDetail(res)) || `请求失败(${res.status})`);

  return res.json() as Promise<T>;
}
