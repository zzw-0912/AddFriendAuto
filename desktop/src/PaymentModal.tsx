import { useEffect, useState } from "react";

interface Props {
  apiBase: string;
  token: string;
  trialRemaining: number;
  onClose: () => void;
  onPaid: () => void;
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

function PaymentModal({ apiBase, token, trialRemaining, onClose, onPaid, onSkipTrial }: Props) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [paymentMethod, setPaymentMethod] = useState<"wechat" | "alipay">("wechat");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

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
  }, []);

  const selectedPlan = plans.find((p) => p.id === selectedPlanId);
  const monthlyPrice = selectedPlan && selectedPlan.duration_days > 0
    ? (selectedPlan.price_yuan / (selectedPlan.duration_days / 30)).toFixed(0)
    : "0";

  const handlePay = async () => {
    if (!selectedPlanId) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`${apiBase}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan_id: selectedPlanId, payment_channel: paymentMethod }),
      });
      if (!res.ok) { setMessage("创建订单失败"); return; }
      const order = await res.json();

      const cb = await fetch(`${apiBase}/payments/${paymentMethod}/callback?order_no=${order.order_no}`, { method: "POST" });
      if (!cb.ok) { setMessage("支付处理失败"); return; }

      setMessage("支付成功！会员已开通");
      setTimeout(onPaid, 1500);
    } catch {
      setMessage("网络错误");
    } finally {
      setLoading(false);
    }
  };

  const handleSkip = (e: React.MouseEvent) => {
    e.preventDefault();
    onSkipTrial();
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="pay-modal" onClick={(e) => e.stopPropagation()}>
        {/* Toast */}
        {message && (
          <div className={`pay-toast ${message.includes("成功") ? "success" : "error"}`}>
            {message}
          </div>
        )}

        {/* Header */}
        <div className="pay-header">
          {trialRemaining > 0 && (
            <span className="trial-badge">剩余试用 {trialRemaining} 次</span>
          )}
          <h2>升级会员，畅享无限加好友</h2>
          <p className="pay-sub">选择适合你的套餐，开通后即可无限使用</p>
        </div>

        {/* Plan cards */}
        <div className="plan-grid">
          {plans.map((p) => {
            const isSelected = p.id === selectedPlanId;
            const isFeatured = p.name === "季卡";
            const features = planFeatures[p.name] ?? [];
            const monthly = p.duration_days > 0
              ? (p.price_yuan / (p.duration_days / 30)).toFixed(0)
              : "0";

            return (
              <div
                key={p.id}
                className={`plan-card${isSelected ? " selected" : ""}${isFeatured ? " featured" : ""}`}
                onClick={() => setSelectedPlanId(p.id)}
              >
                {isFeatured && <span className="plan-badge">推荐</span>}
                <div className="plan-card-name">{p.name}</div>
                <div className="plan-card-duration">{p.duration_days} 天有效期</div>
                <div className="plan-card-price">
                  <span className="price-unit">¥</span>{p.price_yuan.toFixed(0)}
                </div>
                <div className="plan-card-monthly">约 ¥{monthly} / 月</div>
                <ul className="plan-card-features">
                  {features.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
                <div className={`plan-select-btn${isSelected ? " selected" : ""}`}>
                  {isSelected ? "已选择" : `选择${p.name}`}
                </div>
              </div>
            );
          })}
        </div>

        {/* Payment section */}
        <div className="pay-section">
          <div className="pay-label">支付方式</div>
          <div className="pay-options">
            <div
              className={`pay-option${paymentMethod === "wechat" ? " selected" : ""}`}
              onClick={() => setPaymentMethod("wechat")}
            >
              <span className="pay-radio" />
              <span className="pay-icon wechat">微</span>
              <span className="pay-name">微信支付</span>
            </div>
            <div
              className={`pay-option${paymentMethod === "alipay" ? " selected" : ""}`}
              onClick={() => setPaymentMethod("alipay")}
            >
              <span className="pay-radio" />
              <span className="pay-icon alipay">支</span>
              <span className="pay-name">支付宝</span>
            </div>
          </div>

          <div className="pay-actions">
            <button className="btn-primary pay-btn" onClick={handlePay} disabled={!selectedPlanId || loading}>
              {loading ? (
                <><span className="spinner" /> 正在拉起支付…</>
              ) : (
                <>立即支付 ¥{selectedPlan ? selectedPlan.price_yuan.toFixed(0) : "—"}</>
              )}
            </button>
            <a href="#" className="skip-link" onClick={handleSkip}>
              跳过，<strong>开始试用</strong>
            </a>
          </div>
        </div>

        {/* Close */}
        <button className="pay-close" onClick={onClose}>&times;</button>
      </div>
    </div>
  );
}

export default PaymentModal;
