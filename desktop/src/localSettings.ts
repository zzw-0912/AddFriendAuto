import {
  ADD_INTERVAL_MINUTE_OPTIONS,
  DEFAULT_TASK_DEFAULTS,
  TASK_SLOT_CONFIGS_STORAGE_KEY,
  WECHAT_BINDINGS_STORAGE_KEY,
  type AddIntervalMinutes,
  type TaskDefaults,
  type WeChatWindowBinding,
} from "./types";

const PRESET_COUNT = 3;

function normalizeGreetingPresets(value: unknown, fallback: TaskDefaults["greetingPresets"]): string[] {
  const source = Array.isArray(value) ? value : [];
  return Array.from({ length: PRESET_COUNT }, (_, index) => {
    const preset = source[index];
    return typeof preset === "string" ? preset.trim() : fallback[index] || "";
  });
}

function normalizeAddIntervalMinutes(value: unknown, fallback: AddIntervalMinutes): AddIntervalMinutes {
  const minutes = Number(value);
  if (ADD_INTERVAL_MINUTE_OPTIONS.includes(minutes as AddIntervalMinutes)) {
    return minutes as AddIntervalMinutes;
  }
  return fallback;
}

export function normalizeTaskDefaults(defaults: Partial<TaskDefaults> | null | undefined, fallback = DEFAULT_TASK_DEFAULTS): TaskDefaults {
  return {
    targetType: "contact",
    dailyLimit: Math.min(200, Math.max(1, Number(defaults?.dailyLimit) || fallback.dailyLimit)),
    addIntervalMinutes: normalizeAddIntervalMinutes(defaults?.addIntervalMinutes, fallback.addIntervalMinutes),
    createTag: Boolean(defaults?.createTag),
    greetingText: typeof defaults?.greetingText === "string" ? defaults.greetingText.trim() : fallback.greetingText,
    greetingPresets: normalizeGreetingPresets(defaults?.greetingPresets, fallback.greetingPresets),
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
