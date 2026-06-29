import { useEffect, useState } from "react";
import { getAuditLogs } from "./api";
import type { AuditLogItem, PageResponse } from "./api";

function AuditLogsPage() {
  const [data, setData] = useState<PageResponse<AuditLogItem> | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    getAuditLogs(page)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">操作审计</h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>管理员</th>
            <th>操作</th>
            <th>对象类型</th>
            <th>对象 ID</th>
            <th>详情</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((l) => (
            <tr key={l.id}>
              <td>{l.id}</td>
              <td>{l.admin_username || `#${l.admin_user_id}`}</td>
              <td><code>{l.action}</code></td>
              <td>{l.target_type || "-"}</td>
              <td>{l.target_id ?? "-"}</td>
              <td className="mono" style={{ maxWidth: 300, overflow: "hidden", textOverflow: "ellipsis" }}>{l.detail || "-"}</td>
              <td>{l.created_at?.slice(0, 19).replace("T", " ")}</td>
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

export default AuditLogsPage;
