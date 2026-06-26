import { useEffect, useState } from "react";
import { getUserDetail, updateMembership } from "./api";

interface Props {
  userId: number;
  onBack: () => void;
}

function UserDetailPage({ userId, onBack }: Props) {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [extendDays, setExtendDays] = useState(30);
  const [msg, setMsg] = useState("");

  const load = () => {
    setLoading(true);
    getUserDetail(userId).then(setUser).catch(console.error).finally(() => setLoading(false));
  };

  useEffect(() => { load(); }, [userId]);

  const handleExtend = async () => {
    setMsg("");
    try {
      const r = await updateMembership(userId, "extend", extendDays);
      setMsg(`会员已延长，到期时间: ${r.ends_at}`);
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleFreeze = async () => {
    setMsg("");
    try {
      await updateMembership(userId, "freeze");
      setMsg("会员已冻结");
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  const handleUnfreeze = async () => {
    setMsg("");
    try {
      await updateMembership(userId, "unfreeze");
      setMsg("会员已解冻");
      load();
    } catch (err: unknown) {
      setMsg(err instanceof Error ? err.message : "操作失败");
    }
  };

  if (loading) return <div className="page-loading">加载中...</div>;
  if (!user) return <div className="page-loading">用户不存在</div>;

  return (
    <div className="page">
      <div className="page-header">
        <button className="btn-sm" onClick={onBack}>&larr; 返回</button>
        <h2 className="page-title">用户详情 - {user.email}</h2>
      </div>

      <div className="detail-section">
        <h3>基本信息</h3>
        <div className="detail-grid">
          <div><label>ID</label><span>{user.id}</span></div>
          <div><label>邮箱</label><span>{user.email}</span></div>
          <div><label>状态</label><span className={`badge ${user.status === "active" ? "badge-active" : "badge-inactive"}`}>{user.status}</span></div>
          <div><label>注册时间</label><span>{user.created_at?.slice(0, 19).replace("T", " ")}</span></div>
          <div><label>最近登录</label><span>{user.last_login_at?.slice(0, 19).replace("T", " ") || "-"}</span></div>
        </div>
      </div>

      {user.devices && user.devices.length > 0 && (
        <div className="detail-section">
          <h3>设备信息 ({user.devices.length} 台)</h3>
          <div className="detail-list">
            {user.devices.map((d: any) => (
              <div key={d.id} className="detail-card">
                <div className="detail-grid">
                  <div><label>设备 ID</label><span>{d.id}</span></div>
                  <div><label>机器码</label><span className="mono">{d.machine_code_hash.slice(0, 20)}...</span></div>
                  <div><label>状态</label><span className={`badge ${d.status === "active" ? "badge-active" : "badge-inactive"}`}>{d.status}</span></div>
                  <div><label>绑定时间</label><span>{d.bound_at?.slice(0, 19).replace("T", " ") || "-"}</span></div>
                  <div><label>备注</label><span>{d.remark || "-"}</span></div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="detail-section">
        <h3>会员信息</h3>
        {user.membership ? (
          <div className="detail-grid">
            <div><label>状态</label><span className={`badge ${user.membership.is_active ? "badge-active" : "badge-inactive"}`}>{user.membership.is_active ? "有效" : "无效"}</span></div>
            <div><label>有效期起</label><span>{user.membership.starts_at?.slice(0, 19).replace("T", " ") || "-"}</span></div>
            <div><label>有效期止</label><span>{user.membership.ends_at?.slice(0, 19).replace("T", " ") || "-"}</span></div>
            <div><label>原始状态</label><span>{user.membership.status}</span></div>
          </div>
        ) : (
          <p>无会员记录</p>
        )}
        <div className="detail-actions">
          <label>延长天数: <input type="number" value={extendDays} onChange={(e) => setExtendDays(Number(e.target.value))} min={1} /></label>
          <button className="btn-sm" onClick={handleExtend}>延长会员</button>
          <button className="btn-sm btn-danger" onClick={handleFreeze}>冻结</button>
          <button className="btn-sm" onClick={handleUnfreeze}>解冻</button>
        </div>
      </div>

      {user.trial && (
        <div className="detail-section">
          <h3>试用额度</h3>
          <div className="detail-grid">
            <div><label>总额度</label><span>{user.trial.total}</span></div>
            <div><label>已用</label><span>{user.trial.used}</span></div>
            <div><label>剩余</label><span>{user.trial.remaining}</span></div>
          </div>
        </div>
      )}

      {msg && <div className="form-msg">{msg}</div>}
    </div>
  );
}

export default UserDetailPage;
