import { useEffect, useState } from "react";
import { getPlans, updatePlan } from "./api";
import type { PlanItem } from "./api";

function formatPriceYuan(priceCents: number) {
  const priceYuan = priceCents / 100;
  return priceYuan.toFixed(priceCents % 100 === 0 ? 0 : 2);
}

function parsePriceCents(value: string) {
  const priceYuan = Number(value.trim());
  if (!Number.isFinite(priceYuan) || priceYuan < 0) return null;
  return Math.round(priceYuan * 100);
}

function PlansPage() {
  const [plans, setPlans] = useState<PlanItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const load = () => {
    setLoading(true);
    getPlans().then(setPlans).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, []);

  const handleSave = async (planId: number, field: keyof Pick<PlanItem, "name" | "duration_days" | "price_cents" | "enabled">, value: string | number | boolean) => {
    setMsg("");
    try {
      await updatePlan(planId, { [field]: value });
      setMsg("保存成功");
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">套餐管理</h2>
      {msg && <div className="form-msg">{msg}</div>}
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>名称</th>
            <th>天数</th>
            <th>价格(元)</th>
            <th>状态</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {plans.map((p) => (
            <tr key={p.id}>
              <td>{p.id}</td>
              <td>
                <input defaultValue={p.name} onBlur={(e) => { const v = e.target.value.trim(); if (v && v !== p.name) handleSave(p.id, "name", v); }} />
              </td>
              <td>
                <input type="number" defaultValue={p.duration_days} onBlur={(e) => { const v = parseInt(e.target.value); if (v > 0 && v !== p.duration_days) handleSave(p.id, "duration_days", v); }} />
              </td>
              <td>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  defaultValue={formatPriceYuan(p.price_cents)}
                  onBlur={(e) => {
                    const v = parsePriceCents(e.target.value);
                    if (v === null) {
                      e.target.value = formatPriceYuan(p.price_cents);
                      setMsg("请输入有效价格（元）");
                      return;
                    }
                    e.target.value = formatPriceYuan(v);
                    if (v !== p.price_cents) handleSave(p.id, "price_cents", v);
                  }}
                />
              </td>
              <td>
                <span className={`badge ${p.enabled ? "badge-active" : "badge-inactive"}`}>
                  {p.enabled ? "启用" : "禁用"}
                </span>
                <button className="btn-sm" onClick={() => handleSave(p.id, "enabled", !p.enabled)}>
                  切换
                </button>
              </td>
              <td>-</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default PlansPage;
