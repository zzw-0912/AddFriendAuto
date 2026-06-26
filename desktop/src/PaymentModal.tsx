import { useEffect, useState } from "react";

interface Props {
  apiBase: string;
  token: string;
  trialRemaining: number;
  onClose: () => void;
  onSkipTrial: () => void;
}

interface Plan {
  id: number;
  name: string;
  duration_days: number;
  price_cents: number;
  price_yuan: number;
}

const planFeatures: Record<string, string[]> = {
  "月卡": ["无限次自动加好友", "智能标签分组", "自定义打招呼语", "任务进度追踪"],
  "季卡": ["无限次自动加好友", "智能标签分组", "自定义打招呼语", "任务进度追踪", "优先客服支持"],
  "年卡": ["无限次自动加好友", "智能标签分组", "自定义打招呼语", "任务进度追踪", "优先客服支持", "专属功能抢先体验"],
};

const planOrder = ["月卡", "季卡", "年卡"];

function PaymentModal({ apiBase, token, trialRemaining, onClose, onSkipTrial }: Props) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [showQR, setShowQR] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/plans`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data: Plan[] = await res.json();
          data.sort((a, b) => planOrder.indexOf(a.name) - planOrder.indexOf(b.name));
          setPlans(data);
          const mid = data.find((p) => p.name === "季卡")?.id ?? data[1]?.id ?? data[0]?.id;
          setSelectedPlanId(mid);
        }
      } catch {}
    })();
  }, [apiBase, token]);

  const monthlyLabel = (p: Plan) => {
    if (p.duration_days <= 0) return "";
    const perMonth = p.price_yuan / (p.duration_days / 30);
    const monthly = perMonth.toFixed(0);
    const saving = p.name === "季卡"
      ? `省 ¥${(300 * 3 - p.price_yuan).toFixed(0)}`
      : p.name === "年卡"
        ? `省 ¥${(300 * 12 - p.price_yuan).toFixed(0)}`
        : "";
    return `约 ¥${monthly} / 月${saving ? ` · ${saving}` : ""}`;
  };

  const handleSkip = (e: React.MouseEvent) => {
    e.preventDefault();
    onSkipTrial();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="pay-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="pricing-header">
          {trialRemaining > 0 && (
            <span className="trial-badge">剩余试用 {trialRemaining} 次</span>
          )}
          <h2>升级会员，畅享无限加好友</h2>
          <p className="sub">选择适合你的套餐，开通后即可无限使用</p>
        </div>

        {/* Plan cards */}
        <div className="plan-row">
          {plans.map((p) => {
            const isSelected = p.id === selectedPlanId;
            const isFeatured = p.name === "季卡";
            const features = planFeatures[p.name] ?? [];

            return (
              <div
                key={p.id}
                className={`plan-card${isSelected ? " selected" : ""}${isFeatured ? " featured" : ""}`}
                onClick={() => setSelectedPlanId(p.id)}
              >
                {isFeatured && <span className="plan-badge">推荐</span>}
                <div className="plan-name">{p.name}</div>
                <div className="plan-duration">{p.duration_days} 天有效期</div>
                <div className="plan-price"><span className="unit">¥</span>{p.price_yuan.toFixed(0)}</div>
                <div className="plan-monthly">{monthlyLabel(p)}</div>
                <ul className="plan-features">
                  {features.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
                <div className={`plan-select outline${isSelected ? " selected" : ""}`}>
                  {isSelected ? `已选${p.name}` : `选择${p.name}`}
                </div>
              </div>
            );
          })}
        </div>

        {/* Payment section */}
        <div className="payment-section">
          <div className="payment-label">支付方式</div>
          <div className="payment-options">
            <div className="payment-option selected">
              <span className="payment-radio" />
              <span className="payment-icon wechat">微</span>
              <span className="payment-name">微信支付</span>
            </div>
          </div>

          <div className="action-row">
            <button className="btn-primary" onClick={() => setShowQR(true)}>
              联系工作人员充值
            </button>
            <a href="#" className="skip-link" onClick={handleSkip}>
              跳过，<strong>开始试用</strong>
            </a>
          </div>
        </div>

        {/* Close */}
        <button className="pay-close" onClick={onClose}>&times;</button>
      </div>

      {/* QR Modal */}
      <div className={`modal-overlay qr-overlay${showQR ? " show" : ""}`} onClick={() => setShowQR(false)}>
        <div className="modal-box" onClick={(e) => e.stopPropagation()}>
          <div className="modal-icon">
            <svg viewBox="0 0 24 24" fill="currentColor"><path d="M8.691 2.188C3.891 2.188 0 5.476 0 9.53c0 2.212 1.17 4.203 3.002 5.55a.59.59 0 0 1 .213.665l-.39 1.48c-.019.07-.048.141-.048.213 0 .163.13.295.29.295a.326.326 0 0 0 .167-.054l1.903-1.114a.864.864 0 0 1 .717-.098 10.16 10.16 0 0 0 2.837.403c.276 0 .543-.027.811-.05-.857-2.578.157-4.972 1.932-6.446 1.703-1.415 3.882-1.98 5.853-1.838-.576-3.583-4.196-6.348-8.596-6.348zM5.785 5.991c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178A1.17 1.17 0 0 1 4.623 7.17c0-.651.52-1.18 1.162-1.18zm5.813 0c.642 0 1.162.529 1.162 1.18a1.17 1.17 0 0 1-1.162 1.178 1.17 1.17 0 0 1-1.162-1.178c0-.651.52-1.18 1.162-1.18zm5.34 2.867c-1.797-.052-3.746.512-5.28 1.786-1.72 1.428-2.687 3.72-1.78 6.22.942 2.453 3.666 4.229 6.884 4.229.826 0 1.622-.12 2.361-.336a.722.722 0 0 1 .598.082l1.584.926a.272.272 0 0 0 .14.045c.134 0 .24-.11.24-.245 0-.06-.024-.12-.04-.178l-.325-1.233a.492.492 0 0 1 .178-.554C23.028 18.48 24 16.82 24 14.98c0-3.21-2.931-5.952-7.062-6.122zm-2.18 2.769c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982zm4.844 0c.535 0 .969.44.969.982a.976.976 0 0 1-.969.983.976.976 0 0 1-.969-.983c0-.542.434-.982.97-.982z" /></svg>
          </div>
          <h3>扫码添加工作人员</h3>
          <p className="modal-sub">添加好友后，工作人员将为您开通会员</p>
          <div className="qr-wrapper">
            <div className="qr-placeholder">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <rect x="3" y="3" width="7" height="7" rx="1" />
                <rect x="14" y="3" width="7" height="7" rx="1" />
                <rect x="3" y="14" width="7" height="7" rx="1" />
                <path d="M14 14h2v2h-2zM18 14h2v2h-2zM14 18h2v2h-2zM18 18h2v2h-2z" />
              </svg>
            </div>
          </div>
          <p className="modal-note">请使用微信扫描二维码添加好友</p>
          <button className="btn-cancel" onClick={() => setShowQR(false)}>取消</button>
        </div>
      </div>
    </div>
  );
}

export default PaymentModal;
