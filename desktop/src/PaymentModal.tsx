import { useEffect, useState } from "react";

interface Props {
  apiBase: string;
  token: string;
  onClose: () => void;
  onPaid: () => void;
}

interface Plan {
  id: number;
  name: string;
  duration_days: number;
  price_cents: number;
  price_yuan: number;
}

function PaymentModal({ apiBase, token, onClose, onPaid }: Props) {
  const [plans, setPlans] = useState<Plan[]>([]);
  const [selected, setSelected] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch(`${apiBase}/plans`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) setPlans(await res.json());
      } catch {}
    })();
  }, []);

  const handlePay = async () => {
    if (!selected) return;
    setLoading(true);
    setMessage("");
    try {
      const res = await fetch(`${apiBase}/orders`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ plan_id: selected, payment_channel: "wechat" }),
      });
      if (!res.ok) { setMessage("创建订单失败"); return; }
      const order = await res.json();

      // Mock payment callback
      const cb = await fetch(`${apiBase}/payments/wechat/callback?order_no=${order.order_no}`, { method: "POST" });
      if (!cb.ok) { setMessage("支付处理失败"); return; }

      setMessage("支付成功！会员已开通。");
      setTimeout(onPaid, 1500);
    } catch {
      setMessage("网络错误");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>选择套餐</h2>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>

        <div className="plan-list">
          {plans.map((p) => (
            <div
              key={p.id}
              className={`plan-card${selected === p.id ? " selected" : ""}`}
              onClick={() => setSelected(p.id)}
            >
              <div className="plan-name">{p.name}</div>
              <div className="plan-price">¥{p.price_yuan}</div>
              <div className="plan-days">{p.duration_days} 天</div>
            </div>
          ))}
        </div>

        <button className="btn-primary" onClick={handlePay} disabled={!selected || loading}>
          {loading ? "处理中..." : selected ? "立即支付" : "请选择套餐"}
        </button>

        {message && <p className={message.includes("成功") ? "msg-success" : "msg-error"}>{message}</p>}
      </div>
    </div>
  );
}

export default PaymentModal;
