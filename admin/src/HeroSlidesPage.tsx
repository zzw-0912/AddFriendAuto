import { useEffect, useState } from "react";
import {
  ApiRequestError,
  clearAdminHeroSlideImage,
  getAdminHeroSlides,
  resolveAssetUrl,
  uploadAdminHeroSlideImage,
  type HeroSlideItem,
} from "./api";


const HERO_SLOT_INDEXES = [1, 2, 3] as const;


interface DiagnosticLog {
  id: number;
  time: string;
  level: "info" | "success" | "error";
  message: string;
  detail?: string;
}


function createEmptySlides(): HeroSlideItem[] {
  return HERO_SLOT_INDEXES.map((slotIndex) => ({
    slot_index: slotIndex,
    image_url: null,
    updated_at: null,
  }));
}


function normalizeSlides(slides: HeroSlideItem[]): HeroSlideItem[] {
  const slideMap = new Map(slides.map((slide) => [slide.slot_index, slide]));
  return HERO_SLOT_INDEXES.map((slotIndex) => slideMap.get(slotIndex) ?? {
    slot_index: slotIndex,
    image_url: null,
    updated_at: null,
  });
}


function formatUpdatedAt(value?: string | null) {
  if (!value) return "尚未上传";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("zh-CN", { hour12: false });
}


function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(2)} MB`;
}


function describeError(err: unknown) {
  if (err instanceof ApiRequestError) {
    return {
      message: err.message,
      detail: `method=${err.method}; path=${err.path}; status=${err.status}; response=${err.responseText.slice(0, 500) || "-"}`,
    };
  }
  if (err instanceof Error) {
    return { message: err.message, detail: err.stack || "" };
  }
  return { message: "未知错误", detail: String(err) };
}


function HeroSlidesPage() {
  const [slides, setSlides] = useState<HeroSlideItem[]>(() => createEmptySlides());
  const [loading, setLoading] = useState(true);
  const [busySlot, setBusySlot] = useState<number | null>(null);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [logs, setLogs] = useState<DiagnosticLog[]>([]);
  const [imageErrors, setImageErrors] = useState<Record<number, string>>({});

  const appendLog = (level: DiagnosticLog["level"], message: string, detail?: string) => {
    const nextLog = {
      id: Date.now() + Math.random(),
      time: new Date().toLocaleTimeString("zh-CN", { hour12: false }),
      level,
      message,
      detail,
    };
    setLogs((current) => [nextLog, ...current].slice(0, 8));
    const payload = { message, detail };
    if (level === "error") {
      console.error("[hero-slides]", payload);
    } else {
      console.info("[hero-slides]", payload);
    }
  };

  const load = async () => {
    setLoading(true);
    appendLog("info", "开始加载轮播图配置", "GET /admin/hero-slides");
    try {
      const data = await getAdminHeroSlides();
      setSlides(normalizeSlides(data));
      setImageErrors({});
      setError("");
      appendLog("success", "轮播图配置加载成功", `slots=${data.length}`);
    } catch (err: unknown) {
      const info = describeError(err);
      setError(info.message);
      appendLog("error", "轮播图配置加载失败", info.detail);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const updateSingleSlide = (nextSlide: HeroSlideItem) => {
    setSlides((current) => normalizeSlides(current.map((slide) => (
      slide.slot_index === nextSlide.slot_index ? nextSlide : slide
    ))));
  };

  const handleUpload = async (slotIndex: number, file: File | null) => {
    if (!file) return;
    setBusySlot(slotIndex);
    setMsg("");
    setError("");
    setImageErrors((current) => ({ ...current, [slotIndex]: "" }));
    appendLog(
      "info",
      `开始上传第 ${slotIndex} 张轮播图`,
      `POST /admin/hero-slides/${slotIndex}/image; file=${file.name}; type=${file.type || "-"}; size=${formatFileSize(file.size)}`,
    );
    try {
      const updated = await uploadAdminHeroSlideImage(slotIndex, file);
      updateSingleSlide(updated);
      setMsg(`第 ${slotIndex} 张轮播图已更新并立即生效`);
      appendLog("success", `第 ${slotIndex} 张轮播图上传成功`, `image_url=${updated.image_url || "-"}`);
    } catch (err: unknown) {
      const info = describeError(err);
      setError(info.message);
      appendLog("error", `第 ${slotIndex} 张轮播图上传失败`, info.detail);
    } finally {
      setBusySlot(null);
    }
  };

  const handleClear = async (slotIndex: number) => {
    setBusySlot(slotIndex);
    setMsg("");
    setError("");
    appendLog("info", `开始清空第 ${slotIndex} 张轮播图`, `DELETE /admin/hero-slides/${slotIndex}/image`);
    try {
      const updated = await clearAdminHeroSlideImage(slotIndex);
      updateSingleSlide(updated);
      setImageErrors((current) => ({ ...current, [slotIndex]: "" }));
      setMsg(`第 ${slotIndex} 张轮播图已清空，客户端将回退默认装饰图`);
      appendLog("success", `第 ${slotIndex} 张轮播图已清空`, "客户端将回退默认装饰图");
    } catch (err: unknown) {
      const info = describeError(err);
      setError(info.message);
      appendLog("error", `第 ${slotIndex} 张轮播图清空失败`, info.detail);
    } finally {
      setBusySlot(null);
    }
  };

  if (loading) {
    return <div className="page-loading">加载轮播图中...</div>;
  }

  return (
    <div className="page">
      <div className="page-header hero-slides-page-header">
        <div>
          <h2 className="page-title">轮播图管理</h2>
          <p className="page-subtitle">固定管理客户端首页 3 个轮播位，只替换图片，文案继续使用客户端当前配置。</p>
        </div>
      </div>
      {msg && <div className="form-msg">{msg}</div>}
      {error && <div className="form-error">{error}</div>}

      <div className="hero-slides-grid">
        {slides.map((slide) => {
          const imageUrl = slide.image_url ? resolveAssetUrl(slide.image_url) : "";
          const hasImage = !!imageUrl;
          const imageError = imageErrors[slide.slot_index];
          const inputId = `hero-slide-upload-${slide.slot_index}`;
          const isBusy = busySlot === slide.slot_index;
          return (
            <article key={slide.slot_index} className="hero-slide-admin-card">
              <div className="hero-slide-admin-preview">
                {hasImage && !imageError ? (
                  <img
                    className="hero-slide-admin-image"
                    src={imageUrl}
                    alt={`轮播图 ${slide.slot_index}`}
                    onLoad={() => {
                      appendLog("success", `第 ${slide.slot_index} 张轮播图预览加载成功`, imageUrl);
                    }}
                    onError={() => {
                      setImageErrors((current) => ({ ...current, [slide.slot_index]: imageUrl }));
                      appendLog("error", `第 ${slide.slot_index} 张轮播图预览访问失败`, imageUrl);
                    }}
                  />
                ) : (
                  <div className="hero-slide-admin-fallback">
                    <span>{imageError ? "图片地址访问失败" : "默认装饰图"}</span>
                    <small>{imageError || "客户端无上传图时会自动回退这里"}</small>
                  </div>
                )}
              </div>

              <div className="hero-slide-admin-body">
                <div className="hero-slide-admin-heading">
                  <strong>轮播位 {slide.slot_index}</strong>
                  <span>{hasImage ? "已配置图片" : "当前使用默认图"}</span>
                </div>
                <div className="hero-slide-admin-meta">
                  <span>更新时间</span>
                  <b>{formatUpdatedAt(slide.updated_at)}</b>
                  {hasImage && (
                    <>
                      <span>图片地址</span>
                      <code title={imageUrl}>{imageUrl}</code>
                    </>
                  )}
                </div>
                <div className="hero-slide-admin-actions">
                  <label
                    htmlFor={inputId}
                    className={`hero-slide-action hero-slide-action-primary${isBusy ? " disabled" : ""}`}
                  >
                    {hasImage ? "上传替换" : "上传图片"}
                  </label>
                  <input
                    id={inputId}
                    className="hero-slide-file-input"
                    type="file"
                    accept="image/png,image/jpeg,image/webp"
                    disabled={busySlot !== null}
                    onChange={(event) => {
                      const file = event.currentTarget.files?.[0] ?? null;
                      void handleUpload(slide.slot_index, file);
                      event.currentTarget.value = "";
                    }}
                  />
                  <button
                    type="button"
                    className="hero-slide-action hero-slide-action-secondary"
                    disabled={busySlot !== null || !hasImage}
                    onClick={() => {
                      void handleClear(slide.slot_index);
                    }}
                  >
                    {isBusy ? "处理中..." : "清空恢复默认"}
                  </button>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <section className="hero-slide-diagnostics">
        <div className="hero-slide-diagnostics-header">
          <h3>最近诊断日志</h3>
          <button type="button" className="btn-sm" onClick={() => setLogs([])}>清空</button>
        </div>
        {logs.length === 0 ? (
          <p className="hero-slide-diagnostics-empty">暂无诊断日志</p>
        ) : (
          <div className="hero-slide-diagnostics-list">
            {logs.map((item) => (
              <div key={item.id} className={`hero-slide-diagnostics-item ${item.level}`}>
                <div>
                  <span>{item.time}</span>
                  <strong>{item.message}</strong>
                </div>
                {item.detail && <code>{item.detail}</code>}
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}


export default HeroSlidesPage;
