import {
  DEFAULT_TASK_DEFAULTS,
  TASK_SLOT_CONFIGS_STORAGE_KEY,
  WECHAT_BINDINGS_STORAGE_KEY,
  type TaskDefaults,
  type WeChatWindowBinding,
} from "./types";

export function normalizeTaskDefaults(defaults: Partial<TaskDefaults> | null | undefined, fallback = DEFAULT_TASK_DEFAULTS): TaskDefaults {
  return {
    targetType: "contact",
    dailyLimit: Math.min(200, Math.max(1, Number(defaults?.dailyLimit) || fallback.dailyLimit)),
    createTag: Boolean(defaults?.createTag),
    greetingText: typeof defaults?.greetingText === "string" ? defaults.greetingText.trim() : fallback.greetingText,
  };
}

export function loadTaskSlotConfigs(): Record<string, TaskDefaults> {
  try {
    const raw = localStorage.getItem(TASK_SLOT_CONFIGS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, Partial<TaskDefaults>>;
    return Object.fromEntries(
      Object.entries(parsed).map(([slotId, config]) => [slotId, normalizeTaskDefaults(config)]),
    );
  } catch {
    return {};
  }
}

export function loadTaskSlotConfig(slotId: number, fallback: TaskDefaults): TaskDefaults {
  return loadTaskSlotConfigs()[String(slotId)] ?? normalizeTaskDefaults(fallback);
}

export function saveTaskSlotConfig(slotId: number, config: TaskDefaults) {
  const configs = loadTaskSlotConfigs();
  configs[String(slotId)] = normalizeTaskDefaults(config);
  localStorage.setItem(TASK_SLOT_CONFIGS_STORAGE_KEY, JSON.stringify(configs));
}

export function loadWeChatBindings(): Record<string, WeChatWindowBinding> {
  try {
    const raw = localStorage.getItem(WECHAT_BINDINGS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, WeChatWindowBinding>;
    return Object.fromEntries(
      Object.entries(parsed).filter(([, binding]) => binding && binding.hwnd && binding.pid),
    );
  } catch {
    return {};
  }
}

export function saveWeChatBindings(bindings: Record<string, WeChatWindowBinding>) {
  localStorage.setItem(WECHAT_BINDINGS_STORAGE_KEY, JSON.stringify(bindings));
}
