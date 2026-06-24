import { useEffect, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import PaymentModal from "./PaymentModal";
import "./MainPage.css";

interface Props {
  apiBase: string;
  auth: { token: string; email: string };
  machineCode: string;
  onLogout: () => void;
}

interface UserStatus {
  membership: { is_active: boolean; ends_at: string | null };
  trial: { total: number; used: number; remaining: number };
}

function MainPage({ apiBase, auth, onLogout }: Props) {
  const [status, setStatus] = useState<UserStatus | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [healthMsg, setHealthMsg] = useState("");
  const [scriptOutput, setScriptOutput] = useState<string[]>([]);
  const [isRunning, setIsRunning] = useState(false);

  const fetchStatus = async () => {
    try {
      const res = await fetch(`${apiBase}/me/status`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      });
      if (res.ok) setStatus(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const checkHealth = async () => {
    try {
      const res = await fetch(`${apiBase}/health`);
      setHealthMsg(JSON.stringify(await res.json()));
    } catch {
      setHealthMsg("Server unreachable");
    }
  };

  const runTestScript = async () => {
    setIsRunning(true);
    setScriptOutput([]);
    try {
      const result = await invoke<string>("run_python_script", { runId: "tauri_test_001" });
      setScriptOutput(result.split("\n").filter(Boolean));
    } catch (e: any) {
      setScriptOutput([`Error: ${e}`]);
    } finally {
      setIsRunning(false);
    }
  };

  const handlePaid = () => {
    setShowPayment(false);
    fetchStatus();
  };

  return (
    <div className="main-layout">
      {/* Top status bar */}
      <header className="topbar">
        <div className="topbar-left">
          <div className="topbar-logo">F</div>
          <span className="topbar-title">FriendAuto</span>
        </div>
        <div className="topbar-status">
          {status && (
            <>
              {status.membership.is_active ? (
                <span className="badge badge-vip">
                  VIP · {status.membership.ends_at?.slice(0, 10)}
                </span>
              ) : (
                <span className="badge badge-trial">
                  试用剩余 {status.trial.remaining} 次
                </span>
              )}
            </>
          )}
          <button className="btn-recharge" onClick={() => setShowPayment(true)}>
            充值
          </button>
        </div>
        <div className="topbar-right">
          <span className="topbar-email">{auth.email}</span>
          <button className="btn-logout" onClick={onLogout}>退出</button>
        </div>
      </header>

      {/* Main content */}
      <div className="main-content">
        {/* Status card */}
        {status && (
          <div className="status-summary">
            <div className="stat-card">
              <div className="stat-label">会员状态</div>
              <div className={`stat-value ${status.membership.is_active ? "active" : "inactive"}`}>
                {status.membership.is_active ? `有效至 ${status.membership.ends_at?.slice(0, 10)}` : "未开通"}
              </div>
            </div>
            <div className="stat-card">
              <div className="stat-label">试用次数</div>
              <div className="stat-value">{status.trial.remaining} / {status.trial.total}</div>
              <div className="stat-bar">
                <div className="stat-bar-fill" style={{ width: `${(status.trial.used / status.trial.total) * 100}%` }} />
              </div>
            </div>
          </div>
        )}

        {/* Health check */}
        <div className="section-card">
          <div className="section-header">
            <h3>服务状态</h3>
            <button className="btn-sm" onClick={checkHealth}>检测</button>
          </div>
          {healthMsg && <pre className="mono-output">{healthMsg}</pre>}
        </div>

        {/* Script runner */}
        <div className="section-card">
          <div className="section-header">
            <h3>测试自动化脚本</h3>
            <button className="btn-sm" onClick={runTestScript} disabled={isRunning}>
              {isRunning ? "运行中..." : "运行"}
            </button>
          </div>
          {scriptOutput.length > 0 && (
            <div className="log-box">
              {scriptOutput.map((line, i) => <pre key={i} className="log-line">{line}</pre>)}
            </div>
          )}
        </div>
      </div>

      {showPayment && (
        <PaymentModal
          apiBase={apiBase}
          token={auth.token}
          onClose={() => setShowPayment(false)}
          onPaid={handlePaid}
        />
      )}
    </div>
  );
}

export default MainPage;
