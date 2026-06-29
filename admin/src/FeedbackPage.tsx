import { useEffect, useState } from "react";
import { getFeedback, resolveAssetUrl } from "./api";

interface FeedbackItem {
  id: number;
  user_id: number;
  email?: string | null;
  content?: string;
  images?: string[] | null;
  created_at?: string;
}

function FeedbackPage() {
  const [data, setData] = useState<{ items: FeedbackItem[]; total: number } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [selectedFeedback, setSelectedFeedback] = useState<FeedbackItem | null>(null);
  const [failedImages, setFailedImages] = useState<Record<string, boolean>>({});

  useEffect(() => {
    setLoading(true);
    getFeedback(page, 20)
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [page]);

  if (loading) return <div className="page-loading">加载中...</div>;

  return (
    <div className="page">
      <h2 className="page-title">用户反馈</h2>
      <table className="data-table">
        <thead>
          <tr>
            <th>ID</th>
            <th>用户</th>
            <th>内容</th>
            <th>图片</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {data?.items.map((item) => {
            const content = item.content || "";
            return (
            <tr
              key={item.id}
              className="feedback-row"
              onClick={() => setSelectedFeedback(item)}
            >
              <td>{item.id}</td>
              <td>{item.email || `#${item.user_id}`}</td>
              <td>
                <div className="feedback-content">
                  {content.slice(0, 60) + (content.length > 60 ? "..." : "")}
                </div>
              </td>
              <td>
                {item.images?.length ? (
                  <div className="feedback-thumbs">
                    {item.images.slice(0, 3).map((url, i) => {
                      const imageUrl = resolveAssetUrl(url);
                      const key = `${item.id}-${i}-${imageUrl}`;
                      return (
                        <img
                          key={key}
                          src={imageUrl}
                          alt=""
                          className="feedback-thumb"
                          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                        />
                      );
                    })}
                    {item.images.length > 3 && <span className="feedback-more">+{item.images.length - 3}</span>}
                  </div>
                ) : null}
              </td>
              <td className="mono">{item.created_at?.slice(0, 19).replace("T", " ")}</td>
            </tr>
            );
          })}
          {!data?.items.length && (
            <tr><td colSpan={5} style={{ textAlign: "center", padding: 32, color: "#999" }}>暂无反馈</td></tr>
          )}
        </tbody>
      </table>
      <div className="pagination">
        <button disabled={page <= 1} onClick={() => setPage(page - 1)}>上一页</button>
        <span>第 {page} 页 / 共 {Math.ceil((data?.total || 0) / 20)} 页</span>
        <button disabled={(data?.items.length || 0) < 20} onClick={() => setPage(page + 1)}>下一页</button>
      </div>

      {selectedFeedback && (
        <div className="modal-overlay feedback-detail-overlay" onClick={() => setSelectedFeedback(null)}>
          <div className="feedback-detail-modal" onClick={(e) => e.stopPropagation()}>
            <div className="feedback-detail-header">
              <h3>用户反馈详情</h3>
              <button className="feedback-detail-close" onClick={() => setSelectedFeedback(null)}>✕</button>
            </div>
            <div className="feedback-detail-body">
              <div className="feedback-detail-left">
                <div className="feedback-detail-meta">
                  <span><strong>用户：</strong>{selectedFeedback.email || `#${selectedFeedback.user_id}`}</span>
                  <span><strong>时间：</strong>{selectedFeedback.created_at?.slice(0, 19).replace("T", " ")}</span>
                </div>
                <div className="feedback-detail-text">
                  {selectedFeedback.content || "（无内容）"}
                </div>
              </div>
              <div className="feedback-detail-right">
                {selectedFeedback.images?.length ? (
                  <div className="feedback-detail-images">
                    {selectedFeedback.images.map((url, i) => {
                      const imageUrl = resolveAssetUrl(url);
                      const key = `${selectedFeedback.id}-${i}-${imageUrl}`;
                      return failedImages[key] ? (
                        <div key={key} className="feedback-detail-img-broken">图片加载失败</div>
                      ) : (
                        <a key={key} href={imageUrl} target="_blank" rel="noreferrer" className="feedback-detail-img-link">
                          <img
                            src={imageUrl}
                            alt={`反馈图片 ${i + 1}`}
                            className="feedback-detail-img"
                            onError={() => setFailedImages((prev) => ({ ...prev, [key]: true }))}
                          />
                        </a>
                      );
                    })}
                  </div>
                ) : (
                  <div className="feedback-detail-noimg">暂无图片</div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default FeedbackPage;
