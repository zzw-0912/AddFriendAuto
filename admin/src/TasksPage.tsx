import { useEffect, useState } from "react";
import { getTasks, getTaskResults } from "./api";
import type { PageResponse, TaskListItem, TaskResultItem } from "./api";

function targetTypeLabel(type?: string | null) {
  if (type === "contact") return "联系人";
  return type === "wechat_id" ? "微信号" : "手机号";
}

function TasksPage() {
  const [data, setData] = useState<PageResponse<TaskListItem> | null>(null);
  const [page, setPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [results, setResults] = useState<TaskResultItem[] | null>(null);
  const [resultsTaskId, setResultsTaskId] = useState<number | null>(null);

  useEffect(() => {
    setLoading(true);
    getTasks(page, 20, statusFilter || undefined)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page, statusFilter]);

  const handleViewResults = async (taskId: number) => {
    try {
      const r = await getTaskResults(taskId);
      setResults(r);
      setResultsTaskId(taskId);
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "加载失败");
    }
  };

  return (
    <div className="page">
      <h2 className="page-title">任务日志</h2>
      <div className="filter-bar">
        <label>状态筛选:</label>
        <select value={statusFilter} onChange={(e) => { setStatusFilter(e.target.value); setPage(1); }}>
          <option value="">全部</option>
          <option value="running">运行中</option>
          <option value="finished">已完成</option>
          <option value="stopped">已停止</option>
        </select>
      </div>
      {loading ? (
        <div className="page-loading">加载中...</div>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>用户</th>
                <th>微信</th>
                <th>目标类型</th>
                <th>每日限额</th>
                <th>状态</th>
                <th>成功/失败/无效</th>
                <th>开始时间</th>
                <th>结束时间</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {data?.items.map((t) => (
                <tr key={t.id}>
                  <td>{t.id}</td>
                  <td>{t.email || `#${t.user_id}`}</td>
                  <td>微信{t.slot_id}</td>
                  <td>{targetTypeLabel(t.target_type)}</td>
                  <td>{t.daily_limit}</td>
                  <td><span className={`badge ${t.status === "running" ? "badge-warn" : "badge-active"}`}>{t.status}</span></td>
                  <td>{t.success_count}/{t.failed_count}/{t.invalid_count}</td>
                  <td>{t.started_at?.slice(0, 19).replace("T", " ")}</td>
                  <td>{t.finished_at?.slice(0, 19).replace("T", " ") || "-"}</td>
                  <td><button className="btn-sm" onClick={() => handleViewResults(t.id)}>结果</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="pagination">
            <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
            <span>第 {page} 页 / 共 {Math.ceil((data?.total || 0) / 20)} 页</span>
            <button disabled={(data?.items.length || 0) < 20} onClick={() => setPage(page + 1)}>下一页</button>
          </div>
        </>
      )}

      {results !== null && (
        <div className="modal-overlay" onClick={() => setResults(null)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3>任务 #{resultsTaskId} 执行结果</h3>
              <button className="btn-sm" onClick={() => setResults(null)}>关闭</button>
            </div>
            <table className="data-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>目标 ID</th>
                  <th>目标类型</th>
                  <th>联系人 ID</th>
                  <th>结果</th>
                  <th>消息</th>
                  <th>扣次</th>
                  <th>时间</th>
                </tr>
              </thead>
              <tbody>
                {results.length === 0 ? (
                  <tr><td colSpan={8}>暂无结果</td></tr>
                ) : results.map((r) => (
                  <tr key={r.id}>
                    <td>{r.id}</td>
                    <td>{r.target_id ?? "-"}</td>
                    <td>{targetTypeLabel(r.target_type)}</td>
                    <td>{r.contact_id ?? "-"}</td>
                    <td>
                      <span className={`badge ${r.result === "success" ? "badge-active" : r.result === "invalid" ? "badge-warn" : "badge-inactive"}`}>
                        {r.result}
                      </span>
                    </td>
                    <td>{r.message || "-"}</td>
                    <td>{r.trial_charged ? "是" : "否"}</td>
                    <td>{r.created_at?.slice(0, 19).replace("T", " ")}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

export default TasksPage;
