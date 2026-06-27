import { useCallback, useEffect, useRef, useState } from "react";
import {
  DEFAULT_TASK_DEFAULTS,
  type TaskDefaults,
  type UserStatus,
} from "./types";
import { useSendCode } from "./useSendCode";

const APP_VERSION = "0.1.0";

interface DeviceInfo {
  id: number;
  user_id: number;
  machine_code_hash: string;
  status: string;
  bound_at: string | null;
  last_seen_at: string | null;
  remark: string | null;
}

interface SettingsPageProps {
  apiBase: string;
  token: string;
  email: string;
  machineCode: string;
  status: UserStatus | null;
  taskDefaults: TaskDefaults;
  onTaskDefaultsChange: (defaults: TaskDefaults) => void;
  onOpenPayment: () => void;
  onOpenSupport: () => void;
  onOpenFeedback: () => void;
  onLogout: () => void;
}

async function readErrorDetail(res: Response) {
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

function normalizeDefaults(defaults: TaskDefaults): TaskDefaults {
  return {
    dailyLimit: Math.min(200, Math.max(1, Number(defaults.dailyLimit) || DEFAULT_TASK_DEFAULTS.dailyLimit)),
    createTag: Boolean(defaults.createTag),
    greetingText: defaults.greetingText.trim(),
  };
}

function formatDate(s: string | null) {
  return s ? s.slice(0, 10) : "-";
}

function formatDeviceStatus(status: string | undefined) {
  if (!status) return "未绑定";
  if (status === "active") return "已绑定";
  if (status === "disabled") return "已停用";
  return status;
}

function SettingsPage({
  apiBase,
  token,
  email,
  machineCode,
  status,
  taskDefaults,
  onTaskDefaultsChange,
  onOpenPayment,
  onOpenSupport,
  onOpenFeedback,
  onLogout,
}: SettingsPageProps) {
  const [defaultsForm, setDefaultsForm] = useState<TaskDefaults>(taskDefaults);
  const [device, setDevice] = useState<DeviceInfo | null>(null);
  const [deviceLoading, setDeviceLoading] = useState(true);
  const [deviceError, setDeviceError] = useState("");
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetLoading, setResetLoading] = useState(false);

  const showToast = useCallback((message: string) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 2400);
  }, []);

  const { countdown, send } = useSendCode(apiBase, showToast);

  useEffect(() => () => clearTimeout(toastTimer.current), []);

  useEffect(() => {
    setDefaultsForm(taskDefaults);
  }, [taskDefaults]);

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

    return () => {
      cancelled = true;
    };
  }, [apiBase, token, onLogout]);

  const handleDefaultsSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const nextDefaults = normalizeDefaults(defaultsForm);
    setDefaultsForm(nextDefaults);
    onTaskDefaultsChange(nextDefaults);
    showToast("任务默认设置已保存");
  };

  const handleDefaultsReset = () => {
    setDefaultsForm(DEFAULT_TASK_DEFAULTS);
    onTaskDefaultsChange(DEFAULT_TASK_DEFAULTS);
    showToast("已恢复默认任务设置");
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

  return (
    <div className="settings-page">
      {toast && <div className="toast show">{toast}</div>}

      <section className="profile-card settings-hero-card">
        <div>
          <h3 className="settings-title">设置</h3>
          <p className="profile-card-desc">管理账号安全、设备信息和自动化任务默认参数</p>
        </div>
        <button type="button" className="settings-primary-btn" onClick={onOpenPayment}>
          充值会员
        </button>
      </section>

      <div className="settings-grid">
        <section className="profile-card settings-card">
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
        </section>

        <section className="profile-card settings-card">
          <h4 className="profile-card-title">快捷入口</h4>
          <p className="profile-card-desc">发布版先保留最常用的服务入口</p>
          <div className="settings-action-stack">
            <button type="button" className="settings-link-btn" onClick={onOpenSupport}>
              联系客服
            </button>
            <button type="button" className="settings-link-btn" onClick={onOpenFeedback}>
              提交反馈
            </button>
            <button type="button" className="settings-danger-btn" onClick={onLogout}>
              退出登录
            </button>
          </div>
        </section>
      </div>

      <section className="profile-card settings-card">
        <h4 className="profile-card-title">任务默认设置</h4>
        <p className="profile-card-desc">保存后会同步到未运行的任务卡</p>
        <form className="settings-form" onSubmit={handleDefaultsSubmit}>
          <div className="settings-form-grid">
            <div className="field">
              <label>每日限额</label>
              <input
                className="input"
                type="number"
                min={1}
                max={200}
                value={defaultsForm.dailyLimit}
                onChange={(e) => setDefaultsForm((prev) => ({ ...prev, dailyLimit: Number(e.target.value) }))}
              />
            </div>
            <label className="settings-check-row">
              <input
                type="checkbox"
                checked={defaultsForm.createTag}
                onChange={(e) => setDefaultsForm((prev) => ({ ...prev, createTag: e.target.checked }))}
              />
              创建标签
            </label>
          </div>
          <div className="field">
            <label>打招呼语（可选）</label>
            <textarea
              className="input settings-textarea"
              rows={3}
              placeholder="你好，我是..."
              value={defaultsForm.greetingText}
              onChange={(e) => setDefaultsForm((prev) => ({ ...prev, greetingText: e.target.value }))}
            />
          </div>
          <div className="settings-form-actions">
            <button type="button" className="settings-secondary-btn" onClick={handleDefaultsReset}>
              清除本地设置
            </button>
            <button type="submit" className="settings-primary-btn">
              保存设置
            </button>
          </div>
        </form>
      </section>

      <section className="profile-card settings-card">
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
      </section>
    </div>
  );
}

export default SettingsPage;
