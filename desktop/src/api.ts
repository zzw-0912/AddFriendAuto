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

export interface ClientUpdateRequiredPayload {
  code?: string;
  detail?: string;
  latest_version?: string;
  force_update_enabled?: boolean;
  download_url?: string | null;
  qr_image_url?: string | null;
  message?: string | null;
  updated_at?: string | null;
}

export class ClientUpdateRequiredError extends Error {
  payload: ClientUpdateRequiredPayload;

  constructor(payload: ClientUpdateRequiredPayload) {
    super(payload.message || payload.detail || "当前软件版本已停用，请下载最新版本后继续使用。");
    this.name = "ClientUpdateRequiredError";
    this.payload = payload;
  }
}

type ClientUpdateRequiredHandler = (payload: ClientUpdateRequiredPayload) => void;

const CLIENT_VERSION_HEADER = "X-Client-Version";
export const FALLBACK_CLIENT_VERSION = import.meta.env.VITE_APP_VERSION || "0.1.0";

let originalFetch: typeof window.fetch | null = null;
let activeApiBase = "";
let activeClientVersion = FALLBACK_CLIENT_VERSION;
let activeUpdateHandler: ClientUpdateRequiredHandler | null = null;

export function installClientUpdateInterceptor(
  apiBase: string,
  clientVersion: string,
  onUpdateRequired: ClientUpdateRequiredHandler,
) {
  activeApiBase = apiBase.replace(/\/$/, "");
  activeClientVersion = (clientVersion || FALLBACK_CLIENT_VERSION).trim() || FALLBACK_CLIENT_VERSION;
  activeUpdateHandler = onUpdateRequired;

  if (originalFetch) return;

  originalFetch = window.fetch.bind(window);
  window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const shouldAttachVersion = isBackendRequest(input, activeApiBase);
    const nextInit = shouldAttachVersion ? withClientVersionHeader(input, init, activeClientVersion) : init;
    const response = await originalFetch!(input, nextInit);

    if (shouldAttachVersion && response.status === 426) {
      const payload = await notifyClientUpdateRequired(response);
      throw new ClientUpdateRequiredError(payload);
    }

    return response;
  };
}

function withClientVersionHeader(input: RequestInfo | URL, init: RequestInit | undefined, clientVersion: string): RequestInit {
  const headers = new Headers(input instanceof Request ? input.headers : undefined);
  new Headers(init?.headers).forEach((value, key) => headers.set(key, value));
  headers.set(CLIENT_VERSION_HEADER, clientVersion);
  return { ...init, headers };
}

function isBackendRequest(input: RequestInfo | URL, apiBase: string): boolean {
  if (!apiBase) return false;
  const inputUrl = getAbsoluteUrl(input);
  if (!inputUrl) return false;

  try {
    const target = new URL(inputUrl);
    const base = new URL(apiBase, window.location.href);
    const basePath = base.pathname.replace(/\/$/, "");
    return target.origin === base.origin && (!basePath || target.pathname === basePath || target.pathname.startsWith(`${basePath}/`));
  } catch {
    return false;
  }
}

function getAbsoluteUrl(input: RequestInfo | URL): string | null {
  if (typeof input === "string") return new URL(input, window.location.href).toString();
  if (input instanceof URL) return input.toString();
  if (input instanceof Request) return new URL(input.url, window.location.href).toString();
  return null;
}

function fallbackUpdatePayload(): ClientUpdateRequiredPayload {
  return {
    code: "CLIENT_UPDATE_REQUIRED",
    detail: "当前软件版本已停用，请下载最新版本后继续使用。",
  };
}

function normalizeUpdatePayload(data: unknown): ClientUpdateRequiredPayload {
  if (!data || typeof data !== "object") return fallbackUpdatePayload();
  const payload = data as ClientUpdateRequiredPayload;
  return {
    ...payload,
    code: payload.code || "CLIENT_UPDATE_REQUIRED",
    detail: payload.detail || payload.message || "当前软件版本已停用，请下载最新版本后继续使用。",
  };
}

async function readClientUpdatePayload(response: Response): Promise<ClientUpdateRequiredPayload> {
  try {
    return normalizeUpdatePayload(await response.clone().json());
  } catch {
    return fallbackUpdatePayload();
  }
}

async function notifyClientUpdateRequired(response: Response): Promise<ClientUpdateRequiredPayload> {
  const payload = await readClientUpdatePayload(response);
  activeUpdateHandler?.(payload);
  return payload;
}

export function isClientUpdateRequiredError(error: unknown): error is ClientUpdateRequiredError {
  return error instanceof ClientUpdateRequiredError
    || (!!error && typeof error === "object" && (error as Error).name === "ClientUpdateRequiredError");
}

export function isClientUpdateRequired(payload: ClientUpdateRequiredPayload, clientVersion: string): boolean {
  if (!payload.force_update_enabled) return false;
  return (clientVersion || "").trim() !== (payload.latest_version || "").trim();
}

export async function checkClientUpdateRequired(apiBase: string, clientVersion: string): Promise<ClientUpdateRequiredPayload | null> {
  const version = (clientVersion || FALLBACK_CLIENT_VERSION).trim() || FALLBACK_CLIENT_VERSION;
  const fetchImpl = originalFetch ?? window.fetch.bind(window);
  const res = await fetchImpl(`${apiBase.replace(/\/$/, "")}/client-update/config`, {
    headers: {
      [CLIENT_VERSION_HEADER]: version,
      "Cache-Control": "no-cache",
    },
    cache: "no-store",
  });
  if (!res.ok) return null;

  const payload = normalizeUpdatePayload(await res.json());
  if (!isClientUpdateRequired(payload, version)) return null;

  activeUpdateHandler?.(payload);
  return payload;
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
  } catch (error) {
    if (isClientUpdateRequiredError(error)) throw error;
    throw new NetworkError();
  }

  if (res.status === 426) throw new ClientUpdateRequiredError(await readClientUpdatePayload(res));
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
  } catch (error) {
    if (isClientUpdateRequiredError(error)) throw error;
    throw new NetworkError();
  }

  if (res.status === 426) throw new ClientUpdateRequiredError(await readClientUpdatePayload(res));
  if (res.status === 401 || res.status === 403) throw new AuthError();
  if (!res.ok) throw new Error((await readErrorDetail(res)) || `请求失败(${res.status})`);

  return res.json() as Promise<T>;
}

const ACCOUNTS_KEY = "friendauto.accounts";

export interface StoredAccount {
  email: string;
  token: string;
}

export function getSavedAccounts(): StoredAccount[] {
  try {
    return JSON.parse(localStorage.getItem(ACCOUNTS_KEY) || "[]");
  } catch {
    return [];
  }
}

export function saveAccount(email: string, token: string) {
  const accounts = getSavedAccounts().filter((a) => a.email !== email);
  accounts.unshift({ email, token });
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts.slice(0, 5)));
}

export function removeAccount(email: string) {
  const accounts = getSavedAccounts().filter((a) => a.email !== email);
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}
