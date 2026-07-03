import {
  ACCOUNT_AGE_PROFILE_OPTIONS,
  DEFAULT_TASK_DEFAULTS,
  TASK_SLOT_CONFIGS_STORAGE_KEY,
  WECHAT_BINDINGS_STORAGE_KEY,
  type AccountAgeProfile,
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

function isAccountAgeProfile(value: unknown): value is AccountAgeProfile {
  return ACCOUNT_AGE_PROFILE_OPTIONS.some((option) => option.value === value);
}

function normalizeAccountAgeProfile(
  value: unknown,
  fallback: AccountAgeProfile,
  legacyMinutes?: unknown,
): AccountAgeProfile {
  if (isAccountAgeProfile(value)) return value;

  const minutes = Number(legacyMinutes);
  if (minutes === 20) return "new";
  if (minutes === 10) return "mid";
  if (minutes === 5) return "old";
  return fallback;
}

function profileDailyLimit(profile: AccountAgeProfile): number {
  return ACCOUNT_AGE_PROFILE_OPTIONS.find((option) => option.value === profile)?.dailyLimit ?? DEFAULT_TASK_DEFAULTS.dailyLimit;
}

type LegacyTaskDefaults = Partial<TaskDefaults> & {
  addIntervalMinutes?: unknown;
  add_interval_minutes?: unknown;
  account_age_profile?: unknown;
};

function normalizeDailyLimit(defaults: LegacyTaskDefaults | null | undefined, profile: AccountAgeProfile): number {
  if (defaults?.accountAgeProfile === undefined && defaults?.account_age_profile === undefined) {
    return profileDailyLimit(profile);
  }
  return Math.min(200, Math.max(1, Number(defaults?.dailyLimit) || profileDailyLimit(profile)));
}

export function normalizeTaskDefaults(defaults: Partial<TaskDefaults> | null | undefined, fallback = DEFAULT_TASK_DEFAULTS): TaskDefaults {
  const legacyDefaults = defaults as LegacyTaskDefaults | null | undefined;
  const accountAgeProfile = normalizeAccountAgeProfile(
    legacyDefaults?.accountAgeProfile ?? legacyDefaults?.account_age_profile,
    fallback.accountAgeProfile,
    legacyDefaults?.addIntervalMinutes ?? legacyDefaults?.add_interval_minutes,
  );

  return {
    targetType: "contact",
    dailyLimit: normalizeDailyLimit(legacyDefaults, accountAgeProfile),
    accountAgeProfile,
    createTag: false,
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
