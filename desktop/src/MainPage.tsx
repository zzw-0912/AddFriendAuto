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

const MEMBER_STATUS_CACHE_PREFIX = "friendauto.memberStatus.v1:";
const MEMBER_STATUS_REFRESH_MS = 24 * 60 * 60 * 1000;

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
    targetType: "contact",
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

function isMembershipExpired(status: UserStatus | null) {
  if (!status || status.membership.is_active || !status.membership.ends_at) return false;
  const endsAt = new Date(status.membership.ends_at).getTime();
  return Number.isFinite(endsAt) && endsAt <= Date.now();
}

function shouldPromptPayment(status: UserStatus | null) {
  if (!status) return false;
  if (status.membership.is_active) return false;
  return status.trial.remaining <= 0 || isMembershipExpired(status);
}

function localDateKey(date = new Date()) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function memberStatusCacheKey(email: string) {
  return `${MEMBER_STATUS_CACHE_PREFIX}${email}`;
}

function loadCachedMemberStatus(email: string): UserStatus | null {
  try {
    const raw = localStorage.getItem(memberStatusCacheKey(email));
    if (!raw) return null;
    const cached = JSON.parse(raw) as { checkedDate?: string; status?: UserStatus };
    if (cached.checkedDate !== localDateKey()) return null;
    if (!cached.status?.membership.is_active) return null;
    return cached.status;
  } catch {
    return null;
  }
}

function saveMemberStatusCache(email: string, nextStatus: UserStatus) {
  const key = memberStatusCacheKey(email);
  if (!nextStatus.membership.is_active) {
    localStorage.removeItem(key);
    return;
  }
  localStorage.setItem(key, JSON.stringify({ checkedDate: localDateKey(), status: nextStatus }));
}

function msUntilNextLocalDay() {
  const now = new Date();
  const next = new Date(now);
  next.setHours(24, 0, 5, 0);
  return Math.max(60_000, next.getTime() - now.getTime());
}

function MainPage({ apiBase, auth, machineCode, onLogout, onSwitchAccount }: Props) {
  const { isOffline } = useNetworkStatus();
  const [status, setStatus] = useState<UserStatus | null>(() => loadCachedMemberStatus(auth.email));
  const [showPayment, setShowPayment] = useState(false);
  const [showQR, setShowQR] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [activeNav, setActiveNav] = useState("");
  const [currentSlide, setCurrentSlide] = useState(0);
  const [slidePaused, setSlidePaused] = useState(false);
  const [taskDefaults] = useState<TaskDefaults>(() => loadTaskDefaults());
  const [taskDefaultsVersion] = useState(0);

  const fetchStatus = useCallback(async (options?: { force?: boolean }) => {
    if (!options?.force) {
      const cached = loadCachedMemberStatus(auth.email);
      if (cached) {
        setStatus(cached);
        return cached;
      }
    }

    try {
      const res = await fetch(`${apiBase}/me/status`, {
        headers: { Authorization: `Bearer ${auth.token}` },
      });
      if (res.status === 401 || res.status === 403) {
        onLogout();
        return null;
      }
      if (res.ok) {
        const nextStatus = await res.json() as UserStatus;
        setStatus(nextStatus);
        saveMemberStatusCache(auth.email, nextStatus);
        return nextStatus;
      }
    } catch {
      // network error — OfflineBanner handles the UI feedback
    }
    return null;
  }, [apiBase, auth.email, auth.token, onLogout]);

  useEffect(() => {
    void fetchStatus();
  }, [fetchStatus]);

  useEffect(() => {
    if (!status?.membership.is_active) return;

    let intervalId: ReturnType<typeof setInterval> | null = null;
    const timeoutId = setTimeout(() => {
      void fetchStatus({ force: true });
      intervalId = setInterval(() => {
        void fetchStatus({ force: true });
      }, MEMBER_STATUS_REFRESH_MS);
    }, msUntilNextLocalDay());

    return () => {
      clearTimeout(timeoutId);
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchStatus, status?.membership.is_active]);

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
  const membershipExpired = isMembershipExpired(status);
  const canSkipTrialPayment = (status?.trial.remaining ?? 0) > 0 && !membershipExpired;

  useEffect(() => {
    if (shouldPromptPayment(status)) {
      setShowPayment(true);
    }
  }, [status]);

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
          <div className="tutorial-hero">
            <div>
              <h2 className="tutorial-heading">用户教程</h2>
              <p className="tutorial-intro">按照下面 3 步完成任务配置。运行自动化前请先确认微信主窗口已打开，避免任务启动后找不到目标窗口。</p>
            </div>
            <div className="tutorial-flow">
              <span>设置限额</span>
              <span>选择招呼语</span>
              <span>开始任务</span>
            </div>
          </div>

          <div className="tutorial-steps">
            <article className="tutorial-step-card">
              <div className="tutorial-step-copy">
                <span className="tutorial-step-num">01</span>
                <h3>设置每日微信加人人数</h3>
                <p>在“每日限额”里填写当天希望自动添加的人数。建议先小数量测试，确认微信账号状态稳定后再逐步调整。</p>
                <div className="tutorial-limit-guide">
                  <div className="tutorial-limit-row">
                    <strong>新号（注册 0–3 个月，未养好）</strong>
                    <span>单日建议 <b>3–5 人</b>；每小时最多加 <b>2 人</b>；单次间隔 <b>≥ 50 分钟</b>。</span>
                  </div>
                  <div className="tutorial-limit-row">
                    <strong>中期号（3 个月–1 年，实名绑卡）</strong>
                    <span>单日建议 <b>≤ 10 人</b>；每小时不要超过 <b>5 次申请</b>。</span>
                  </div>
                  <div className="tutorial-limit-row">
                    <strong>老号（1 年以上、高活跃、无违规）</strong>
                    <span>单日建议 <b>≤ 20 人</b>；避免连续快速添加。</span>
                  </div>
                </div>
              </div>
              <div className="tutorial-image-frame">
                <img src="/tutorial/daily-limit.png" alt="设置每日微信加人人数" />
              </div>
            </article>

            <article className="tutorial-step-card">
              <div className="tutorial-step-copy">
                <span className="tutorial-step-num">02</span>
                <h3>设置默认打招呼语</h3>
                <p>可以手动输入招呼语，也可以点击下方 3 条默认话术快速填入。选中后仍然可以继续修改文字。</p>
                <div className="tutorial-tip">建议使用自然、简短、不夸张的文案，减少被微信风控识别的风险。</div>
              </div>
              <div className="tutorial-image-frame">
                <img src="/tutorial/greeting-presets.png" alt="设置默认打招呼语" />
              </div>
            </article>

            <article className="tutorial-step-card">
              <div className="tutorial-step-copy">
                <span className="tutorial-step-num">03</span>
                <h3>开始执行加人程序</h3>
                <p>点击“开始任务”后会弹出自动化提示。确认后有 5 秒时间切换到微信，之后程序会接管鼠标和键盘。</p>
                <div className="tutorial-tip">运行期间请勿操作浏览器、微信或鼠标，等待任务完成或手动停止。</div>
              </div>
              <div className="tutorial-image-frame">
                <img src="/tutorial/start-task.png" alt="开始执行加人程序" />
              </div>
            </article>
          </div>

          <div className="tutorial-warning">
            <strong>温馨提示</strong>
            <p>请合理设置每日限额并遵守微信平台规则。如未按建议操作导致微信号被限制或封禁，本平台不承担账号风险。</p>
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
              onOpenTutorial={() => setActiveNav("用户教程")}
              onOpenPayment={() => setShowPayment(true)}
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
              {membershipExpired ? (
                <div className="status-badge trial">
                  <span className="dot" />
                  <span>会员已过期</span>
                </div>
              ) : (!status || !status.membership.is_active) && (
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
              canSkipTrial={canSkipTrialPayment}
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
