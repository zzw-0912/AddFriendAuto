import { useEffect, useState } from "react";
import PaymentModal from "./PaymentModal";
import QRCodeModal from "./QRCodeModal";
import FeedbackModal from "./FeedbackModal";
import TaskCard from "./TaskCard";
import "./MainPage.css";

interface Props {
  apiBase: string;
  auth: { token: string; email: string };
  machineCode: string;
  onLogout: () => void;
}

interface UserStatus {
  membership: { is_active: boolean; plan_id: number | null; ends_at: string | null };
  trial: { total: number; used: number; remaining: number };
}

const BOTTOM_NAV_ITEMS = [
  { label: "客服", icon: "service" },
  { label: "反馈", icon: "feedback" },
  { label: "我的", icon: "profile" },
  { label: "设置", icon: "settings" },
];

function MainPage({ apiBase, auth, onLogout }: Props) {
  const [status, setStatus] = useState<UserStatus | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("");

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

  const formatDate = (s: string | null) => s ? s.slice(0, 10) : "";
  const planId = status?.membership.plan_id;
  const cardCount = !status?.membership.is_active || !planId || planId === 1 ? 1 : planId === 2 ? 2 : 3;

  return (
    <div className="app-window main-layout">
      <div className="app-body">
        {/* Sidebar */}
        <aside className={`sidebar${sidebarCollapsed ? " collapsed" : ""}`}>
          <div className="sidebar-brand">
            <div className="brand-mark">F</div>
            <div className="sidebar-brand-name">FriendAuto</div>
          </div>

          <nav className="sidebar-nav">
            {BOTTOM_NAV_ITEMS.map((item) => (
              <a
                key={item.label}
                className={`nav-item${activeNav === item.label ? " active" : ""}`}
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setActiveNav(item.label);
                  if (item.label === "客服") setShowQR(true);
                  if (item.label === "反馈") setShowFeedback(true);
                }}
              >
                <NavIcon name={item.icon} />
                <span className="nav-text">{item.label}</span>
              </a>
            ))}
          </nav>

          <button
            className="sidebar-toggle"
            type="button"
            aria-label={sidebarCollapsed ? "展开侧边栏" : "收起侧边栏"}
            onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          >
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
              <path d="M15 18l-6-6 6-6" />
            </svg>
            <span className="toggle-text">{sidebarCollapsed ? "展开" : "收起"}</span>
          </button>
        </aside>

        {/* Content */}
        <main className="content">
          <div className="content-header">
            <div className="greeting">下午好，欢迎回来</div>
            <div className="status-bar">
              <button className="recharge-btn" onClick={() => setShowPayment(true)}>充值会员</button>
              {status?.membership.is_active && (
                <div className="status-badge member">
                  <span className="dot" />
                  <span>会员有效至 {formatDate(status.membership.ends_at)}</span>
                </div>
              )}
              {(!status || !status.membership.is_active) && (
                <div className="status-badge trial">
                  <span className="dot" />
                  <span>剩余试用 {status?.trial.remaining ?? 20} 次</span>
                </div>
              )}
              <span className="user-email">{auth.email}</span>
              <button type="button" className="btn-logout" onClick={onLogout}>退出</button>
            </div>
          </div>

          {/* Hero Banner */}
          <section className="hero-panel" aria-label="功能横幅">
            <div className="hero-track">
              <article className="hero-slide">
                <div className="hero-copy">
                  <h2 className="hero-title">智能高效 • 轻松拓展人脉</h2>
                  <p className="hero-desc">自动化加好友，精准筛选，高效管理</p>
                  <button className="hero-cta" type="button">立即体验</button>
                </div>
                <div className="hero-art" aria-hidden="true">
                  <div className="hero-ring" />
                  <div className="hero-card" />
                  <div className="hero-sheet"><div className="hero-line" /></div>
                  <div className="hero-avatar" />
                  <div className="hero-plus" />
                  <div className="hero-spark spark-a" />
                  <div className="hero-spark spark-b" />
                  <div className="hero-spark spark-c" />
                  <div className="hero-dash dash-a" />
                  <div className="hero-dash dash-b" />
                </div>
              </article>
            </div>
          </section>

          {/* Task Cards */}
          <div className="task-cards">
            {Array.from({ length: cardCount }, (_, i) => (
              <TaskCard
                key={i}
                apiBase={apiBase}
                token={auth.token}
                status={status}
                onStatusChange={fetchStatus}
              />
            ))}
          </div>
        </main>
      </div>

      {showPayment && (
            <PaymentModal
              apiBase={apiBase}
              token={auth.token}
              trialRemaining={status?.trial.remaining ?? 0}
              onClose={() => setShowPayment(false)}
              onSkipTrial={() => setShowPayment(false)}
            />
      )}
      <QRCodeModal visible={showQR} onClose={() => setShowQR(false)} qrImages={["/qr-wechat.png", "/qr-wechat-2.png"]} />
      {showFeedback && (
        <FeedbackModal
          apiBase={apiBase}
          token={auth.token}
          onClose={() => setShowFeedback(false)}
        />
      )}
    </div>
  );
}

function NavIcon({ name }: { name: string }) {
  switch (name) {
    case "home":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="3" y="3" width="8" height="8" rx="1.5" />
          <rect x="13" y="3" width="8" height="8" rx="1.5" />
          <rect x="3" y="13" width="8" height="8" rx="1.5" />
          <rect x="13" y="13" width="8" height="8" rx="1.5" />
        </svg>
      );
    case "addfriend":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M15 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2" />
          <circle cx="9" cy="7" r="4" />
          <path d="M19 8v6" />
          <path d="M16 11h6" />
        </svg>
      );
    case "contacts":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="3" y="5" width="18" height="14" rx="2.5" />
          <path d="M8 20h8" />
        </svg>
      );
    case "tasks":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="6" y="4" width="12" height="16" rx="2" />
          <path d="M9 2h6" />
          <path d="M9 10h6" />
        </svg>
      );
    case "service":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="10" />
          <path d="M9.5 9a2.5 2.5 0 0 1 5 0c0 1.9-2.5 2.2-2.5 4" />
          <circle cx="12" cy="17" r="1" fill="currentColor" stroke="none" />
        </svg>
      );
    case "feedback":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M21 15a2 2 0 0 1-2 2H8l-5 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
      );
    case "profile":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <rect x="5" y="3" width="14" height="18" rx="2.5" />
          <circle cx="12" cy="10" r="3.2" />
          <path d="M8.5 17.2c.9-1.7 2.1-2.5 3.5-2.5s2.6.8 3.5 2.5" />
        </svg>
      );
    case "settings":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="3" />
          <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 0 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 0 1-4 0v-.1a1.7 1.7 0 0 0-1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 0 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 0 1 0-4h.1a1.7 1.7 0 0 0 1.5-1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3 1.7 1.7 0 0 0 1-1.5V3a2 2 0 0 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 0 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8 1.7 1.7 0 0 0 1.5 1H21a2 2 0 0 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
        </svg>
      );
    default:
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <circle cx="12" cy="12" r="3" />
        </svg>
      );
  }
}

export default MainPage;
