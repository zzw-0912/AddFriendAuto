import { useEffect, useState } from "react";
import { getUsers, getOrders, getTasks, getDevices } from "./api";

function Dashboard() {
  const [stats, setStats] = useState({ users: 0, orders: 0, tasks: 0, devices: 0 });
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([getUsers(1, 1), getOrders(1, 1), getTasks(1, 1), getDevices(1, 1)])
      .then(([u, o, t, d]) => {
        setStats({ users: u.total, orders: o.total, tasks: t.total, devices: d.total });
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-loading">加载中...</div>;

  const cards = [
    { label: "用户总数", value: stats.users, color: "#4f46e5" },
    { label: "订单总数", value: stats.orders, color: "#0891b2" },
    { label: "任务总数", value: stats.tasks, color: "#059669" },
    { label: "设备总数", value: stats.devices, color: "#d97706" },
  ];

  return (
    <div className="page">
      <h2 className="page-title">系统概览</h2>
      <div className="dashboard-cards">
        {cards.map((c) => (
          <div key={c.label} className="stat-card" style={{ borderLeftColor: c.color }}>
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Dashboard;
