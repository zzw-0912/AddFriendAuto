import { useCallback, useEffect, useRef, useState } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { isClientUpdateRequiredError, readErrorDetail } from "./api";
import { useNetworkStatus } from "./useNetworkStatus";
import { loadTaskSlotConfig, loadWeChatBindings, normalizeTaskDefaults, saveTaskSlotConfig, saveWeChatBindings } from "./localSettings";
import { ACCOUNT_AGE_PROFILE_OPTIONS, type AccountAgeProfile, type TargetType, type TaskDefaults, type UserStatus, type WeChatWindowBinding } from "./types";

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
  onOpenProfile: () => void;
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
  can_claim?: boolean;
  reason?: string | null;
  reason_code?: string | null;
  task_id: number;
  target_type: TargetType;
  count: number;
  targets: TaskTarget[];
  membership?: UserStatus["membership"] | null;
  trial?: UserStatus["trial"] | null;
}

interface ActiveTaskContext {
  taskId: number;
  safeConfig: TaskDefaults;
  wechatBinding: WeChatWindowBinding;
}

interface AccessSnapshot {
  membership?: UserStatus["membership"] | null;
  trial?: UserStatus["trial"] | null;
}

interface ResultResponse {
  charged?: boolean;
  duplicate?: boolean;
  updated?: boolean;
}

interface LogEntry {
  id: number;
  text: string;
  type: "normal" | "success" | "failed" | "invalid" | "error" | "info";
}

let logId = 0;

const BOOT_STEPS = [
  "AI模型正在思考中",
  "AI模型正在搜索中",
  "AI模型正在整合信息中",
];

const WAIT_HINTS = [
  "AI模型正在思考中...",
  "AI模型正在搜索中...",
  "AI模型正在信息验证中...",
];
const WAIT_HINT_INTERVAL_MS = 60_000;
const START_DELAY_SECONDS = 5;

function asAccessSnapshot(value: unknown): AccessSnapshot | null {
  if (!value || typeof value !== "object") return null;
  if (!("membership" in value) || !("trial" in value)) return null;
  return value as AccessSnapshot;
}

function trialRemaining(access: AccessSnapshot | null | undefined) {
  return Math.max(0, Number(access?.trial?.remaining ?? 0));
}

function isMembershipExpired(access: AccessSnapshot | null | undefined) {
  const membership = access?.membership;
  if (!membership || membership.is_active || !membership.ends_at) return false;
  const endsAt = new Date(membership.ends_at).getTime();
  return Number.isFinite(endsAt) && endsAt <= Date.now();
}

function needsPayment(access: AccessSnapshot | null | undefined) {
  if (!access) return false;
  return !access.membership?.is_active && trialRemaining(access) <= 0;
}

function accessNotice(access: AccessSnapshot | null | undefined) {
  if (!access) return "";
  if (access.membership?.is_active) return "会员状态正常";
  return `免费额度还剩 ${trialRemaining(access)} 次`;
}

function paymentNotice(access: AccessSnapshot | null | undefined) {
  return isMembershipExpired(access) ? "会员已过期，请充值后继续使用" : "免费额度已用完，请充值后继续使用";
}

function claimStopNotice(reasonCode?: string | null, reason?: string | null) {
  if (reasonCode === "goal_reached") return "任务已完成";
  if (reasonCode === "targets_exhausted") return "好友名单不足，本次任务未补满";
  return reason || "暂无可继续添加的好友名单";
}

function TaskPanel({
  apiBase,
  token,
  status,
  slotId,
  taskDefaults,
  taskDefaultsVersion,
  onStatusChange,
  onOpenTutorial,
  onOpenPayment,
  onOpenProfile,
}: Props) {
  const { isOnline } = useNetworkStatus();
  const [targetType, setTargetType] = useState<TargetType>(() => loadTaskSlotConfig(slotId, taskDefaults).targetType);
  const [dailyLimit, setDailyLimit] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).dailyLimit);
  const [accountAgeProfile, setAccountAgeProfile] = useState<AccountAgeProfile>(() => loadTaskSlotConfig(slotId, taskDefaults).accountAgeProfile);
  const [greetingText, setGreetingText] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).greetingText);
  const [greetingPresets, setGreetingPresets] = useState(() => loadTaskSlotConfig(slotId, taskDefaults).greetingPresets);
  const [isRunning, setIsRunning] = useState(false);
  const [, setTaskId] = useState<number | null>(null);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [bootSequenceKey, setBootSequenceKey] = useState(0);
  const [visibleSteps, setVisibleSteps] = useState(0);
  const [bootDone, setBootDone] = useState(false);
  const [toast, setToast] = useState("");
  const [bindingPromptMessage, setBindingPromptMessage] = useState("");
  const [showAutomationPrompt, setShowAutomationPrompt] = useState(false);
  const [startCountdown, setStartCountdown] = useState(0);
  const logEndRef = useRef<HTMLDivElement>(null);
  const taskIdRef = useRef<number | null>(null);
  const activeTaskContextRef = useRef<ActiveTaskContext | null>(null);
  const isFinishingRef = useRef(false);
  const hasRunErrorRef = useRef(false);
  const resultReportFailedRef = useRef(false);
  const manualStopRequestedRef = useRef(false);
  const batchFinishedRef = useRef(false);
  const batchExitHandledRef = useRef(false);
  const successCountRef = useRef(0);
  const processedResultKeysRef = useRef<Set<string>>(new Set());
  const pendingResultReportsRef = useRef<Set<Promise<ResultResponse | null>>>(new Set());
  const lastLogTextRef = useRef("");
  const lastTrialRemainingRef = useRef<number | null>(null);
  const startDelayTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const startCountdownTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const toastTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const waitHintTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const waitHintIndexRef = useRef(0);

  const showToast = (message: string) => {
    setToast(message);
    if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
    toastTimerRef.current = setTimeout(() => setToast(""), 2200);
  };

  const addLog = useCallback((text: string, type: LogEntry["type"] = "info") => {
    logId += 1;
    lastLogTextRef.current = text;
    setLogs((prev) => [...prev, { id: logId, text, type }]);
  }, []);

  const addUniqueLog = useCallback((text: string, type: LogEntry["type"] = "info") => {
    if (lastLogTextRef.current === text) return;
    addLog(text, type);
  }, [addLog]);

  const addAccessLog = useCallback((access: AccessSnapshot | null | undefined) => {
    if (!access) return;
    if (access.membership?.is_active) {
      addUniqueLog(accessNotice(access), "info");
      return;
    }

    const remaining = trialRemaining(access);
    if (lastTrialRemainingRef.current === remaining) return;
    lastTrialRemainingRef.current = remaining;
    addUniqueLog(accessNotice(access), remaining > 0 ? "info" : "error");
  }, [addUniqueLog]);

  const startBootSequence = useCallback(() => {
    setVisibleSteps(0);
    setBootDone(false);
    setBootSequenceKey((prev) => prev + 1);
  }, []);

  const clearWaitHintTimer = useCallback((resetIndex = false) => {
    if (waitHintTimerRef.current) {
      clearInterval(waitHintTimerRef.current);
      waitHintTimerRef.current = null;
    }
    if (resetIndex) {
      waitHintIndexRef.current = 0;
    }
  }, []);

  const appendWaitHint = useCallback(() => {
    const hint = WAIT_HINTS[waitHintIndexRef.current % WAIT_HINTS.length];
    waitHintIndexRef.current += 1;
    addLog(hint, "info");
  }, [addLog]);

  const startWaitHintTimer = useCallback(() => {
    clearWaitHintTimer(true);
    appendWaitHint();
    waitHintTimerRef.current = setInterval(appendWaitHint, WAIT_HINT_INTERVAL_MS);
  }, [appendWaitHint, clearWaitHintTimer]);

  const writeClientLog = useCallback((message: string) => {
    void invoke("write_client_log", { message }).catch(() => {});
  }, []);

  const resetBatchLifecycle = useCallback(() => {
    batchFinishedRef.current = false;
    batchExitHandledRef.current = false;
  }, []);

  const requestWorkerStop = useCallback(async () => {
    const runId = taskIdRef.current ? String(taskIdRef.current) : "";
    if (!runId) return;
    try {
      await invoke("stop_task", { runId });
    } catch {
      // Ignore stop errors; the batch exit handler will still clean up.
    }
  }, []);

  const reportResult = useCallback(async (
    contactId: string | number | undefined,
    targetId: string | number | undefined,
    event: string,
    message: string,
  ): Promise<ResultResponse | null> => {
    const tid = taskIdRef.current;
    if (!tid || (!targetId && !contactId)) {
      writeClientLog(`result_report_skip task_id=${tid || ""} target_id=${targetId || ""} contact_id=${contactId || ""} event=${event}`);
      return null;
    }
    const payload = {
      target_id: targetId ? Number(targetId) : undefined,
      contact_id: contactId ? Number(contactId) : undefined,
      event,
      message,
    };
    writeClientLog(`result_report_start task_id=${tid} target_id=${payload.target_id || ""} contact_id=${payload.contact_id || ""} event=${event}`);
    try {
      const res = await fetch(`${apiBase}/tasks/${tid}/results`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      const responseText = await res.text();
      writeClientLog(
        `result_report_response task_id=${tid} target_id=${payload.target_id || ""} event=${event} status=${res.status} ok=${res.ok} body=${responseText.slice(0, 500)}`,
      );
      if (!res.ok) return null;
      return JSON.parse(responseText || "{}") as ResultResponse;
    } catch (err) {
      writeClientLog(`result_report_error task_id=${tid} target_id=${payload.target_id || ""} event=${event} error=${String(err)}`);
      return null;
    }
  }, [apiBase, token, writeClientLog]);

  const waitForPendingResultReports = useCallback(async () => {
    const pending = Array.from(pendingResultReportsRef.current);
    if (!pending.length) return;
    await Promise.allSettled(pending);
  }, []);

  const finishCurrentTask = useCallback(async () => {
    const tid = taskIdRef.current;
    if (!tid || isFinishingRef.current) return;
    clearWaitHintTimer(true);
    isFinishingRef.current = true;
    await waitForPendingResultReports();
    try {
      await fetch(`${apiBase}/tasks/${tid}/finish`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      writeClientLog(`task_finish_response task_id=${tid} ok=true`);
    } catch {
      writeClientLog(`task_finish_error task_id=${tid}`);
      addUniqueLog("任务状态同步失败，请稍后刷新", "error");
    }
    activeTaskContextRef.current = null;
    setTaskId(null);
    taskIdRef.current = null;
    setIsRunning(false);
    manualStopRequestedRef.current = false;
    hasRunErrorRef.current = false;
    resultReportFailedRef.current = false;
    batchFinishedRef.current = false;
    batchExitHandledRef.current = false;
    successCountRef.current = 0;
    isFinishingRef.current = false;
    const latestStatus = asAccessSnapshot(await onStatusChange({ force: true }));
    addAccessLog(latestStatus);
  }, [addAccessLog, addUniqueLog, apiBase, clearWaitHintTimer, onStatusChange, token, waitForPendingResultReports, writeClientLog]);

  const refreshAccessLog = useCallback(async () => {
    const latestStatus = asAccessSnapshot(await onStatusChange({ force: true }));
    if (!latestStatus) return;
    if (needsPayment(latestStatus)) {
      addUniqueLog(paymentNotice(latestStatus), "error");
      onOpenPayment();
      return;
    }
    addAccessLog(latestStatus);
  }, [addAccessLog, addUniqueLog, onOpenPayment, onStatusChange]);

  const claimAndStartNextBatch = useCallback(async (continuation: boolean) => {
    const context = activeTaskContextRef.current;
    const tid = taskIdRef.current;
    if (!context || !tid || manualStopRequestedRef.current || isFinishingRef.current) return false;

    if (continuation) {
      const message = successCountRef.current > 0
        ? `已成功 ${successCountRef.current} 个，正在补领下一批好友名单`
        : "正在补领下一批好友名单";
      addUniqueLog(message, "info");
    }

    writeClientLog(`claim_targets_start task_id=${tid} continuation=${continuation}`);
    try {
      const claimRes = await fetch(`${apiBase}/tasks/${tid}/claim-targets`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!claimRes.ok) {
        throw new Error((await readErrorDetail(claimRes)) || "准备任务失败");
      }

      const claimData: ClaimTargetsResponse = await claimRes.json();
      writeClientLog(
        `claim_targets_response task_id=${tid} continuation=${continuation} can_claim=${String(claimData.can_claim ?? true)} count=${claimData.count} reason_code=${claimData.reason_code || ""}`,
      );

      const claimAccess = asAccessSnapshot(claimData);
      addAccessLog(claimAccess);
      if (claimData.can_claim === false || !claimData.targets.length) {
        addUniqueLog(claimStopNotice(claimData.reason_code, claimData.reason), claimData.reason_code === "goal_reached" ? "success" : "error");
        await finishCurrentTask();
        if (needsPayment(claimAccess)) {
          onOpenPayment();
        }
        return false;
      }

      resetBatchLifecycle();
      const config = {
        run_id: String(tid),
        task_id: tid,
        slot_id: slotId,
        target_type: claimData.target_type,
        daily_limit: context.safeConfig.dailyLimit,
        account_age_profile: context.safeConfig.accountAgeProfile,
        create_tag: false,
        greeting_text: context.safeConfig.greetingText,
        wechat_binding: context.wechatBinding,
        targets: claimData.targets,
      };

      writeClientLog(`start_batch task_id=${tid} continuation=${continuation} targets=${claimData.targets.length}`);
      if (!continuation) {
        addUniqueLog("正在打开微信中", "info");
      }
      await invoke("start_task", { configJson: JSON.stringify(config) });
      return true;
    } catch (error) {
      if (isClientUpdateRequiredError(error)) {
        clearWaitHintTimer(true);
        activeTaskContextRef.current = null;
        setTaskId(null);
        taskIdRef.current = null;
        setIsRunning(false);
        return false;
      }

      writeClientLog(`claim_targets_error task_id=${tid} continuation=${continuation} error=${String(error)}`);
      addUniqueLog(continuation ? "补领下一批失败，请稍后重试" : "启动失败，请稍后重试", "error");
      if (taskIdRef.current) {
        await finishCurrentTask();
      } else {
        setIsRunning(false);
      }
      return false;
    }
  }, [
    addAccessLog,
    addUniqueLog,
    apiBase,
    clearWaitHintTimer,
    finishCurrentTask,
    onOpenPayment,
    resetBatchLifecycle,
    slotId,
    token,
    writeClientLog,
  ]);

  const handleBatchExited = useCallback(async () => {
    clearWaitHintTimer(true);
    if (batchExitHandledRef.current) return;
    batchExitHandledRef.current = true;
    if (manualStopRequestedRef.current || isFinishingRef.current) return;
    if (!taskIdRef.current) return;

    await waitForPendingResultReports();
    if (manualStopRequestedRef.current || isFinishingRef.current) return;

    if (!batchFinishedRef.current) {
      if (!hasRunErrorRef.current) {
        hasRunErrorRef.current = true;
        addUniqueLog("任务运行异常，请稍后重试", "error");
      }
      await finishCurrentTask();
      return;
    }

    if (hasRunErrorRef.current || resultReportFailedRef.current) {
      await finishCurrentTask();
      return;
    }

    await claimAndStartNextBatch(true);
  }, [addUniqueLog, claimAndStartNextBatch, clearWaitHintTimer, finishCurrentTask, waitForPendingResultReports]);

  const queueResultReport = useCallback((
    contactId: string | number | undefined,
    targetId: string | number | undefined,
    event: string,
    message: string,
  ) => {
    const reportPromise = reportResult(contactId, targetId, event, message).then((result) => {
      if (!result) {
        if (!resultReportFailedRef.current) {
          resultReportFailedRef.current = true;
          hasRunErrorRef.current = true;
          addUniqueLog("任务结果同步失败，已停止本次任务", "error");
          void requestWorkerStop();
        }
        return null;
      }

      if (event === "success") {
        successCountRef.current += 1;
        void refreshAccessLog();
      } else if (result.charged) {
        void refreshAccessLog();
      }
      return result;
    });
    pendingResultReportsRef.current.add(reportPromise);
    void reportPromise.finally(() => {
      pendingResultReportsRef.current.delete(reportPromise);
    });
    return reportPromise;
  }, [addUniqueLog, refreshAccessLog, reportResult, requestWorkerStop]);

  const handleScriptEvent = useCallback((event: { payload: string }) => {
    try {
      const data: ScriptEvent = JSON.parse(event.payload);
      const currentRunId = taskIdRef.current ? String(taskIdRef.current) : "";
      const eventRunId = data.run_id ? String(data.run_id) : "";
      if (data.slot_id && data.slot_id !== slotId) return;
      if (eventRunId && currentRunId && eventRunId !== currentRunId) return;
      if (eventRunId && !currentRunId) return;

      if (data.event === "exited") {
        void handleBatchExited();
        return;
      }

      const msg = data.message || data.event;
      const resultKey = `${data.run_id || taskIdRef.current || ""}:${data.target_id || data.contact_id || ""}:${data.event}`;
      const isResultEvent = data.event === "success" || data.event === "failed" || data.event === "invalid";
      if (isResultEvent && processedResultKeysRef.current.has(resultKey)) {
        return;
      }

      switch (data.event) {
        case "started":
          clearWaitHintTimer(true);
          break;
        case "progress":
          if (msg.includes("等待下一次加好友")) {
            startWaitHintTimer();
          } else if (msg.includes("开始处理联系人")) {
            clearWaitHintTimer(true);
          }
          break;
        case "success":
          clearWaitHintTimer(true);
          processedResultKeysRef.current.add(resultKey);
          void queueResultReport(data.contact_id, data.target_id, data.event, msg);
          break;
        case "failed":
          clearWaitHintTimer(true);
          processedResultKeysRef.current.add(resultKey);
          void queueResultReport(data.contact_id, data.target_id, data.event, msg);
          break;
        case "invalid":
          clearWaitHintTimer(true);
          processedResultKeysRef.current.add(resultKey);
          void queueResultReport(data.contact_id, data.target_id, data.event, msg);
          break;
        case "error":
          clearWaitHintTimer(true);
          if (!manualStopRequestedRef.current) {
            hasRunErrorRef.current = true;
            addUniqueLog("任务运行异常，请稍后重试", "error");
            void requestWorkerStop();
          }
          break;
        case "finished":
          clearWaitHintTimer(true);
          batchFinishedRef.current = true;
          break;
        default:
          break;
      }
    } catch {
      // Ignore malformed worker progress payloads; user-facing status stays on the AI step animation.
    }
  }, [addUniqueLog, clearWaitHintTimer, handleBatchExited, queueResultReport, requestWorkerStop, slotId, startWaitHintTimer]);

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
    if (!bootSequenceKey || bootDone) return;
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
  }, [bootDone, bootSequenceKey]);

  useEffect(() => {
    if (isRunning) return;
    const slotConfig = loadTaskSlotConfig(slotId, taskDefaults);
    setTargetType(slotConfig.targetType);
    setDailyLimit(slotConfig.dailyLimit);
    setAccountAgeProfile(slotConfig.accountAgeProfile);
    setGreetingText(slotConfig.greetingText);
    setGreetingPresets(slotConfig.greetingPresets);
  }, [isRunning, slotId, taskDefaults, taskDefaultsVersion]);

  useEffect(() => {
    return () => {
      if (startDelayTimerRef.current) clearTimeout(startDelayTimerRef.current);
      if (startCountdownTimerRef.current) clearInterval(startCountdownTimerRef.current);
      if (toastTimerRef.current) clearTimeout(toastTimerRef.current);
      clearWaitHintTimer(true);
    };
  }, [clearWaitHintTimer]);

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

  const handleGreetingPresetChange = (index: number, value: string) => {
    setGreetingPresets((prev) => prev.map((preset, i) => (i === index ? value : preset)));
  };

  const handleAccountAgeProfileChange = (profile: AccountAgeProfile) => {
    const option = ACCOUNT_AGE_PROFILE_OPTIONS.find((item) => item.value === profile);
    setAccountAgeProfile(profile);
    if (option) setDailyLimit(option.dailyLimit);
  };

  const handleSaveConfig = () => {
    const nextConfig = normalizeTaskDefaults(
      { targetType, dailyLimit, accountAgeProfile, createTag: false, greetingText, greetingPresets },
      taskDefaults,
    );
    setGreetingText(nextConfig.greetingText);
    setGreetingPresets(nextConfig.greetingPresets);
    saveTaskSlotConfig(slotId, nextConfig);
    addUniqueLog("任务配置已保存", "success");
    showToast(`微信${slotId}配置已保存`);
  };

  const checkWechatBinding = async (): Promise<{ binding: WeChatWindowBinding | null; message: string | null }> => {
    const wechatBinding = loadWeChatBindings()[String(slotId)];
    if (!wechatBinding) {
      return {
        binding: null,
        message: `微信${slotId}还没有绑定窗口，请先去绑定后再开始任务`,
      };
    }

    try {
      const refreshedBinding = await invoke<WeChatWindowBinding>("ensure_wechat_binding", { binding: wechatBinding });
      const bindings = loadWeChatBindings();
      bindings[String(slotId)] = { ...wechatBinding, ...refreshedBinding, slotId };
      saveWeChatBindings(bindings);
      return { binding: bindings[String(slotId)], message: null };
    } catch (err) {
      return {
        binding: null,
        message: String(err || `微信${slotId}自动打开失败，请重新绑定后再开始任务`),
      };
    }
  };

  const runStartTask = async () => {
    if (!isOnline) {
      addUniqueLog("网络已断开，请恢复后再开始", "error");
      return;
    }

    const bindingCheck = await checkWechatBinding();
    const wechatBinding = bindingCheck.binding;
    if (!wechatBinding) {
      addUniqueLog(bindingCheck.message || `请先在“我的”页面绑定微信${slotId}窗口`, "error");
      return;
    }

    setLogs([]);
    lastLogTextRef.current = "";
    lastTrialRemainingRef.current = null;
    manualStopRequestedRef.current = false;
    hasRunErrorRef.current = false;
    resultReportFailedRef.current = false;
    batchFinishedRef.current = false;
    batchExitHandledRef.current = false;
    successCountRef.current = 0;
    processedResultKeysRef.current.clear();
    clearWaitHintTimer(true);

    try {
      const safeConfig = normalizeTaskDefaults(
        { targetType, dailyLimit, accountAgeProfile, createTag: false, greetingText, greetingPresets },
        taskDefaults,
      );

      addUniqueLog("正在打开微信中", "info");

      addUniqueLog("正在同步免费额度", "info");
      const res = await fetch(`${apiBase}/tasks/start-check`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          slot_id: slotId,
          target_type: targetType,
          daily_limit: dailyLimit,
          create_tag: false,
          greeting_text: safeConfig.greetingText || null,
        }),
      });
      const data = await res.json();
      if (!res.ok || !data.can_start) {
        const access = { membership: data.membership, trial: data.trial };
        if (needsPayment(access)) {
          addUniqueLog(paymentNotice(access), "error");
          await onStatusChange({ force: true });
          onOpenPayment();
        } else {
          addUniqueLog("暂时无法启动任务，请稍后重试", "error");
        }
        return;
      }

      const access = { membership: data.membership, trial: data.trial };
      addAccessLog(access);
      setTaskId(data.task_id);
      taskIdRef.current = data.task_id;
      activeTaskContextRef.current = {
        taskId: data.task_id,
        safeConfig,
        wechatBinding,
      };
      isFinishingRef.current = false;
      setIsRunning(true);
      startBootSequence();
      await claimAndStartNextBatch(false);
    } catch (e: any) {
      if (isClientUpdateRequiredError(e)) {
        clearWaitHintTimer(true);
        setIsRunning(false);
        return;
      }
      addUniqueLog("启动失败，请稍后重试", "error");
      if (taskIdRef.current) {
        await finishCurrentTask();
      } else {
        setIsRunning(false);
      }
    }
  };

  const handleStartClick = async () => {
    if (!isOnline || isRunning || startCountdown > 0) return;
    const latestStatus = asAccessSnapshot(await onStatusChange({ force: true })) ?? status;
    if (needsPayment(latestStatus)) {
      addUniqueLog(paymentNotice(latestStatus), "error");
      onOpenPayment();
      return;
    }
    const wechatBinding = loadWeChatBindings()[String(slotId)];
    if (!wechatBinding) {
      const message = `微信${slotId}还没有绑定窗口，请先去绑定后再开始任务`;
      addUniqueLog(message, "error");
      setBindingPromptMessage(message);
      return;
    }
    setShowAutomationPrompt(true);
  };

  const handleCancelAutomationPrompt = useCallback(() => {
    clearStartDelay();
    setShowAutomationPrompt(false);
  }, [clearStartDelay]);

  const handleCloseBindingPrompt = useCallback(() => {
    setBindingPromptMessage("");
  }, []);

  const handleGoBindWechat = useCallback(() => {
    setBindingPromptMessage("");
    onOpenProfile();
  }, [onOpenProfile]);

  const handleConfirmAutomationPrompt = () => {
    if (startCountdown > 0) return;
    let remaining = START_DELAY_SECONDS;
    setStartCountdown(remaining);
    addUniqueLog(`${START_DELAY_SECONDS} 秒后将自动打开微信${slotId}并开始任务`, "info");
    startCountdownTimerRef.current = setInterval(() => {
      remaining -= 1;
      setStartCountdown(Math.max(remaining, 0));
    }, 1000);
    startDelayTimerRef.current = setTimeout(() => {
      clearStartDelay();
      setShowAutomationPrompt(false);
      window.setTimeout(() => {
        runStartTask();
      }, 180);
    }, START_DELAY_SECONDS * 1000);
  };

  const handleStop = async () => {
    clearWaitHintTimer(true);
    manualStopRequestedRef.current = true;
    addUniqueLog("正在停止任务", "info");
    try {
      const runId = taskIdRef.current ? String(taskIdRef.current) : "";
      if (runId) await invoke("stop_task", { runId });
    } catch { /* ignore */ }
    await finishCurrentTask();
    addUniqueLog("任务已停止", "info");
  };

  return (
    <div className="task-panel">
      {toast && <div className="toast show">{toast}</div>}
      {/* Config section */}
      <div className="section-card task-config-card">
        <div className="task-config-header">
          <h3 className="section-title">微信{slotId}任务配置</h3>
          <div className="task-shortcuts">
            <button className="task-shortcut task-shortcut-warning" type="button" onClick={onOpenTutorial}>
              启动前必看
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
            <div className="field add-interval-field">
              <label>加人间隔</label>
              <div className="add-interval-options" role="radiogroup" aria-label="加人间隔">
                {ACCOUNT_AGE_PROFILE_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className={`add-interval-option${accountAgeProfile === option.value ? " active" : ""}`}
                    disabled={isRunning}
                    onClick={() => handleAccountAgeProfileChange(option.value)}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
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
              {greetingPresets.map((text, index) => (
                <div key={index} className={`greeting-preset-editor${greetingText === text && text ? " active" : ""}`}>
                  <textarea
                    className="input greeting-preset-input"
                    value={text}
                    rows={2}
                    disabled={isRunning}
                    placeholder={`默认招呼语 ${index + 1}`}
                    onChange={(e) => handleGreetingPresetChange(index, e.target.value)}
                  />
                  <button
                    className="greeting-preset-use-btn"
                    type="button"
                    disabled={isRunning || !text.trim()}
                    onClick={() => setGreetingText(text.trim())}
                  >
                    使用
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div className="task-actions">
            <button className="btn-save-config" type="button" onClick={handleSaveConfig} disabled={isRunning}>
              保存配置
            </button>
            {!isRunning ? (
              <button className="btn-start" onClick={handleStartClick} disabled={!isOnline || startCountdown > 0} title={!isOnline ? "网络已断开，无法启动任务" : ""}>
                {startCountdown > 0 ? "等待启动..." : "开始任务"}
              </button>
            ) : (
              <button className="btn-stop" onClick={handleStop}>停止任务</button>
            )}
          </div>
        </div>
      </div>

      {/* Task reminders */}
      <div className="section-card terminal-card">
        <div className="terminal-header">
          <div className="terminal-dots">
            <span className="terminal-dot dot-red" />
            <span className="terminal-dot dot-yellow" />
            <span className="terminal-dot dot-green" />
          </div>
          <span className="terminal-title">任务提醒</span>
          <span className="terminal-safety">运行期间请不要操作鼠标和键盘</span>
        </div>
        <div className="terminal-body">
          <div className="term-line term-title">任务状态</div>
          {bootSequenceKey > 0 && BOOT_STEPS.slice(0, visibleSteps).map((step, i) => (
            <div key={i} className="term-line term-status">
              <span className="term-arrow">▶</span> {step}...
              <span className="term-ok">完成</span>
            </div>
          ))}
          {bootSequenceKey > 0 && !bootDone && visibleSteps < BOOT_STEPS.length && <span className="term-cursor">█</span>}
          {bootSequenceKey === 0 && (
            <div className="term-line term-ready">等待开始任务</div>
          )}
          {bootSequenceKey > 0 && bootDone && (
            <div className="term-line term-ready">{isRunning ? "任务运行中，请勿操作鼠标和键盘" : "等待开始任务"}</div>
          )}
          {logs.map((entry) => (
            <div key={entry.id} className={`term-line term-log term-log-${entry.type}`}>
              {entry.text}
            </div>
          ))}
          <div ref={logEndRef} />
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
              <li>点击确认后有 5 秒准备时间</li>
              <li>倒计时结束后会自动打开或唤起已绑定的微信窗口</li>
              <li>运行期间请不要操作鼠标和键盘</li>
            </ol>
            {startCountdown > 0 && (
              <div className="automation-countdown">
                <strong>{startCountdown}</strong>
                <span>秒后自动打开微信{slotId}并启动</span>
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

      {bindingPromptMessage && (
        <div className="automation-warning-overlay" onClick={handleCloseBindingPrompt}>
          <div className="automation-warning-modal" onClick={(e) => e.stopPropagation()}>
            <div className="automation-warning-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
                <rect x="4" y="3" width="16" height="12" rx="2.5" />
                <path d="M8 21h8" />
                <path d="M12 15v6" />
                <path d="M8 8h8" />
              </svg>
            </div>
            <h3>请先绑定微信窗口</h3>
            <ol className="automation-warning-list">
              <li>{bindingPromptMessage}</li>
              <li>绑定完成后，再返回当前任务卡开始任务即可。</li>
            </ol>
            <div className="automation-warning-actions">
              <button className="automation-secondary-btn" type="button" onClick={handleCloseBindingPrompt}>
                取消
              </button>
              <button className="automation-primary-btn" type="button" onClick={handleGoBindWechat}>
                去绑定
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default TaskPanel;
