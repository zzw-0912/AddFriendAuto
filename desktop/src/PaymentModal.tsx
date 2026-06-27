import { useEffect, useState } from "react";
import QRCodeModal from "./QRCodeModal";

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
      } catch {
        // network error — plans fetch fails silently, user sees empty state
      }
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

      <QRCodeModal visible={showQR} onClose={() => setShowQR(false)} qrImages={["/qr-wechat.png", "/qr-wechat-2.png"]} />
    </div>
  );
}

export default PaymentModal;
