import { useEffect, useState } from "react";
import { apiPost } from "./api";
import QRCodeModal from "./QRCodeModal";

interface Props {
  apiBase: string;
  token: string;
  userEmail: string;
  trialRemaining: number;
  canSkipTrial?: boolean;
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

interface OrderResponse {
  id: number;
  order_no: string;
  plan_id: number;
  amount_cents: number;
  payment_channel: string | null;
  status: string;
  paid_at: string | null;
  created_at: string;
}

const planTiers: Record<number, { name: string; usage: string; features: string[] }> = {
  1: {
    name: "Plus",
    usage: "适合轻量加好友任务",
    features: ["1 个微信任务窗口", "会员期内无限使用", "自定义打招呼语", "任务进度追踪"],
  },
  2: {
    name: "Pro 5x",
    usage: "适合多账号稳定执行",
    features: ["最多 2 个微信任务窗口", "会员期内无限使用", "任务进度追踪", "专属会员通道", "专属客服支持", "更高客户群体"],
  },
  3: {
    name: "Pro 20x",
    usage: "适合高强度加好友任务",
    features: ["最多 3 个微信任务窗口", "最高任务处理能力", "自定义打招呼语", "优先客服支持"],
  },
};

const legacyPlanNameToId: Record<string, number> = { "月卡": 1, "季卡": 2, "年卡": 3 };
const visiblePublicPlanPrices = [30000, 50000];
const hiddenPublicPlanIds = new Set([3]);
const hiddenPublicPlanPrices = new Set([80000]);

function planTier(p: Plan) {
  const legacyId = legacyPlanNameToId[p.name];
  return planTiers[p.id] ?? (legacyId ? planTiers[legacyId] : undefined);
}

function planDisplayName(p: Plan) {
  return planTier(p)?.name ?? p.name;
}

function planSortRank(p: Plan) {
  const tierId = planTiers[p.id] ? p.id : legacyPlanNameToId[p.name];
  return tierId ?? p.id;
}

function isHiddenPublicPlan(p: Plan) {
  return hiddenPublicPlanIds.has(p.id)
    || hiddenPublicPlanPrices.has(p.price_cents)
    || planDisplayName(p) === "Pro 20x";
}

function visiblePublicPlans(plans: Plan[]) {
  const sortedPlans = plans.filter((p) => !isHiddenPublicPlan(p)).sort((a, b) => planSortRank(a) - planSortRank(b));
  return visiblePublicPlanPrices
    .map((price) => sortedPlans.find((p) => p.price_cents === price))
    .filter((p): p is Plan => Boolean(p));
}

function PaymentModal({ apiBase, token, userEmail, trialRemaining, canSkipTrial = true, onClose, onSkipTrial }: Props) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selectedPlanId, setSelectedPlanId] = useState<number | null>(null);
  const [showQR, setShowQR] = useState(false);
  const [creatingOrder, setCreatingOrder] = useState(false);
  const [orderError, setOrderError] = useState("");
  const [orderInfo, setOrderInfo] = useState<{
    orderNo: string;
    planName: string;
    amountYuan: number;
    userEmail: string;
  } | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/plans`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data: Plan[] = await res.json();
          const visiblePlans = visiblePublicPlans(data);
          setPlans(visiblePlans);
          const mid = visiblePlans.find((p) => planDisplayName(p) === "Pro 5x")?.id ?? visiblePlans[1]?.id ?? visiblePlans[0]?.id ?? null;
          setSelectedPlanId(mid);
        }
      } catch {
        // network error — plans fetch fails silently, user sees empty state
      }
    })();
  }, [apiBase, token]);

  const monthlyLabel = () => "月卡套餐 · 30 天有效";

  const handleSkip = (e: React.MouseEvent) => {
    e.preventDefault();
    onSkipTrial();
  };

  const handleCreateManualOrder = async () => {
    if (!selectedPlanId || creatingOrder) return;
    const selectedPlan = plans.find((p) => p.id === selectedPlanId);
    setOrderError("");
    setCreatingOrder(true);
    try {
      const order = await apiPost<OrderResponse>(
        apiBase,
        "/orders",
        { plan_id: selectedPlanId, payment_channel: "manual_wechat" },
        token,
      );
      setOrderInfo({
        orderNo: order.order_no,
        planName: selectedPlan ? planDisplayName(selectedPlan) : `套餐 #${order.plan_id}`,
        amountYuan: order.amount_cents / 100,
        userEmail,
      });
      setShowQR(true);
    } catch (err: unknown) {
      setOrderError(err instanceof Error ? err.message : "创建订单失败，请稍后重试");
    } finally {
      setCreatingOrder(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="pay-modal" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="pricing-header">
          {trialRemaining > 0 && (
            <span className="trial-badge">剩余试用 {trialRemaining} 次</span>
          )}
          <h2>选择月卡套餐，继续自动加好友</h2>
          <p className="sub">2 个会员档位，按你的微信窗口数量和任务强度选择</p>
        </div>

        {/* Plan cards */}
        <div className="plan-row">
          {plans.map((p) => {
            const isSelected = p.id === selectedPlanId;
            const tier = planTier(p);
            const displayName = planDisplayName(p);
            const isFeatured = displayName === "Pro 5x";
            const features = tier?.features ?? ["会员期内无限使用", "自定义打招呼语", "任务进度追踪"];

            return (
              <div
                key={p.id}
                className={`plan-card${isSelected ? " selected" : ""}`}
                onClick={() => {
                  setSelectedPlanId(p.id);
                  setOrderInfo(null);
                  setOrderError("");
                }}
              >
                {isFeatured && <span className="plan-badge">推荐</span>}
                <div className="plan-name">{displayName}</div>
                <div className="plan-duration">{tier?.usage ?? "月卡会员套餐"}</div>
                <div className="plan-price"><span className="unit">¥</span>{p.price_yuan.toFixed(0)}</div>
                <div className="plan-monthly">{monthlyLabel()}</div>
                <ul className="plan-features">
                  {features.map((f, i) => (
                    <li key={i}>{f}</li>
                  ))}
                </ul>
                <div className={`plan-select outline${isSelected ? " selected" : ""}`}>
                  {isSelected ? `已选 ${displayName}` : `选择 ${displayName}`}
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
            <button className="btn-primary" disabled={!selectedPlanId || creatingOrder} onClick={handleCreateManualOrder}>
              {creatingOrder ? "正在创建订单..." : "联系工作人员充值"}
            </button>
            {canSkipTrial && (
              <a href="#" className="skip-link" onClick={handleSkip}>
                跳过，<strong>开始试用</strong>
              </a>
            )}
          </div>
          {orderError && <div className="pay-error">{orderError}</div>}
        </div>

        {/* Close */}
        <button className="pay-close" onClick={onClose}>&times;</button>
      </div>

      <QRCodeModal
        visible={showQR}
        onClose={() => setShowQR(false)}
        qrImages={["/qr-wechat.png", "/qr-wechat-2.png"]}
        orderInfo={orderInfo}
      />
    </div>
  );
}

export default PaymentModal;
