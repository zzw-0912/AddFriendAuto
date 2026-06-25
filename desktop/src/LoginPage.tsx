import { useState, useEffect, useCallback, useRef } from "react";

interface Props {
  apiBase: string;
  machineCode: string;
  onLogin: (token: string, email: string) => void;
}

type Tab = "login" | "register" | "reset";

export default function LoginPage({ apiBase, machineCode, onLogin }: Props) {
  const [tab, setTab] = useState<Tab>("login");
  const [toast, setToast] = useState("");
  const toastTimer = useRef<ReturnType<typeof setTimeout>>();

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(""), 2400);
  }, []);

  return (
    <>
      {toast && (
        <div style={{
          position: "fixed", top: 24, left: "50%", transform: "translateX(-50%)",
          padding: "10px 20px", background: "#101828", color: "#fff",
          borderRadius: 10, fontSize: 14, zIndex: 100,
          transition: "opacity 0.24s cubic-bezier(0.2,0,0,1)",
        }}>{toast}</div>
      )}
      <div className="app-window">
        <TitleBar />
        <div className="app-body">
          <BrandPanel />
          <AuthPanel tab={tab} onTabChange={setTab} apiBase={apiBase} machineCode={machineCode} onLogin={onLogin} showToast={showToast} />
        </div>
      </div>
    </>
  );
}

function TitleBar() {
  return (
    <div className="titlebar">
      <div className="titlebar-left">
        <div className="titlebar-logo">F</div>
        <span className="titlebar-title">FriendAuto</span>
      </div>
      <div className="titlebar-controls">
        <button className="win-btn" aria-label="最小化">
          <svg viewBox="0 0 12 12"><rect x="1" y="5.5" width="10" height="1" fill="currentColor" /></svg>
        </button>
        <button className="win-btn" aria-label="最大化">
          <svg viewBox="0 0 12 12"><rect x="1.5" y="1.5" width="9" height="9" rx="0.5" fill="none" stroke="currentColor" strokeWidth="1" /></svg>
        </button>
        <button className="win-btn close" aria-label="关闭">
          <svg viewBox="0 0 12 12"><path d="M1 1l10 10M11 1L1 11" stroke="currentColor" strokeWidth="1.2" fill="none" /></svg>
        </button>
      </div>
    </div>
  );
}

function BrandPanel() {
  return (
    <div className="brand-panel">
      <div className="brand-content">
        <div className="brand-icon">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
            <circle cx="12" cy="8" r="4" />
            <path d="M6 20v-2a6 6 0 0 1 10.5-3.3" />
            <path d="M18 20v-2a3 3 0 0 0-1.5-2.6" />
            <path d="M20 14h2v6h-6v-2h3l-2.5-3" />
          </svg>
        </div>
        <div className="brand-name">FriendAuto</div>
        <p className="brand-tagline">智能微信好友管理，让每一次连接都简单高效</p>
        <div className="brand-features">
          <div className="brand-feat"><span className="feat-dot" />每日自动添加好友任务</div>
          <div className="brand-feat"><span className="feat-dot" />智能标签分组管理</div>
          <div className="brand-feat"><span className="feat-dot" />自定义打招呼语</div>
          <div className="brand-feat"><span className="feat-dot" />实时任务进度追踪</div>
        </div>
      </div>
    </div>
  );
}

function AuthPanel({ tab, onTabChange, apiBase, machineCode, onLogin, showToast }: {
  tab: Tab; onTabChange: (t: Tab) => void;
  apiBase: string; machineCode: string;
  onLogin: (token: string, email: string) => void;
  showToast: (msg: string) => void;
}) {
  return (
    <div className="auth-panel">
      <nav className="auth-tabs">
        {(["login", "register", "reset"] as const).map((t) => (
          <button key={t} className={`auth-tab${tab === t ? " active" : ""}`} onClick={() => onTabChange(t)}>
            {t === "login" ? "登录" : t === "register" ? "注册" : "找回密码"}
          </button>
        ))}
      </nav>

      {tab === "login" && <LoginForm apiBase={apiBase} machineCode={machineCode} onLogin={onLogin} showToast={showToast} onGotoRegister={() => onTabChange("register")} />}
      {tab === "register" && <RegisterForm apiBase={apiBase} machineCode={machineCode} onLogin={onLogin} showToast={showToast} onGotoLogin={() => onTabChange("login")} />}
      {tab === "reset" && <ResetForm apiBase={apiBase} machineCode={machineCode} showToast={showToast} onGotoLogin={() => onTabChange("login")} />}
    </div>
  );
}

function useSendCode(apiBase: string, showToast: (m: string) => void) {
  const [countdown, setCountdown] = useState(0);
  const timer = useRef<ReturnType<typeof setInterval>>();

  const send = useCallback(async (email: string) => {
    if (!email) { showToast("请先输入邮箱地址"); return; }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { showToast("请输入有效的邮箱地址"); return; }

    setCountdown(60);
    try {
      const res = await fetch(`${apiBase}/auth/send-code`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "发送失败"); setCountdown(0); return; }
      if (data.dev_code) showToast(`验证码: ${data.dev_code}`);
      else showToast("验证码已发送");
    } catch {
      showToast("无法连接服务器");
      setCountdown(0);
      return;
    }

    clearInterval(timer.current);
    timer.current = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) { clearInterval(timer.current); return 0; }
        return prev - 1;
      });
    }, 1000);
  }, [apiBase, showToast]);

  useEffect(() => () => clearInterval(timer.current), []);

  return { countdown, send };
}

function LoginForm({ apiBase, machineCode, onLogin, showToast, onGotoRegister }: {
  apiBase: string; machineCode: string;
  onLogin: (t: string, e: string) => void;
  showToast: (m: string) => void;
  onGotoRegister: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { showToast("请输入邮箱地址"); return; }
    if (!password) { showToast("请输入密码"); return; }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/login`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, machine_code: machineCode }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "登录失败"); return; }
      onLogin(data.access_token, email);
      showToast(remember ? "登录成功，下次将自动登录" : "登录成功");
    } catch {
      showToast("无法连接服务器");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="auth-form visible" onSubmit={handleSubmit} autoComplete="off">
      <h2>欢迎回来</h2>
      <p className="form-sub">输入邮箱和密码登录</p>

      <div className="field">
        <label>邮箱地址</label>
        <input className="input" type="email" placeholder="your@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>

      <div className="field">
        <label>密码</label>
        <input className="input" type="password" placeholder="输入密码" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </div>

      <div className="check-row">
        <input type="checkbox" id="login-remember" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
        <label htmlFor="login-remember">记住我，下次自动登录</label>
      </div>

      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? <><span className="spinner" /> 登录中…</> : "登 录"}
      </button>
      <p className="form-footer">还没有账号？<a href="#" onClick={(e) => { e.preventDefault(); onGotoRegister(); }}>立即注册</a></p>
    </form>
  );
}

function RegisterForm({ apiBase, machineCode, onLogin, showToast, onGotoLogin }: {
  apiBase: string; machineCode: string;
  onLogin: (t: string, e: string) => void;
  showToast: (m: string) => void;
  onGotoLogin: () => void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [code, setCode] = useState("");
  const [agree, setAgree] = useState(false);
  const [loading, setLoading] = useState(false);
  const { countdown, send } = useSendCode(apiBase, showToast);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { showToast("请输入邮箱地址"); return; }
    if (!password || password.length < 6) { showToast("密码至少 6 位字符"); return; }
    if (password !== confirm) { showToast("两次输入的密码不一致"); return; }
    if (code.length < 6) { showToast("请输入 6 位验证码"); return; }
    if (!agree) { showToast("请先阅读并同意用户协议和隐私政策"); return; }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/register`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, code, machine_code: machineCode }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "注册失败"); return; }
      onLogin(data.access_token, email);
      showToast("注册成功，即将自动登录");
    } catch {
      showToast("无法连接服务器");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="auth-form visible" onSubmit={handleSubmit} autoComplete="off">
      <h2>创建账号</h2>
      <p className="form-sub">使用邮箱注册，设置密码后即可开始使用</p>

      <div className="field">
        <label>邮箱地址</label>
        <input className="input" type="email" placeholder="your@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>

      <div className="field">
        <label>设置密码</label>
        <input className="input" type="password" placeholder="至少 6 位字符" value={password} onChange={(e) => setPassword(e.target.value)} required />
      </div>

      <div className="field">
        <label>确认密码</label>
        <input className="input" type="password" placeholder="再次输入密码" value={confirm} onChange={(e) => setConfirm(e.target.value)} required />
      </div>

      <div className="code-row">
        <div className="field">
          <label>验证码</label>
          <input className="input" type="text" placeholder="6 位验证码" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric" autoComplete="off" />
        </div>
        <button type="button" className="btn-send" style={{ marginTop: 26 }} disabled={countdown > 0} onClick={() => send(email)}>
          {countdown > 0 ? `${countdown}s 后重发` : "发送验证码"}
        </button>
      </div>

      <div className="check-row">
        <input type="checkbox" id="register-agree" checked={agree} onChange={(e) => setAgree(e.target.checked)} />
        <label htmlFor="register-agree">我已阅读并同意</label>
        <a href="#">《用户协议》</a><span>和</span><a href="#">《隐私政策》</a>
      </div>

      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? <><span className="spinner" /> 注册中…</> : "注 册"}
      </button>
      <p className="form-footer">已有账号？<a href="#" onClick={(e) => { e.preventDefault(); onGotoLogin(); }}>立即登录</a></p>
    </form>
  );
}

function ResetForm({ apiBase, machineCode, showToast, onGotoLogin }: {
  apiBase: string; machineCode: string;
  showToast: (m: string) => void;
  onGotoLogin: () => void;
}) {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const { countdown, send } = useSendCode(apiBase, showToast);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email) { showToast("请输入邮箱地址"); return; }
    if (!code || code.length < 6) { showToast("请输入 6 位验证码"); return; }
    if (!newPassword || newPassword.length < 6) { showToast("密码至少 6 位字符"); return; }
    if (newPassword !== confirmPassword) { showToast("两次输入的密码不一致"); return; }

    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/auth/reset-password`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, code, new_password: newPassword }),
      });
      const data = await res.json();
      if (!res.ok) { showToast(data.detail || "重置失败"); return; }
      showToast("密码重置成功，请使用新密码登录");
      onGotoLogin();
    } catch {
      showToast("无法连接服务器");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="auth-form visible" onSubmit={handleSubmit} autoComplete="off">
      <h2>找回密码</h2>
      <p className="form-sub">通过邮箱验证后重置密码</p>

      <div className="field">
        <label>注册邮箱</label>
        <input className="input" type="email" placeholder="your@email.com" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>

      <div className="code-row">
        <div className="field">
          <label>验证码</label>
          <input className="input" type="text" placeholder="6 位验证码" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))} inputMode="numeric" autoComplete="off" />
        </div>
        <button type="button" className="btn-send" style={{ marginTop: 26 }} disabled={countdown > 0} onClick={() => send(email)}>
          {countdown > 0 ? `${countdown}s 后重发` : "发送验证码"}
        </button>
      </div>

      <div className="field">
        <label>设置密码</label>
        <input className="input" type="password" placeholder="至少 6 位字符" value={newPassword} onChange={(e) => setNewPassword(e.target.value)} required />
      </div>

      <div className="field">
        <label>确认密码</label>
        <input className="input" type="password" placeholder="再次输入密码" value={confirmPassword} onChange={(e) => setConfirmPassword(e.target.value)} required />
      </div>

      <button type="submit" className="btn-primary" disabled={loading}>
        {loading ? <><span className="spinner" /> 重置中…</> : "验证并重置密码"}
      </button>
      <p className="form-footer"><a href="#" onClick={(e) => { e.preventDefault(); onGotoLogin(); }}>返回登录</a></p>
    </form>
  );
}
