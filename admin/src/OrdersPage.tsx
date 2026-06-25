import { useEffect, useState } from "react";
import { getOrders } from "./api";

function OrdersPage() {
  const [data, setData] = useState<{ items: any[]; total: number } | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getOrders(page, 20, statusFilter || undefined)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">订单管理</h2>
      <div className="filter-bar">
        <label>状态筛选:</label>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">全部</option>
          <option value="pending">待支付</option>
          <option value="paid">已支付</option>
          <option value="expired">已过期</option>
          <option value="cancelled">已取消</option>
        </select>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>订单号</th>
            <th>用户</th>
            <th>金额(分)</th>
            <th>支付方式</th>
            <th>状态</th>
            <th>支付时间</th>
            <th>创建时间</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((o: any) => (
            <tr key={o.id}>
              <td>{o.id}</td>
              <td className="mono">{o.order_no}</td>
              <td>{o.email || `#${o.user_id}`}</td>
              <td>{o.amount_cents}</td>
              <td>{o.payment_channel || "-"}</td>
              <td><span className={`badge ${o.status === "paid" ? "badge-active" : o.status === "pending" ? "badge-warn" : "badge-inactive"}`}>{o.status}</span></td>
              <td>{o.paid_at?.slice(0, 19).replace("T", " ") || "-"}</td>
              <td>{o.created_at?.slice(0, 19).replace("T", " ")}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span>第 {page} 页 / 共 {Math.ceil((data?.total || 0) / 20)} 页</span>
        <button disabled={(data?.items.length || 0) < 20} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
    </div>
  );
}

export default OrdersPage;
