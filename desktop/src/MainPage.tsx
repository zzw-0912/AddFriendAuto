import { useCallback, useEffect, useState } from "react";
import PaymentModal from "./PaymentModal";
import QRCodeModal from "./QRCodeModal";
import FeedbackModal from "./FeedbackModal";
import ProfilePage from "./ProfilePage";
import TaskCard from "./TaskCard";
import OfflineBanner from "./OfflineBanner";
import { useNetworkStatus } from "./useNetworkStatus";
import {
  DEFAULT_TASK_DEFAULTS,
  TASK_DEFAULTS_STORAGE_KEY,
  type TaskDefaults,
  type UserStatus,
} from "./types";
import "./MainPage.css";

interface Props {
  apiBase: string;
  auth: { token: string; email: string };
  machineCode: string;
  onLogout: () => void;
  onSwitchAccount: (token: string, email: string) => void;
}

const TOP_NAV_ITEMS = [
  { label: "首页", icon: "home" },
  { label: "用户教程", icon: "tutorial" },
];

const BOTTOM_NAV_ITEMS = [
  { label: "客服", icon: "service" },
  { label: "反馈", icon: "feedback" },
  { label: "我的", icon: "profile" },
];

const HERO_SLIDES = [
  {
    title: "智能高效 · 轻松拓展人脉",
    desc: "自动化加好友，精准筛选，高效管理",
    cta: "立即体验",
  },
  {
    title: "多账号同时管理",
    desc: "支持多个微信账号绑定，任务独立配置运行",
    cta: "了解更多",
  },
  {
    title: "智能标签分组",
    desc: "自动为新增好友添加标签，分类管理更方便",
    cta: "开始使用",
  },
];

function normalizeTaskDefaults(defaults: Partial<TaskDefaults> | null): TaskDefaults {
  return {
    dailyLimit: Math.min(200, Math.max(1, Number(defaults?.dailyLimit) || DEFAULT_TASK_DEFAULTS.dailyLimit)),
    createTag: Boolean(defaults?.createTag),
    greetingText: typeof defaults?.greetingText === "string" ? defaults.greetingText.trim() : DEFAULT_TASK_DEFAULTS.greetingText,
  };
}

function loadTaskDefaults(): TaskDefaults {
  try {
    const raw = localStorage.getItem(TASK_DEFAULTS_STORAGE_KEY);
    if (!raw) return DEFAULT_TASK_DEFAULTS;
    return normalizeTaskDefaults(JSON.parse(raw) as Partial<TaskDefaults>);
  } catch {
    return DEFAULT_TASK_DEFAULTS;
  }
}

function getGreeting() {
  const hour = new Date().getHours();
  if (hour < 6) return "凌晨好";
  if (hour < 12) return "早上好";
  if (hour < 14) return "中午好";
  if (hour < 18) return "下午好";
  return "晚上好";
}

function MainPage({ apiBase, auth, machineCode, onLogout, onSwitchAccount }: Props) {
  const { isOffline } = useNetworkStatus();
  const [status, setStatus] = useState<UserStatus | null>(null);
  const [showPayment, setShowPayment] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("");
  const [currentSlide, setCurrentSlide] = useState(0);
  const [slidePaused, setSlidePaused] = useState(false);
  const [taskDefaults] = useState<TaskDefaults>(() => loadTaskDefaults());
  const [taskDefaultsVersion] = useState(0);

  const fetchStatus = useCallback(async () => {
    try {
      const res = await fetch(`${apiBase}/me/status`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      });
      if (res.status === 401 || res.status === 403) {
        onLogout();
        return;
      }
      if (res.ok) setStatus(await res.json());
    } catch {
      // network error — OfflineBanner handles the UI feedback
    }
  }, [apiBase, auth.token, onLogout]);

  useEffect(() => {
    fetchStatus();
    const interval = setInterval(fetchStatus, 30000);
    return () => clearInterval(interval);
  }, [fetchStatus]);

  useEffect(() => {
    if (slidePaused) return;
    const timer = setInterval(() => {
      setCurrentSlide((prev) => (prev + 1) % HERO_SLIDES.length);
    }, 5000);
    return () => clearInterval(timer);
  }, [slidePaused]);

  const formatDate = (s: string | null) => s ? s.slice(0, 10) : "";
  const planId = status?.membership.plan_id;
  const cardCount = !status?.membership.is_active || !planId || planId === 1 ? 1 : planId === 2 ? 2 : 3;

  const renderMainContent = () => {
    if (activeNav === "我的") {
      return (
        <ProfilePage
          apiBase={apiBase}
          token={auth.token}
          email={auth.email}
          machineCode={machineCode}
          status={status}
          onAuthExpired={onLogout}
          onLogout={onLogout}
          onSwitchAccount={onSwitchAccount}
        />
      );
    }

    if (activeNav === "用户教程") {
      return (
        <div className="tutorial-page">
          <h2 className="tutorial-heading">用户教程</h2>
          <p className="tutorial-intro">不同注册时间的微信号每日添加好友上限不同，请按照以下建议操作，超出限制可能导致账号异常。</p>
          <div className="tutorial-cards">
            <div className="tutorial-card">
              <div className="tutorial-card-num">1</div>
              <div className="tutorial-card-body">
                <strong>新号</strong>
                <span>单日主动陌生人：3–5 人封顶，严禁批量加</span>
                <span>每小时最多加 2 人，单次间隔 ≥ 30 分钟</span>
              </div>
            </div>
            <div className="tutorial-card">
              <div className="tutorial-card-num">2</div>
              <div className="tutorial-card-body">
                <strong>中期号</strong>
                <span>每日安全主动添加：≤ 10 人</span>
                <span>1 小时内不要超过 5 次申请</span>
              </div>
            </div>
            <div className="tutorial-card">
              <div className="tutorial-card-num">3</div>
              <div className="tutorial-card-body">
                <strong>老号</strong>
                <span>单日安全主动上限：20 人</span>
                <span>严禁连续快速点添加，每条申请间隔 5–10 分钟</span>
              </div>
            </div>
          </div>
          <div className="tutorial-warning">
            <strong>⚠️ 温馨提示</strong>
            <p>如未按以上建议操作，导致微信号被限制或被封禁，本平台概不负责。请合理使用，遵守微信平台规则。</p>
          </div>
        </div>
      );
    }

    return (
      <>
        {/* Hero Carousel */}
        <section
          className="hero-panel"
          aria-label="功能横幅"
          onMouseEnter={() => setSlidePaused(true)}
          onMouseLeave={() => setSlidePaused(false)}
        >
          <div className="hero-track" style={{ transform: `translateX(-${currentSlide * 100}%)` }}>
            {HERO_SLIDES.map((slide, i) => (
              <article key={i} className="hero-slide">
                <div className="hero-copy">
                  <h2 className="hero-title">{slide.title}</h2>
                  <p className="hero-desc">{slide.desc}</p>
                  <button className="hero-cta" type="button">{slide.cta}</button>
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
            ))}
          </div>

          {/* Dots */}
          <div className="hero-dots">
            {HERO_SLIDES.map((_, i) => (
              <button
                key={i}
                className={`hero-dot${i === currentSlide ? " active" : ""}`}
                aria-label={`切换到第 ${i + 1} 张`}
                onClick={() => setCurrentSlide(i)}
              />
            ))}
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
              slotId={i + 1}
              taskDefaults={taskDefaults}
              taskDefaultsVersion={taskDefaultsVersion}
              onStatusChange={fetchStatus}
            />
          ))}
        </div>
      </>
    );
  };

  return (
    <div className="app-window main-layout">
      <div className="app-body">
        {/* Sidebar */}
        <aside className={`sidebar${sidebarCollapsed ? " collapsed" : ""}`}>
          <button className="sidebar-brand" type="button" onClick={() => setActiveNav("")}>
            <div className="brand-mark">F</div>
            <div className="sidebar-brand-name">FriendAuto</div>
          </button>

          <nav className="sidebar-nav">
            {TOP_NAV_ITEMS.map((item) => (
              <a
                key={item.label}
                className={`nav-item${activeNav === item.label ? " active" : ""}`}
                href="#"
                onClick={(e) => {
                  e.preventDefault();
                  setActiveNav(item.label === "首页" ? "" : item.label);
                }}
              >
                <NavIcon name={item.icon} />
                <span className="nav-text">{item.label}</span>
              </a>
            ))}

            <div className="nav-spacer" />

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
            <div className="greeting">{getGreeting()}，欢迎回来</div>
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

          <OfflineBanner isOffline={isOffline} />
          {renderMainContent()}
        </main>
      </div>

      {showPayment && (
            <PaymentModal
              apiBase={apiBase}
              token={auth.token}
              userEmail={auth.email}
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
    case "tutorial":
      return (
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          <path d="M8 7h8M8 11h6" />
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
