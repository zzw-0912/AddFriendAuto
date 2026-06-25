import { useEffect, useState } from "react";
import PaymentModal from "./PaymentModal";
import TaskPanel from "./TaskPanel";
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
        <TaskPanel
          apiBase={apiBase}
          token={auth.token}
          status={status}
          onStatusChange={fetchStatus}
        />
      </div>

      {showPayment && (
        <PaymentModal
          apiBase={apiBase}
          token={auth.token}
          trialRemaining={status?.trial.remaining ?? 0}
          onClose={() => setShowPayment(false)}
          onPaid={handlePaid}
          onSkipTrial={() => setShowPayment(false)}
        />
      )}
    </div>
  );
}

export default MainPage;
