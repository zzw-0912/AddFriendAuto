import { useCallback, useEffect, useState } from "react";
import { readErrorDetail } from "./api";

interface Props {
  apiBase: string;
  token: string;
  email: string;
  onAuthExpired: () => void;
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

interface LoadError {
  message: string;
  canRetry: boolean;
}

function ProfilePage({ apiBase, token, email, onAuthExpired }: Props) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState<LoadError | null>(null);
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);

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

  const handleCopy = async () => {
    if (!profile?.referral_code) return;
    try {
      await navigator.clipboard.writeText(profile.referral_code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {}
  };

  const formatDate = (s: string | null) => s ? s.slice(0, 10) : "-";

  if (loading) {
    return <div className="profile-loading">加载中...</div>;
  }

  if (error || !profile) {
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
      {/* User Info Card */}
      <div className="profile-card">
        <div className="profile-card-header">
          <div className="profile-avatar">{email.charAt(0).toUpperCase() || "U"}</div>
          <div className="profile-title">
            <h3>{email}</h3>
            <span className={`profile-status ${profile.membership.is_active ? "member" : "trial"}`}>
              {profile.membership.is_active ? "已开通会员" : "试用用户"}
            </span>
          </div>
        </div>
        <div className="profile-info-grid">
          <div className="profile-info-item">
            <span className="profile-label">注册时间</span>
            <span className="profile-value">{formatDate(profile.created_at)}</span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">最后登录</span>
            <span className="profile-value">{formatDate(profile.last_login_at)}</span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">会员有效期</span>
            <span className="profile-value">
              {profile.membership.is_active
                ? `至 ${formatDate(profile.membership.ends_at)}`
                : "未开通"}
            </span>
          </div>
          <div className="profile-info-item">
            <span className="profile-label">剩余试用</span>
            <span className="profile-value">{profile.trial.remaining} 次</span>
          </div>
        </div>
      </div>

      {/* Statistics Card */}
      <div className="profile-card">
        <h4 className="profile-card-title">累计数据</h4>
        <div className="profile-stats">
          <div className="profile-stat stat-success">
            <div className="stat-number">{profile.success_count.toLocaleString()}</div>
            <div className="stat-label">加人成功</div>
          </div>
          <div className="profile-stat stat-failed">
            <div className="stat-number">{profile.failed_count.toLocaleString()}</div>
            <div className="stat-label">失败</div>
          </div>
          <div className="profile-stat stat-invalid">
            <div className="stat-number">{profile.invalid_count.toLocaleString()}</div>
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
              <span className="referral-code">{profile.referral_code || "-"}</span>
              {profile.referral_code && (
                <button type="button" className="referral-copy-btn" onClick={handleCopy}>
                  {copied ? "已复制" : "复制"}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default ProfilePage;
