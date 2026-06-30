import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { readErrorDetail, getSavedAccounts, saveAccount, removeAccount } from "./api";
import type { StoredAccount } from "./api";
import { loadWeChatBindings, saveWeChatBindings } from "./localSettings";
import { useSendCode } from "./useSendCode";
import type { UserStatus, WeChatWindowBinding, WeChatWindowInfo } from "./types";

interface Props {
  apiBase: string;
  token: string;
  email: string;
  machineCode: string;
  status: UserStatus | null;
  onAuthExpired: () => void;
  onLogout: () => void;
  onSwitchAccount: (token: string, email: string) => void;
}

interface Profile {
  user_id: number;
  email: string;
  status: string;
  created_at: string;
  last_login_at: string | null;
  membership: {
    is_active: boolean;
    plan_id: number | null;
    starts_at: string | null;
    ends_at: string | null;
  };
  trial: { total: number; used: number; remaining: number };
  success_count: number;
  failed_count: number;
  invalid_count: number;
  referral_code: string | null;
}

interface DeviceInfo {
  id: number;
  user_id: number;
  machine_code_hash: string;
  status: string;
  bound_at: string | null;
  last_seen_at: string | null;
  remark: string | null;
}

interface LoadError {
  message: string;
  canRetry: boolean;
}

const APP_VERSION = "0.1.0";

function formatDate(s: string | null) {
  return s ? s.slice(0, 10) : "-";
}

function formatDeviceStatus(status: string | undefined) {
  if (!status) return "未绑定";
  if (status === "active") return "已绑定";
  if (status === "disabled") return "已停用";
  return status;
}

function ProfilePage({
  apiBase,
  token,
  email,
  machineCode,
  status,
  onAuthExpired,
  onLogout,
  onSwitchAccount,
}: Props) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<LoadError | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [deviceLoading, setDeviceLoading] = useState(true);
  const [deviceError, setDeviceError] = useState("");

  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetLoading, setResetLoading] = useState(false);
  const [showAccountSwitcher, setShowAccountSwitcher] = useState(false);
  const [savedAccounts, setSavedAccounts] = useState<StoredAccount[]>([]);
  const [wechatWindows, setWeChatWindows] = useState<WeChatWindowInfo[]>([]);
  const [wechatBindings, setWeChatBindings] = useState<Record<string, WeChatWindowBinding>>(() => loadWeChatBindings());
  const [wechatSelections, setWeChatSelections] = useState<Record<string, string>>({});
  const [wechatLoading, setWeChatLoading] = useState(false);

  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);
  const showToast = useCallback((message: string) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 2400);
  }, []);

  const { countdown, send } = useSendCode(apiBase, showToast);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  const refreshWeChatWindows = useCallback(async () => {
    setWeChatLoading(true);
    try {
      const windows = await invoke<WeChatWindowInfo[]>("list_wechat_windows");
      setWeChatWindows(windows);
      if (windows.length === 0) {
        showToast("未找到已打开的微信窗口");
      }
    } catch (err) {
      showToast(String(err || "微信窗口刷新失败"));
    } finally {
      setWeChatLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    refreshWeChatWindows();
  }, [refreshWeChatWindows]);

  const handleBindWeChat = (slotId: number) => {
    const selection = wechatSelections[String(slotId)];
    const selectedWindow = wechatWindows.find((window) => `${window.pid}:${window.hwnd}` === selection);
    if (!selectedWindow) {
      showToast(`请先选择微信${slotId}窗口`);
      return;
    }

    const nextBindings = {
      ...wechatBindings,
      [String(slotId)]: {
        slotId,
        hwnd: selectedWindow.hwnd,
        pid: selectedWindow.pid,
        title: selectedWindow.title,
        displayName: selectedWindow.displayName,
        boundAt: new Date().toISOString(),
      },
    };
    setWeChatBindings(nextBindings);
    saveWeChatBindings(nextBindings);
    showToast(`微信${slotId}已绑定`);
  };

  const handleClearWeChatBinding = (slotId: number) => {
    const nextBindings = { ...wechatBindings };
    delete nextBindings[String(slotId)];
    setWeChatBindings(nextBindings);
    saveWeChatBindings(nextBindings);
    showToast(`微信${slotId}绑定已清除`);
  };

  const loadProfile = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/me/profile`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.status === 401 || res.status === 403) {
        setProfile(null);
        setError({ message: "登录已失效，请重新登录", canRetry: false });
        window.setTimeout(onAuthExpired, 800);
        return;
      }

      if (!res.ok) {
        const detail = await readErrorDetail(res);
        const message =
          res.status === 404
            ? "个人资料接口未加载，请重启后端服务"
            : res.status >= 500
              ? `服务器异常(${res.status})${detail ? `：${detail}` : ""}`
              : `个人资料加载失败(${res.status})${detail ? `：${detail}` : ""}`;
        setProfile(null);
        setError({ message, canRetry: true });
        return;
      }

      setProfile(await res.json());
    } catch {
      setProfile(null);
      setError({ message: "无法连接服务器，请确认后端服务已启动", canRetry: true });
    } finally {
      setLoading(false);
    }
  }, [apiBase, token, onAuthExpired]);

  useEffect(() => {
    loadProfile();
  }, [loadProfile]);

  useEffect(() => {
    let cancelled = false;
    setDeviceLoading(true);
    setDeviceError("");

    (async () => {
      try {
        const res = await fetch(`${apiBase}/devices/current`, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (cancelled) return;
        if (res.status === 401 || res.status === 403) {
          onLogout();
          return;
        }
        if (!res.ok) {
          setDevice(null);
          setDeviceError("设备信息读取失败");
          return;
        }
        setDevice(await res.json());
      } catch {
        if (!cancelled) {
          setDevice(null);
          setDeviceError("无法连接服务器");
        }
      } finally {
        if (!cancelled) setDeviceLoading(false);
      }
    })();

    return () => { cancelled = true; };
  }, [apiBase, token, onLogout]);

  const handleCopyReferral = async () => {
    if (!profile?.referral_code) return;
    try {
      await navigator.clipboard.writeText(profile.referral_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const handleCopyMachineCode = async () => {
    try {
      await navigator.clipboard.writeText(machineCode);
      showToast("设备码已复制");
    } catch {
      showToast("复制失败，请手动复制设备码");
    }
  };

  const handlePasswordReset = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length < 6) {
      showToast("请输入 6 位验证码");
      return;
    }
    if (newPassword.length < 6) {
      showToast("密码至少 6 位字符");
      return;
    }
    if (newPassword !== confirmPassword) {
      showToast("两次输入的密码不一致");
      return;
    }

    setResetLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code, new_password: newPassword }),
      });

      if (!res.ok) {
        const detail = await readErrorDetail(res);
        showToast(detail || "重置失败");
        return;
      }

      setCode("");
      setNewPassword("");
      setConfirmPassword("");
      showToast("密码已修改，请使用新密码重新登录");
      setTimeout(onLogout, 1200);
    } catch {
      showToast("无法连接服务器");
    } finally {
      setResetLoading(false);
    }
  };

  const membershipText = status?.membership.is_active
    ? `会员有效至 ${formatDate(status.membership.ends_at)}`
    : `试用剩余 ${status?.trial.remaining ?? 0} 次`;

  if (loading && !profile) {
    return <div className="profile-loading">加载中...</div>;
  }

  if (error && !profile) {
    return (
      <div className="profile-loading profile-error">
        <div>{error?.message || "个人资料加载失败"}</div>
        {error?.canRetry && (
          <button type="button" className="profile-retry-btn" onClick={loadProfile}>
            重试
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="profile-page">
      {toast && <div className="toast show">{toast}</div>}

      {/* User Info Card */}
      <div className="profile-card">
        <div className="profile-card-header">
          <div className="profile-avatar">{email.charAt(0).toUpperCase() || "U"}</div>
          <div className="profile-title">
            <h3>{email}</h3>
            <span className={`profile-status ${profile?.membership.is_active ? "member" : "trial"}`}>
              {profile?.membership.is_active ? "已开通会员" : "试用用户"}
            </span>
          </div>
        </div>
        <div className="profile-info-grid">
          <div className="profile-info-item">
            <span className="profile-label">注册时间</span>
            <span className="profile-value">{formatDate(profile?.created_at ?? null)}</span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">最后登录</span>
            <span className="profile-value">{formatDate(profile?.last_login_at ?? null)}</span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">会员有效期</span>
            <span className="profile-value">
              {profile?.membership.is_active
                ? `至 ${formatDate(profile.membership.ends_at)}`
                : "未开通"}
            </span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">剩余试用</span>
            <span className="profile-value">{profile?.trial.remaining ?? 0} 次</span>
          </div>
        </div>
      </div>

      {/* Statistics Card */}
      <div className="profile-card">
        <h4 className="profile-card-title">累计数据</h4>
        <div className="profile-stats">
          <div className="profile-stat stat-success">
            <div className="stat-number">{(profile?.success_count ?? 0).toLocaleString()}</div>
            <div className="stat-label">加人成功</div>
          </div>
          <div className="profile-stat stat-failed">
            <div className="stat-number">{(profile?.failed_count ?? 0).toLocaleString()}</div>
            <div className="stat-label">失败</div>
          </div>
          <div className="profile-stat stat-invalid">
            <div className="stat-number">{(profile?.invalid_count ?? 0).toLocaleString()}</div>
            <div className="stat-label">无效</div>
          </div>
        </div>
      </div>

      {/* Referral Code Card */}
      <div className="profile-card">
        <h4 className="profile-card-title">推荐码</h4>
        <p className="profile-card-desc">分享推荐码给好友，邀请他们下载使用</p>
        <div className="profile-referral">
          <div className="referral-code-box">
            <div className="referral-qr-frame">
              <img src="/qr-wechat.png" alt="推荐二维码" />
            </div>
            <div className="referral-code-content">
              <span className="referral-code">{profile?.referral_code || "-"}</span>
              {profile?.referral_code && (
                <button type="button" className="referral-copy-btn" onClick={handleCopyReferral}>
                  {copied ? "已复制" : "复制"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Device Info Card */}
      <div className="profile-card settings-card">
        <h4 className="profile-card-title">账号与设备</h4>
        <div className="settings-info-list">
          <div className="settings-info-row">
            <span className="profile-label">登录邮箱</span>
            <span className="profile-value settings-break-text">{email}</span>
          </div>
          <div className="settings-info-row">
            <span className="profile-label">账户状态</span>
            <span className={`profile-status ${status?.membership.is_active ? "member" : "trial"}`}>
              {membershipText}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="profile-label">设备绑定</span>
            <span className="profile-value">
              {deviceLoading ? "读取中..." : deviceError ? "未读取到绑定信息" : formatDeviceStatus(device?.status)}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="profile-label">绑定时间</span>
            <span className="profile-value">{device ? formatDate(device.bound_at) : "-"}</span>
          </div>
          <div className="settings-info-row">
            <span className="profile-label">最后在线</span>
            <span className="profile-value">{device ? formatDate(device.last_seen_at) : "-"}</span>
          </div>
          <div className="settings-info-row">
            <span className="profile-label">应用版本</span>
            <span className="profile-value">v{APP_VERSION}</span>
          </div>
        </div>
        <div className="settings-machine-box">
          <div>
            <div className="profile-label">本机设备码</div>
            <div className="settings-machine-code">{machineCode}</div>
          </div>
          <button type="button" className="settings-secondary-btn" onClick={handleCopyMachineCode}>
            复制
          </button>
        </div>
        <div className="settings-machine-box" style={{ marginTop: 12 }}>
          <button
            type="button"
            className="settings-danger-btn"
            style={{ width: "100%", textAlign: "center" }}
            onClick={() => { setSavedAccounts(getSavedAccounts()); setShowAccountSwitcher(true); }}
          >
            切换账号
          </button>
        </div>
      </div>

      {/* WeChat Binding Card */}
      <div className="profile-card settings-card">
        <div className="profile-card-header compact">
          <div>
            <h4 className="profile-card-title">微信窗口绑定</h4>
            <p className="profile-card-desc">每个任务配置固定使用对应微信窗口</p>
          </div>
          <button type="button" className="settings-secondary-btn" onClick={refreshWeChatWindows} disabled={wechatLoading}>
            {wechatLoading ? "刷新中..." : "刷新窗口"}
          </button>
        </div>

        <div className="wechat-bind-list">
          {[1, 2, 3].map((slotId) => {
            const binding = wechatBindings[String(slotId)];
            return (
              <div className="wechat-bind-row" key={slotId}>
                <div className="wechat-bind-meta">
                  <strong>微信{slotId}</strong>
                  <span>{binding ? binding.displayName : "未绑定"}</span>
                  {binding && <small>绑定时间 {formatDate(binding.boundAt)}</small>}
                </div>
                <select
                  className="input wechat-bind-select"
                  value={wechatSelections[String(slotId)] || ""}
                  onChange={(e) => setWeChatSelections((prev) => ({ ...prev, [String(slotId)]: e.target.value }))}
                >
                  <option value="">选择已打开的微信窗口</option>
                  {wechatWindows.map((window) => (
                    <option key={`${window.pid}:${window.hwnd}`} value={`${window.pid}:${window.hwnd}`}>
                      {window.displayName}
                    </option>
                  ))}
                </select>
                <div className="wechat-bind-actions">
                  <button type="button" className="settings-primary-btn" onClick={() => handleBindWeChat(slotId)}>
                    绑定
                  </button>
                  <button type="button" className="settings-secondary-btn" onClick={() => handleClearWeChatBinding(slotId)} disabled={!binding}>
                    清除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Password Reset Card */}
      <div className="profile-card settings-card">
        <h4 className="profile-card-title">修改密码</h4>
        <p className="profile-card-desc">通过当前登录邮箱验证后修改密码</p>
        <form className="settings-form" onSubmit={handlePasswordReset}>
          <div className="field">
            <label>邮箱地址</label>
            <input className="input" type="email" value={email} disabled />
          </div>
          <div className="code-row settings-code-row">
            <div className="field">
              <label>验证码</label>
              <input
                className="input"
                type="text"
                placeholder="6 位验证码"
                maxLength={6}
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))}
                inputMode="numeric"
                autoComplete="off"
              />
            </div>
            <button type="button" className="btn-send" disabled={countdown > 0} onClick={() => send(email)}>
              {countdown > 0 ? `${countdown}s 后重发` : "发送验证码"}
            </button>
          </div>
          <div className="settings-form-grid">
            <div className="field">
              <label>新密码</label>
              <input
                className="input"
                type="password"
                placeholder="至少 6 位字符"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="field">
              <label>确认密码</label>
              <input
                className="input"
                type="password"
                placeholder="再次输入密码"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
            </div>
          </div>
          <div className="settings-form-actions">
            <button type="submit" className="settings-primary-btn" disabled={resetLoading}>
              {resetLoading ? "修改中..." : "修改密码"}
            </button>
          </div>
        </form>
      </div>

      {showAccountSwitcher && (
        <div className="modal-overlay" onClick={() => setShowAccountSwitcher(false)}>
          <div className="account-switcher" onClick={(e) => e.stopPropagation()}>
            <div className="account-switcher-header">
              <h3>切换账号</h3>
              <button className="account-switcher-close" onClick={() => setShowAccountSwitcher(false)}>✕</button>
            </div>
            <div className="account-switcher-body">
              <div className="account-switcher-current">
                <div className="account-switcher-avatar">{email.charAt(0).toUpperCase()}</div>
                <div className="account-switcher-info">
                  <span className="account-switcher-email">{email}</span>
                  <span className="account-switcher-tag">当前账号</span>
                </div>
              </div>
              {savedAccounts.filter((a) => a.email !== email).length > 0 && (
                <>
                  <div className="account-switcher-divider" />
                  <div className="account-switcher-label">其他账号</div>
                  <div className="account-switcher-list">
                    {savedAccounts.filter((a) => a.email !== email).map((account) => (
                      <div
                        key={account.email}
                        className="account-switcher-item"
                        onClick={() => { onSwitchAccount(account.token, account.email); setShowAccountSwitcher(false); }}
                      >
                        <div className="account-switcher-avatar">{account.email.charAt(0).toUpperCase()}</div>
                        <span className="account-switcher-email">{account.email}</span>
                        <button
                          className="account-switcher-remove"
                          onClick={(e) => { e.stopPropagation(); removeAccount(account.email); setSavedAccounts(getSavedAccounts()); }}
                        >
                          移除
                        </button>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
            <div className="account-switcher-footer">
              <button
                className="settings-primary-btn"
                style={{ flex: 1 }}
                onClick={() => { saveAccount(email, token); onLogout(); }}
              >
                添加新账号
              </button>
              <button
                className="settings-danger-btn"
                style={{ flex: 1 }}
                onClick={() => { removeAccount(email); onLogout(); }}
              >
                退出当前账号
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProfilePage;
