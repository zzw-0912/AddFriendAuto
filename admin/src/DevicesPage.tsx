import { useEffect, useState } from "react";
import { getDevices, updateDevice, rebindDevice } from "./api";

function DevicesPage() {
  const [data, setData] = useState<{ items: any[]; total: number } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState("");

  const load = () => {
    setLoading(true);
    getDevices(page).then(setData).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [page]);

  const handleUnbind = async (id: number) => {
    if (!confirm("确定解绑该设备？")) return;
    setMsg("");
    try {
      await updateDevice(id, { unbind: true });
      setMsg("设备已解绑");
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleRebind = async (id: number) => {
    const newUserId = prompt("输入新用户 ID:");
    if (!newUserId) return;
    setMsg("");
    try {
      await rebindDevice(id, parseInt(newUserId));
      setMsg(`设备已改绑到用户 ${newUserId}`);
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">设备管理</h2>
      {msg && <div className="form-msg">{msg}</div>}
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户</th>
            <th>机器码</th>
            <th>状态</th>
            <th>绑定时间</th>
            <th>备注</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((d: any) => (
            <tr key={d.id}>
              <td>{d.id}</td>
              <td>{d.email || `#${d.user_id}`}</td>
              <td className="mono">{d.machine_code_hash?.slice(0, 16)}...</td>
              <td><span className={`badge ${d.status === "active" ? "badge-active" : "badge-inactive"}`}>{d.status}</span></td>
              <td>{d.bound_at?.slice(0, 19).replace("T", " ") || "-"}</td>
              <td>{d.remark || "-"}</td>
              <td>
                <button className="btn-sm" onClick={() => handleRebind(d.id)}>改绑</button>
                <button className="btn-sm btn-danger" onClick={() => handleUnbind(d.id)}>解绑</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span>第 {page} 页</span>
        <button disabled={(data?.items.length || 0) < 20} onClick={() => setPage(page + 1)}>下一页</button>
      </div>
    </div>
  );
}

export default DevicesPage;
