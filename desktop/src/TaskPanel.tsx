import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useNetworkStatus } from "./useNetworkStatus";
import type { TaskDefaults, UserStatus } from "./types";

interface Props {
  apiBase: string;
  token: string;
  status: UserStatus | null;
  taskDefaults: TaskDefaults;
  taskDefaultsVersion: number;
  onStatusChange: () => void;
}

interface ScriptEvent {
  run_id?: string;
  contact_id?: string | number;
  event: string;
  message?: string;
  timestamp?: string;
}

interface LogEntry {
  id: number;
  text: string;
  type: "normal" | "success" | "failed" | "invalid" | "error" | "info";
}

let logId = 0;

const BOOT_STEPS = [
  "建立加密数据传输信道",
  "同步本地联系人节点数据库",
  "演算全域风控监测矩阵阈值",
  "解析用户存量链路容量上限",
  "分配交互行为缓冲算力池",
  "规避高频访问识别探针",
];

function TaskPanel({ apiBase, token, status, taskDefaults, taskDefaultsVersion, onStatusChange }: Props) {
  const { isOnline } = useNetworkStatus();
  const [dailyLimit, setDailyLimit] = useState(taskDefaults.dailyLimit);
  const [createTag, setCreateTag] = useState(taskDefaults.createTag);
  const [greetingText, setGreetingText] = useState(taskDefaults.greetingText);
  const [isRunning, setIsRunning] = useState(false);
  const [, setTaskId] = useState<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [counters, setCounters] = useState({ success: 0, failed: 0, invalid: 0, total: 0 });
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [bootDone, setBootDone] = useState(false);
  const logEndRef = useRef<HTMLDivElement>(null);
  const taskIdRef = useRef<number | null>(null);
  const isFinishingRef = useRef(false);
  const processedResultKeysRef = useRef<Set<string>>(new Set());

  const addLog = useCallback((text: string, type: LogEntry["type"] = "info") => {
    logId += 1;
    setLogs((prev) => [...prev, { id: logId, text, type }]);
  }, []);

  const reportResult = useCallback(async (contactId: string | number | undefined, event: string, message: string) => {
    const tid = taskIdRef.current;
    if (!tid || !contactId) return;
    try {
      await fetch(`${apiBase}/tasks/${tid}/results`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ contact_id: Number(contactId), event, message }),
      });
    } catch {
      addLog("上报结果失败", "error");
    }
  }, [addLog, apiBase, token]);

  const finishCurrentTask = useCallback(async () => {
    const tid = taskIdRef.current;
    if (!tid || isFinishingRef.current) return;
    isFinishingRef.current = true;
    try {
      await fetch(`${apiBase}/tasks/${tid}/finish`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch {
      addLog("结束任务失败", "error");
    }
    setTaskId(null);
    taskIdRef.current = null;
    setIsRunning(false);
    isFinishingRef.current = false;
    onStatusChange();
  }, [addLog, apiBase, onStatusChange, token]);

  const handleScriptEvent = useCallback((event: { payload: string }) => {
    try {
      const data: ScriptEvent = JSON.parse(event.payload);

      if (data.event === "exited") {
        addLog("脚本进程已退出", "info");
        if (taskIdRef.current) {
          finishCurrentTask();
        } else {
          setIsRunning(false);
        }
        return;
      }

      const msg = data.message || data.event;
      const ts = data.timestamp ? data.timestamp.split("T")[1]?.split("+")[0] || "" : "";
      const resultKey = `${data.run_id || taskIdRef.current || ""}:${data.contact_id || ""}:${data.event}`;
      const isResultEvent = data.event === "success" || data.event === "failed" || data.event === "invalid";
      if (isResultEvent && processedResultKeysRef.current.has(resultKey)) {
        return;
      }

      switch (data.event) {
        case "started":
          addLog(`[${ts}] 任务启动: ${msg}`, "info");
          break;
        case "progress":
          addLog(`[${ts}] ${msg}`, "normal");
          break;
        case "success":
          processedResultKeysRef.current.add(resultKey);
          addLog(`[${ts}] ✅ ${msg}`, "success");
          setCounters((c) => ({ ...c, success: c.success + 1, total: c.total + 1 }));
          reportResult(data.contact_id, data.event, msg);
          break;
        case "failed":
          processedResultKeysRef.current.add(resultKey);
          addLog(`[${ts}] ❌ ${msg}`, "failed");
          setCounters((c) => ({ ...c, failed: c.failed + 1, total: c.total + 1 }));
          reportResult(data.contact_id, data.event, msg);
          break;
        case "invalid":
          processedResultKeysRef.current.add(resultKey);
          addLog(`[${ts}] ⚠️ ${msg}`, "invalid");
          setCounters((c) => ({ ...c, invalid: c.invalid + 1, total: c.total + 1 }));
          reportResult(data.contact_id, data.event, msg);
          break;
        case "error":
          addLog(`[${ts}] 🔴 ${msg}`, "error");
          break;
        case "finished":
          addLog(`[${ts}] 任务完成: ${msg}`, "info");
          finishCurrentTask();
          break;
        default:
          addLog(`[${ts}] ${msg}`, "normal");
      }
    } catch {
      addLog(`收到脚本输出: ${event.payload}`, "normal");
    }
  }, [addLog, finishCurrentTask, reportResult]);

  useEffect(() => {
    let cancelled = false;
    let unlistenFn: (() => void) | undefined;
    (async () => {
      unlistenFn = await listen<string>("script-event", handleScriptEvent);
      if (cancelled) {
        unlistenFn();
      }
    })();
    return () => {
      cancelled = true;
      unlistenFn?.();
    };
  }, [handleScriptEvent]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    if (bootDone) return;
    const timer = setInterval(() => {
      setVisibleSteps((prev) => {
        if (prev >= BOOT_STEPS.length) {
          clearInterval(timer);
          setBootDone(true);
          return prev;
        }
        return prev + 1;
      });
    }, 700);
    return () => clearInterval(timer);
  }, [bootDone]);

  useEffect(() => {
    if (isRunning) return;
    setDailyLimit(taskDefaults.dailyLimit);
    setCreateTag(taskDefaults.createTag);
    setGreetingText(taskDefaults.greetingText);
  }, [isRunning, taskDefaults.dailyLimit, taskDefaults.createTag, taskDefaults.greetingText, taskDefaultsVersion]);

  const handleStart = async () => {
    if (!isOnline) {
      addLog("无法启动：网络连接已断开", "error");
      return;
    }

    setLogs([]);
    setCounters({ success: 0, failed: 0, invalid: 0, total: 0 });
    processedResultKeysRef.current.clear();

    try {
      addLog("正在校验会员状态...", "info");
      const res = await fetch(`${apiBase}/tasks/start-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({ daily_limit: dailyLimit, create_tag: createTag, greeting_text: greetingText || null }),
      });
      const data = await res.json();
      if (!res.ok || !data.can_start) {
        addLog(`无法启动: ${data.reason || "校验失败"}`, "error");
        return;
      }

      setTaskId(data.task_id);
      taskIdRef.current = data.task_id;
      isFinishingRef.current = false;
      setIsRunning(true);

      const config = {
        run_id: String(data.task_id),
        task_id: data.task_id,
        daily_limit: dailyLimit,
        create_tag: createTag,
        greeting_text: greetingText,
        contacts: [],
      };

      addLog("正在启动脚本...", "info");
      await invoke("start_task", { configJson: JSON.stringify(config) });
    } catch (e: any) {
      addLog(`启动失败: ${e}`, "error");
      setIsRunning(false);
    }
  };

  const handleStop = async () => {
    addLog("正在停止任务...", "info");
    try {
      await invoke("stop_task");
    } catch { /* ignore */ }
    await finishCurrentTask();
    addLog("任务已停止", "info");
  };

  return (
    <div className="task-panel">
      {/* Config section */}
      <div className="section-card">
        <h3 className="section-title">任务配置</h3>
        <div className="task-config">
          <div className="config-row">
            <div className="field">
              <label>每日限额</label>
              <input
                className="input config-input"
                type="number"
                min={1}
                max={200}
                value={dailyLimit}
                onChange={(e) => setDailyLimit(Math.max(1, parseInt(e.target.value) || 1))}
                disabled={isRunning}
              />
            </div>
            <div className="field check-field">
              <label className="check-label">
                <input type="checkbox" checked={createTag} onChange={(e) => setCreateTag(e.target.checked)} disabled={isRunning} />
                创建标签
              </label>
            </div>
          </div>
          <div className="field">
            <label>打招呼语（可选）</label>
            <textarea
              className="input config-textarea"
              placeholder="你好，我是..."
              value={greetingText}
              onChange={(e) => setGreetingText(e.target.value)}
              disabled={isRunning}
              rows={2}
            />
          </div>
          <div className="task-actions">
            {!isRunning ? (
              <button className="btn-start" onClick={handleStart} disabled={!isOnline} title={!isOnline ? "网络已断开，无法启动任务" : ""}>开始任务</button>
            ) : (
              <button className="btn-stop" onClick={handleStop}>停止任务</button>
            )}
          </div>
        </div>
      </div>

      {/* Status & Counters */}
      <div className="section-card">
        <div className="task-status-row">
          <div className="ts-item">
            <span className="ts-label">会员</span>
            <span className={`ts-value ${status?.membership.is_active ? "active" : "inactive"}`}>
              {status?.membership.is_active ? `有效至 ${status.membership.ends_at?.slice(0, 10)}` : "未开通"}
            </span>
          </div>
          <div className="ts-item">
            <span className="ts-label">试用剩余</span>
            <span className="ts-value">{status?.trial.remaining ?? 0} 次</span>
          </div>
          <div className="ts-item">
            <span className="ts-label">成功</span>
            <span className="ts-value success">{counters.success}</span>
          </div>
          <div className="ts-item">
            <span className="ts-label">失败</span>
            <span className="ts-value failed">{counters.failed}</span>
          </div>
          <div className="ts-item">
            <span className="ts-label">无效</span>
            <span className="ts-value invalid">{counters.invalid}</span>
          </div>
        </div>
      </div>

      {/* Terminal — replaces log area */}
      <div className="section-card terminal-card">
        <div className="terminal-header">
          <div className="terminal-dots">
            <span className="terminal-dot dot-red" />
            <span className="terminal-dot dot-yellow" />
            <span className="terminal-dot dot-green" />
          </div>
          <span className="terminal-title">人际链路交互终端 v3.2.1</span>
        </div>
        <div className="terminal-body">
          <div className="term-line term-title">人际链路交互终端初始化</div>
          {BOOT_STEPS.slice(0, visibleSteps).map((step, i) => (
            <div key={i} className="term-line term-status">
              <span className="term-arrow">▶</span> {step}...
              <span className="term-ok">OK</span>
            </div>
          ))}
          {!bootDone && visibleSteps < BOOT_STEPS.length && <span className="term-cursor">█</span>}
          {bootDone && (
            <div className="term-line term-ready">链路解析内核就绪，等待人工交互指令输入</div>
          )}
        </div>
        <div className="terminal-footer">
          全域行为监测系统实时在线，高密度连续发起链路申请将触发交互权限锁定，操作风险由使用者全权承担。本终端仅提供数据查阅能力，无自主批量交互执行模块。
        </div>
      </div>
    </div>
  );
}

export default TaskPanel;
