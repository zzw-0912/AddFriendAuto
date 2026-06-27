import { useRef, useState } from "react";

interface Props {
  apiBase: string;
  token: string;
  onClose: () => void;
}

function FeedbackModal({ apiBase, token, onClose }: Props) {
  const [content, setContent] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files || []);
    setFiles((prev) => [...prev, ...selected]);
    selected.forEach((f) => {
      const reader = new FileReader();
      reader.onload = () => setPreviews((p) => [...p, reader.result as string]);
      reader.readAsDataURL(f);
    });
    if (fileRef.current) fileRef.current.value = "";
  };

  const removeFile = (idx: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== idx));
    setPreviews((prev) => prev.filter((_, i) => i !== idx));
  };

  const getErrorMessage = async (res: Response) => {
    const body = await res.text().catch(() => "");
    let detail = "";
    if (body) {
      try {
        const data = JSON.parse(body) as { detail?: unknown };
        const rawDetail = data.detail;
        if (typeof rawDetail === "string") {
          detail = rawDetail;
        } else if (Array.isArray(rawDetail)) {
          detail = rawDetail
            .map((item: unknown) => {
              if (typeof item === "string") return item;
              if (item && typeof item === "object" && "msg" in item) {
                const msg = (item as { msg?: unknown }).msg;
                if (typeof msg === "string") return msg;
              }
              return JSON.stringify(item);
            })
            .join("; ");
        } else if (rawDetail) {
          detail = JSON.stringify(rawDetail);
        } else {
          detail = body;
        }
      } catch {
        detail = body;
      }
    }

    if (res.status === 404) return "接口不存在(404)，请重启后端服务";
    if (res.status === 401 || res.status === 403) return "登录状态已失效，请重新登录后再提交";
    if (res.status === 422) return `提交内容格式不正确(422)${detail ? `：${detail}` : ""}`;
    if (res.status >= 500) return `服务器异常(${res.status})${detail ? `：${detail}` : ""}`;
    return detail ? `提交失败(${res.status})：${detail}` : `提交失败(${res.status})`;
  };

  const handleSubmit = async () => {
    if (!content.trim()) return;
    setSubmitting(true);
    try {
      const fd = new FormData();
      fd.append("content", content);
      files.forEach((f) => fd.append("images", f));
      const res = await fetch(`${apiBase}/feedback`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
        body: fd,
      });
      if (!res.ok) throw new Error(await getErrorMessage(res));
      setDone(true);
    } catch (err) {
      alert(err instanceof Error ? err.message : "提交失败，请稍后重试");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="feedback-modal" onClick={(e) => e.stopPropagation()}>
        {done ? (
          <>
            <div className="feedback-done-icon">✓</div>
            <h3>感谢您的反馈！</h3>
            <p className="modal-sub">我们会尽快处理您的问题</p>
            <button type="button" className="btn-primary" onClick={onClose}>关闭</button>
          </>
        ) : (
          <>
            <h3>意见反馈</h3>
            <p className="modal-sub">请描述您的问题或建议，我们会及时处理</p>

            <textarea
              className="feedback-textarea"
              rows={5}
              placeholder="请描述您的问题或建议..."
              value={content}
              onChange={(e) => setContent(e.target.value)}
            />

            <div className="feedback-files">
              {previews.map((src, i) => (
                <div key={i} className="feedback-preview">
                  <img src={src} alt="" />
                  <button type="button" className="feedback-remove" onClick={() => removeFile(i)}>&times;</button>
                </div>
              ))}
              {previews.length < 6 && (
                <button type="button" className="feedback-add" onClick={() => fileRef.current?.click()}>+</button>
              )}
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              style={{ display: "none" }}
              onChange={handleFileChange}
            />

            <div className="feedback-actions">
              <button type="button" className="btn-primary" disabled={!content.trim() || submitting} onClick={handleSubmit}>
                {submitting ? "提交中..." : "提交反馈"}
              </button>
              <button type="button" className="btn-cancel" onClick={onClose}>取消</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default FeedbackModal;
