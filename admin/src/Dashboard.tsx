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
      <div className="tutorial-section">
        <h3 className="tutorial-title">用户教程</h3>
        <div className="tutorial-list">
          <div className="tutorial-item">
            <div className="tutorial-step">1</div>
            <div className="tutorial-body">
              <strong>下载客户端并登录</strong>
              <p>用户通过桌面端应用输入邮箱验证码即可完成登录。</p>
            </div>
          </div>
          <div className="tutorial-item">
            <div className="tutorial-step">2</div>
            <div className="tutorial-body">
              <strong>添加好友任务</strong>
              <p>在任务面板配置添加好友的数量与间隔，系统自动执行。</p>
            </div>
          </div>
          <div className="tutorial-item">
            <div className="tutorial-step">3</div>
            <div className="tutorial-body">
              <strong>管理设备</strong>
              <p>每个微信号需绑定一台设备运行，可在设备页面管理。</p>
            </div>
          </div>
          <div className="tutorial-item">
            <div className="tutorial-step">4</div>
            <div className="tutorial-body">
              <strong>升级会员</strong>
              <p>购买套餐解锁更多任务配额，支持多种支付方式。</p>
            </div>
          </div>
          <div className="tutorial-item">
            <div className="tutorial-step">5</div>
            <div className="tutorial-body">
              <strong>提交反馈</strong>
              <p>如遇问题可在客户端「反馈」入口提交文字描述与截图。</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default Dashboard;
