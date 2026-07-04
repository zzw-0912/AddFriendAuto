import { useEffect, useState } from "react";
import {
  clearAdminClientUpdateQrImage,
  getAdminClientUpdateConfig,
  resolveAssetUrl,
  setAdminClientForceUpdate,
  updateAdminClientUpdateConfig,
  uploadAdminClientUpdateQrImage,
  type ClientUpdateConfig,
} from "./api";


function formatUpdatedAt(value?: string | null) {
  if (!value) return "尚未更新";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}


function ClientUpdatePage() {
  const [config, setConfig] = useState<ClientUpdateConfig | null>(null);
  const [latestVersion, setLatestVersion] = useState("");
  const [downloadUrl, setDownloadUrl] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  const applyConfig = (next: ClientUpdateConfig) => {
    setConfig(next);
    setLatestVersion(next.latest_version || "");
    setDownloadUrl(next.download_url || "");
    setMessage(next.message || "");
  };

  const load = async () => {
    setLoading(true);
    try {
      applyConfig(await getAdminClientUpdateConfig());
      setError("");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "加载版本配置失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    setMsg("");
    setError("");
    try {
      const next = await updateAdminClientUpdateConfig({
        latest_version: latestVersion.trim(),
        download_url: downloadUrl.trim(),
        message: message.trim(),
      });
      applyConfig(next);
      setMsg("版本配置已保存");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "保存版本配置失败");
    } finally {
      setSaving(false);
    }
  };

  const handleForceToggle = async (enabled: boolean) => {
    setSaving(true);
    setMsg("");
    setError("");
    try {
      const next = await setAdminClientForceUpdate(enabled);
      applyConfig(next);
      setMsg(enabled ? "已开启客户端强制更新" : "已关闭客户端强制更新");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "切换强制更新状态失败");
    } finally {
      setSaving(false);
    }
  };

  const handleUploadQr = async (file: File | null) => {
    if (!file) return;
    setSaving(true);
    setMsg("");
    setError("");
    try {
      const next = await uploadAdminClientUpdateQrImage(file);
      applyConfig(next);
      setMsg("微信扫码图片已更新");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "上传微信扫码图片失败");
    } finally {
      setSaving(false);
    }
  };

  const handleClearQr = async () => {
    setSaving(true);
    setMsg("");
    setError("");
    try {
      const next = await clearAdminClientUpdateQrImage();
      applyConfig(next);
      setMsg("微信扫码图片已清空");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "清空微信扫码图片失败");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <div className="page-loading">加载版本配置中...</div>;

  const qrUrl = config?.qr_image_url ? resolveAssetUrl(config.qr_image_url) : "";

  return (
    <div className="page">
      <div className="page-header client-update-header">
        <div>
          <h2 className="page-title">版本控制</h2>
          <p className="page-subtitle">配置客户端最新版本和强制更新状态。开启后，旧版本客户端请求后端会被要求更新。</p>
        </div>
        <span className={`client-update-status ${config?.force_update_enabled ? "danger" : "safe"}`}>
          {config?.force_update_enabled ? "强制更新中" : "未开启强制更新"}
        </span>
      </div>

      {msg && <div className="form-msg">{msg}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="client-update-layout">
        <section className="client-update-form">
          <div className="form-group">
            <label>最新版本号</label>
            <input value={latestVersion} onChange={(e) => setLatestVersion(e.target.value)} placeholder="例如 0.1.1" />
          </div>
          <div className="form-group">
            <label>下载链接</label>
            <input value={downloadUrl} onChange={(e) => setDownloadUrl(e.target.value)} placeholder="填写最新安装包下载地址" />
          </div>
          <div className="form-group">
            <label>更新提示文案</label>
            <textarea value={message} onChange={(e) => setMessage(e.target.value)} rows={5} placeholder="提示用户下载最新版本" />
          </div>
          <div className="client-update-actions">
            <button className="btn-primary" type="button" disabled={saving} onClick={handleSave}>保存配置</button>
            <button className="btn-sm btn-danger" type="button" disabled={saving || config?.force_update_enabled} onClick={() => void handleForceToggle(true)}>一键强制更新</button>
            <button className="btn-sm" type="button" disabled={saving || !config?.force_update_enabled} onClick={() => void handleForceToggle(false)}>关闭强制更新</button>
          </div>
        </section>

        <section className="client-update-preview">
          <div className="client-update-preview-head">
            <strong>微信扫码图片</strong>
            <span>更新时间：{formatUpdatedAt(config?.updated_at)}</span>
          </div>
          <div className="client-update-qr-box">
            {qrUrl ? <img src={qrUrl} alt="微信扫码图片" /> : <span>暂未上传</span>}
          </div>
          <div className="client-update-actions">
            <label className={`btn-sm client-update-upload${saving ? " disabled" : ""}`}>
              上传图片
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={saving}
                onChange={(event) => {
                  const file = event.currentTarget.files?.[0] ?? null;
                  void handleUploadQr(file);
                  event.currentTarget.value = "";
                }}
              />
            </label>
            <button className="btn-sm btn-danger" type="button" disabled={saving || !qrUrl} onClick={() => void handleClearQr()}>清空图片</button>
          </div>
        </section>
      </div>
    </div>
  );
}


export default ClientUpdatePage;
