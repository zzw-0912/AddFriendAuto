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
  const [expandedId, setExpandedId] = useState<number | null>(null);
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
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.email || `#${item.user_id}`}</td>
              <td>
                <div
                  className="feedback-content"
                  onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                >
                  {expandedId === item.id ? content : content.slice(0, 60) + (content.length > 60 ? "..." : "")}
                </div>
              </td>
              <td>
                {item.images?.length ? (
                  <div className="feedback-thumbs">
                    {item.images.map((url, i) => {
                      const imageUrl = resolveAssetUrl(url);
                      const key = `${item.id}-${i}-${imageUrl}`;
                      return (
                      <a key={key} href={imageUrl} target="_blank" rel="noreferrer" className="feedback-thumb-link">
                        {failedImages[key] ? (
                          <span className="feedback-thumb-broken">加载失败</span>
                        ) : (
                          <img
                            src={imageUrl}
                            alt="反馈图片"
                            className="feedback-thumb"
                            onError={() => setFailedImages((prev) => ({ ...prev, [key]: true }))}
                          />
                        )}
                      </a>
                      );
                    })}
                  </div>
                ) : (
                  <span className="text-muted">-</span>
                )}
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
    </div>
  );
}

export default FeedbackPage;
