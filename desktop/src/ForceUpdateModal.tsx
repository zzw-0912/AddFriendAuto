import { open } from "@tauri-apps/plugin-shell";
import type { ClientUpdateRequiredPayload } from "./api";

interface Props {
  apiBase: string;
  clientVersion: string;
  update: ClientUpdateRequiredPayload;
}

function resolveAssetUrl(apiBase: string, url?: string | null) {
  if (!url) return "";
  if (/^(https?:)?\/\//.test(url) || url.startsWith("data:") || url.startsWith("blob:")) {
    return url;
  }
  return `${apiBase.replace(/\/$/, "")}/${url.replace(/^\//, "")}`;
}

function ForceUpdateModal({ apiBase, clientVersion, update }: Props) {
  const latestVersion = update.latest_version || "最新版本";
  const downloadUrl = update.download_url || "";
  const qrUrl = resolveAssetUrl(apiBase, update.qr_image_url);
  const message = update.message || update.detail || "当前软件版本已停用，请下载最新版本后继续使用。";

  const handleDownload = async () => {
    if (!downloadUrl) return;
    try {
      await open(downloadUrl);
    } catch {
      window.open(downloadUrl, "_blank", "noopener,noreferrer");
    }
  };

  return (
    <div className="force-update-overlay" role="dialog" aria-modal="true" aria-labelledby="force-update-title">
      <div className="force-update-modal">
        <div className="force-update-badge">需要更新</div>
        <h2 id="force-update-title">请下载最新客户端</h2>
        <p className="force-update-message">{message}</p>

        <div className="force-update-version-row">
          <span>当前版本：{clientVersion || "未知"}</span>
          <strong>最新版本：{latestVersion}</strong>
        </div>

        <div className="force-update-content">
          <div className="force-update-download">
            <span>下载链接</span>
            {downloadUrl ? (
              <code>{downloadUrl}</code>
            ) : (
              <p>后台暂未配置下载链接，请联系工作人员获取安装包。</p>
            )}
            <button type="button" className="force-update-button" disabled={!downloadUrl} onClick={() => void handleDownload()}>
              立即下载
            </button>
          </div>

          <div className="force-update-qr">
            <span>微信扫码咨询</span>
            {qrUrl ? <img src={qrUrl} alt="微信扫码咨询" /> : <div className="force-update-qr-empty">暂未配置微信图片</div>}
          </div>
        </div>

        <p className="force-update-note">更新完成后重新打开软件即可继续使用。</p>
      </div>
    </div>
  );
}

export default ForceUpdateModal;
