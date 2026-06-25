import { useEffect, useState } from "react";
import { isLoggedIn, clearToken, login as apiLogin } from "./api";
import LoginPage from "./LoginPage";
import Dashboard from "./Dashboard";
import UsersPage from "./UsersPage";
import UserDetailPage from "./UserDetailPage";
import DevicesPage from "./DevicesPage";
import PlansPage from "./PlansPage";
import OrdersPage from "./OrdersPage";
import TasksPage from "./TasksPage";
import AuditLogsPage from "./AuditLogsPage";
import "./style.css";

type Page = "dashboard" | "users" | "user-detail" | "devices" | "plans" | "orders" | "tasks" | "audit-logs";

function App() {
  const [loggedIn, setLoggedIn] = useState(isLoggedIn());
  const [page, setPage] = useState<Page>("dashboard");
  const [selectedUserId, setSelectedUserId] = useState<number | null>(null);

  const handleLogin = async (username: string, password: string) => {
    await apiLogin(username, password);
    setLoggedIn(true);
    setPage("dashboard");
  };

  const handleLogout = () => {
    clearToken();
    setLoggedIn(false);
  };

  const navigate = (p: Page) => {
    setPage(p);
    setSelectedUserId(null);
  };

  const showUserDetail = (id: number) => {
    setSelectedUserId(id);
    setPage("user-detail");
  };

  if (!loggedIn) {
    return <LoginPage onLogin={handleLogin} />;
  }

  return (
    <div className="admin-layout">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h2>FriendAuto</h2>
          <span className="sidebar-subtitle">管理后台</span>
        </div>
        <nav className="sidebar-nav">
          <button className={page === "dashboard" ? "active" : ""} onClick={() => navigate("dashboard")}>概览</button>
          <button className={page === "users" ? "active" : ""} onClick={() => navigate("users")}>用户管理</button>
          <button className={page === "devices" ? "active" : ""} onClick={() => navigate("devices")}>设备管理</button>
          <button className={page === "plans" ? "active" : ""} onClick={() => navigate("plans")}>套餐管理</button>
          <button className={page === "orders" ? "active" : ""} onClick={() => navigate("orders")}>订单管理</button>
          <button className={page === "tasks" ? "active" : ""} onClick={() => navigate("tasks")}>任务日志</button>
          <button className={page === "audit-logs" ? "active" : ""} onClick={() => navigate("audit-logs")}>操作审计</button>
        </nav>
        <div className="sidebar-footer">
          <button onClick={handleLogout}>退出登录</button>
        </div>
      </aside>
      <main className="main-area">
        {page === "dashboard" && <Dashboard />}
        {page === "users" && <UsersPage onViewDetail={showUserDetail} />}
        {page === "user-detail" && selectedUserId !== null && (
          <UserDetailPage userId={selectedUserId} onBack={() => navigate("users")} />
        )}
        {page === "devices" && <DevicesPage />}
        {page === "plans" && <PlansPage />}
        {page === "orders" && <OrdersPage />}
        {page === "tasks" && <TasksPage />}
        {page === "audit-logs" && <AuditLogsPage />}
      </main>
    </div>
  );
}

export default App;
