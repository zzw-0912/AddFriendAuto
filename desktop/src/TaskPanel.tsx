import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { useNetworkStatus } from "./useNetworkStatus";
import { loadTaskSlotConfig, loadWeChatBindings, saveTaskSlotConfig } from "./localSettings";
import type { TargetType, TaskDefaults, UserStatus } from "./types";

interface Props {
  apiBase: string;
  token: string;
  status: UserStatus | null;
  slotId: number;
  taskDefaults: TaskDefaults;
  taskDefaultsVersion: number;
  onStatusChange: (options?: { force?: boolean }) => void | Promise<unknown>;
  onOpenTutorial: () => void;
  onOpenPayment: () => void;
}

interface ScriptEvent {
  run_id?: string;
  slot_id?: number;
  target_id?: string | number;
  target_type?: TargetType;
  contact_id?: string | number;
  event: string;
  message?: string;
  timestamp?: string;
}

interface TaskTarget {
  target_id: number;
  target_type: TargetType;
  target_value: string;
  masked_value: string;
  display_name?: string | null;
}

interface ClaimTargetsResponse {
  task_id: number;
  target_type: TargetType;
  count: number;
  targets: TaskTarget[];
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

const START_DELAY_SECONDS = 5;
const DEFAULT_GREETING_TEXTS = [
  "你好，很高兴认识你，方便加个微信交流一下吗？",
  "您好，看到您的资料很不错，想加个好友认识一下。",
  "你好，我这边想和你交流一下相关信息，方便通过好友吗？",
];

function targetTypeLabel(type: TargetType) {
  if (type === "contact") return "联系人";
  return type === "wechat_id" ? "微信号" : "手机号";
}

function TaskPanel({
  apiBase,
  token,
  slotId,
  taskDefaults,
  taskDefaultsVersion,
  onStatusChange,
  onOpenTutorial,
  onOpenPayment,
}: Props) {
  const { isOnline } = useNetworkStatus();
  const [targetType, setTargetType] = useState<TargetType>(() => loadTaskSlotConfig(slotId, taskDefaults).targetType);
  const [dailyLimit, setDailyLimit] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).dailyLimit);
  const [createTag, setCreateTag] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).createTag);
  const [greetingText, setGreetingText] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).greetingText);
  const [isRunning, setIsRunning] = useState(false);
  const [, setTaskId] = useState<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [bootDone, setBootDone] = useState(false);
  const [showAutomationPrompt, setShowAutomationPrompt] = useState(false);
  const [startCountdown, setStartCountdown] = useState(0);
  const logEndRef = useRef<HTMLDivElement>(null);
  const taskIdRef = useRef<number | null>(null);
  const isFinishingRef = useRef(false);
  const processedResultKeysRef = useRef<Set<string>>(new Set());
  const startDelayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startCountdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const addLog = useCallback((text: string, type: LogEntry["type"] = "info") => {
    logId += 1;
    setLogs((prev) => [...prev, { id: logId, text, type }]);
  }, []);

  const reportResult = useCallback(async (
    contactId: string | number | undefined,
    targetId: string | number | undefined,
    event: string,
    message: string,
  ) => {
    const tid = taskIdRef.current;
    if (!tid || (!targetId && !contactId)) return;
    try {
      await fetch(`${apiBase}/tasks/${tid}/results`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          target_id: targetId ? Number(targetId) : undefined,
          contact_id: contactId ? Number(contactId) : undefined,
          event,
          message,
        }),
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
      const currentRunId = taskIdRef.current ? String(taskIdRef.current) : "";
      const eventRunId = data.run_id ? String(data.run_id) : "";
      if (data.slot_id && data.slot_id !== slotId) return;
      if (eventRunId && currentRunId && eventRunId !== currentRunId) return;
      if (eventRunId && !currentRunId) return;

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
      const resultKey = `${data.run_id || taskIdRef.current || ""}:${data.target_id || data.contact_id || ""}:${data.event}`;
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
          reportResult(data.contact_id, data.target_id, data.event, msg);
          break;
        case "failed":
          processedResultKeysRef.current.add(resultKey);
          addLog(`[${ts}] ❌ ${msg}`, "failed");
          reportResult(data.contact_id, data.target_id, data.event, msg);
          break;
        case "invalid":
          processedResultKeysRef.current.add(resultKey);
          addLog(`[${ts}] ⚠️ ${msg}`, "invalid");
          reportResult(data.contact_id, data.target_id, data.event, msg);
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
  }, [addLog, finishCurrentTask, reportResult, slotId]);

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
    const slotConfig = loadTaskSlotConfig(slotId, taskDefaults);
    setTargetType(slotConfig.targetType);
    setDailyLimit(slotConfig.dailyLimit);
    setCreateTag(slotConfig.createTag);
    setGreetingText(slotConfig.greetingText);
  }, [isRunning, slotId, taskDefaults, taskDefaultsVersion]);

  useEffect(() => {
    if (isRunning) return;
    saveTaskSlotConfig(slotId, { targetType, dailyLimit, createTag, greetingText });
  }, [createTag, dailyLimit, greetingText, isRunning, slotId, targetType]);

  useEffect(() => {
    return () => {
      if (startDelayTimerRef.current) clearTimeout(startDelayTimerRef.current);
      if (startCountdownTimerRef.current) clearInterval(startCountdownTimerRef.current);
    };
  }, []);

  const clearStartDelay = useCallback(() => {
    if (startDelayTimerRef.current) {
      clearTimeout(startDelayTimerRef.current);
      startDelayTimerRef.current = null;
    }
    if (startCountdownTimerRef.current) {
      clearInterval(startCountdownTimerRef.current);
      startCountdownTimerRef.current = null;
    }
    setStartCountdown(0);
  }, []);

  const runStartTask = async () => {
    if (!isOnline) {
      addLog("无法启动：网络连接已断开", "error");
      return;
    }

    const wechatBinding = loadWeChatBindings()[String(slotId)];
    if (!wechatBinding) {
      addLog(`无法启动：请先在“我的”页面绑定微信${slotId}窗口`, "error");
      return;
    }

    setLogs([]);
    processedResultKeysRef.current.clear();

    try {
      const bindingAlive = await invoke<boolean>("validate_wechat_binding", { binding: wechatBinding });
      if (!bindingAlive) {
        addLog(`无法启动：微信${slotId}绑定窗口已失效，请重新绑定`, "error");
        return;
      }

      addLog("正在校验会员状态...", "info");
      const res = await fetch(`${apiBase}/tasks/start-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          slot_id: slotId,
          target_type: targetType,
          daily_limit: dailyLimit,
          create_tag: createTag,
          greeting_text: greetingText || null,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.can_start) {
        addLog(`无法启动: ${data.reason || "校验失败"}`, "error");
        const noRemainingAccess = !data.membership?.is_active && (data.trial?.remaining ?? 0) <= 0;
        if (noRemainingAccess) {
          await onStatusChange({ force: true });
          onOpenPayment();
        }
        return;
      }

      setTaskId(data.task_id);
      taskIdRef.current = data.task_id;
      isFinishingRef.current = false;
      setIsRunning(true);

      addLog(`正在领取${targetTypeLabel(targetType)}任务数据...`, "info");
      const claimRes = await fetch(`${apiBase}/tasks/${data.task_id}/claim-targets`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      const claimData: ClaimTargetsResponse = await claimRes.json();
      if (!claimRes.ok) {
        throw new Error((claimData as any)?.detail || "领取任务数据失败");
      }
      if (!claimData.targets.length) {
        addLog(`暂无可执行的${targetTypeLabel(targetType)}任务数据`, "error");
        await finishCurrentTask();
        return;
      }

      const config = {
        run_id: String(data.task_id),
        task_id: data.task_id,
        slot_id: slotId,
        target_type: claimData.target_type,
        daily_limit: dailyLimit,
        create_tag: createTag,
        greeting_text: greetingText,
        wechat_binding: wechatBinding,
        targets: claimData.targets,
      };

      addLog(`已领取 ${claimData.targets.length} 条${targetTypeLabel(claimData.target_type)}数据，正在启动脚本`, "info");
      await invoke("start_task", { configJson: JSON.stringify(config) });
    } catch (e: any) {
      addLog(`启动失败: ${e}`, "error");
      if (taskIdRef.current) {
        await finishCurrentTask();
      } else {
        setIsRunning(false);
      }
    }
  };

  const handleStartClick = () => {
    if (!isOnline || isRunning || startCountdown > 0) return;
    setShowAutomationPrompt(true);
  };

  const handleCancelAutomationPrompt = useCallback(() => {
    clearStartDelay();
    setShowAutomationPrompt(false);
  }, [clearStartDelay]);

  const handleConfirmAutomationPrompt = () => {
    if (startCountdown > 0) return;
    let remaining = START_DELAY_SECONDS;
    setStartCountdown(remaining);
    addLog(`已确认自动化提示，${START_DELAY_SECONDS} 秒后启动，请切换到微信${slotId}主窗口`, "info");
    startCountdownTimerRef.current = setInterval(() => {
      remaining -= 1;
      setStartCountdown(Math.max(remaining, 0));
    }, 1000);
    startDelayTimerRef.current = setTimeout(() => {
      clearStartDelay();
      setShowAutomationPrompt(false);
      runStartTask();
    }, START_DELAY_SECONDS * 1000);
  };

  const handleStop = async () => {
    addLog("正在停止任务...", "info");
    try {
      const runId = taskIdRef.current ? String(taskIdRef.current) : "";
      if (runId) await invoke("stop_task", { runId });
    } catch { /* ignore */ }
    await finishCurrentTask();
    addLog("任务已停止", "info");
  };

  return (
    <div className="task-panel">
      {/* Config section */}
      <div className="section-card task-config-card">
        <div className="task-config-header">
          <h3 className="section-title">微信{slotId}任务配置</h3>
          <div className="task-shortcuts">
            <button className="task-shortcut task-shortcut-warning" type="button" onClick={onOpenTutorial}>
              注意事项
            </button>
            <button className="task-shortcut task-shortcut-upgrade" type="button" onClick={onOpenPayment}>
              增加微信加人窗口
            </button>
          </div>
        </div>
        <div className="task-config">
          <div className="config-row">
            <div className="field daily-limit-field">
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
            <div className="greeting-presets">
              {DEFAULT_GREETING_TEXTS.map((text) => (
                <button
                  key={text}
                  className={`greeting-preset-btn${greetingText === text ? " active" : ""}`}
                  type="button"
                  disabled={isRunning}
                  onClick={() => setGreetingText(text)}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
          <div className="task-actions">
            {!isRunning ? (
              <button className="btn-start" onClick={handleStartClick} disabled={!isOnline || startCountdown > 0} title={!isOnline ? "网络已断开，无法启动任务" : ""}>
                {startCountdown > 0 ? "等待切换..." : "开始任务"}
              </button>
            ) : (
              <button className="btn-stop" onClick={handleStop}>停止任务</button>
            )}
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
          {logs.map((entry) => (
            <div key={entry.id} className={`term-line term-log term-log-${entry.type}`}>
              {entry.text}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>
        <div className="terminal-footer">
          全域行为监测系统实时在线，高密度连续发起链路申请将触发交互权限锁定，操作风险由使用者全权承担。本终端仅提供数据查阅能力，无自主批量交互执行模块。
        </div>
      </div>

      {showAutomationPrompt && (
        <div className="automation-warning-overlay" onClick={startCountdown > 0 ? undefined : handleCancelAutomationPrompt}>
          <div className="automation-warning-modal" onClick={(e) => e.stopPropagation()}>
            <div className="automation-warning-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="4" y="3" width="16" height="12" rx="2.5" />
                <path d="M8 21h8" />
                <path d="M12 15v6" />
                <path d="M9 7h6" />
                <path d="M9 10h3" />
              </svg>
            </div>
            <h3>自动化将控制鼠标和键盘</h3>
            <ol className="automation-warning-list">
              <li>请先打开微信主窗口（不必手动打开「添加朋友」）</li>
              <li>点击确认后有 5 秒切换到微信</li>
              <li>运行期间请勿操作浏览器或鼠标</li>
            </ol>
            {startCountdown > 0 && (
              <div className="automation-countdown">
                <strong>{startCountdown}</strong>
                <span>秒后开始，请切换到微信{slotId}主窗口</span>
              </div>
            )}
            <div className="automation-warning-actions">
              <button className="automation-secondary-btn" type="button" onClick={handleCancelAutomationPrompt}>
                {startCountdown > 0 ? "取消启动" : "取消"}
              </button>
              <button className="automation-primary-btn" type="button" onClick={handleConfirmAutomationPrompt} disabled={startCountdown > 0}>
                确认，5 秒后启动
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TaskPanel;
