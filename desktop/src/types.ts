export interface TaskDefaults {
  dailyLimit: number;
  createTag: boolean;
  greetingText: string;
}

export const TASK_DEFAULTS_STORAGE_KEY = "friendauto.taskDefaults.v1";

export const DEFAULT_TASK_DEFAULTS: TaskDefaults = {
  dailyLimit: 20,
  createTag: false,
  greetingText: "",
};

export interface UserStatus {
  membership: { is_active: boolean; plan_id: number | null; ends_at: string | null };
  trial: { total: number; used: number; remaining: number };
}
