import { useEffect, useState } from "react";
import { getUsers } from "./api";
import type { PageResponse, UserListItem } from "./api";

interface Props {
  onViewDetail: (id: number) => void;
}

function UsersPage({ onViewDetail }: Props) {
  const [data, setData] = useState<PageResponse<UserListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getUsers(page)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">用户管理</h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>邮箱</th>
            <th>状态</th>
            <th>注册时间</th>
            <th>最近登录</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((u) => (
            <tr key={u.id}>
              <td>{u.id}</td>
              <td>{u.email}</td>
              <td><span className={`badge ${u.status === "active" ? "badge-active" : "badge-inactive"}`}>{u.status}</span></td>
              <td>{u.created_at?.slice(0, 19).replace("T", " ")}</td>
              <td>{u.last_login_at ? u.last_login_at.slice(0, 19).replace("T", " ") : "-"}</td>
              <td><button className="btn-sm" onClick={() => onViewDetail(u.id)}>详情</button></td>
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

export default UsersPage;
